# get_indirect_stats.ps1
# Espera a que las colas estén vacías, para workers, muestra tabla de stats y reinicia.
# Uso: .\get_indirect_stats.ps1

$keyFile = Join-Path $PSScriptRoot "sd-indirect-key.pem"
$tfDir   = Join-Path $PSScriptRoot "terraform\indirect"
$sshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15", "-i", $keyFile)

# 1. Obtener IPs
Write-Host "Obteniendo IPs..." -ForegroundColor Cyan
Push-Location $tfDir
$ips = terraform output -json ips | ConvertFrom-Json
Pop-Location

$infraIp   = $ips.PSObject.Properties | Where-Object { $_.Name -eq "infra" } | Select-Object -ExpandProperty Value
$workerIps = $ips.PSObject.Properties | Where-Object { $_.Name -match "^worker" } | Sort-Object Name | Select-Object Name, Value

# 2. Esperar colas vacías
Write-Host ""
Write-Host "Esperando a que las colas de RabbitMQ se vacíen..." -ForegroundColor Yellow
while ($true) {
    $output = ssh @sshOpts "ec2-user@$infraIp" "sudo rabbitmqctl list_queues name messages 2>/dev/null"
    $total  = 0
    foreach ($line in $output) {
        if ($line -match "ticket_.*\s+(\d+)") { $total += [int]$matches[1] }
    }
    Write-Host "  Mensajes pendientes: $total" -ForegroundColor Gray
    if ($total -eq 0) { break }
    Start-Sleep -Seconds 5
}
Write-Host "  Colas vacías!" -ForegroundColor Green
Start-Sleep -Seconds 2

# 3. Parar workers y recoger logs en paralelo
Write-Host ""
Write-Host "Recogiendo stats de workers..." -ForegroundColor Cyan

$jobs = @()
foreach ($w in $workerIps) {
    $jobs += Start-Job -Name $w.Name -ScriptBlock {
        param($name, $ip, $sshOpts)
        # Parar el worker y leer TODO el log desde que arrancó
        $log = ssh @sshOpts "ec2-user@$ip" `
            "sudo systemctl stop sd-worker 2>/dev/null; sleep 1; sudo journalctl -u sd-worker --no-pager 2>/dev/null"
        [PSCustomObject]@{ Name = $name; IP = $ip; Log = $log }
    } -ArgumentList $w.Name, $w.Value, (,$sshOpts)
}

$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

# 4. Parsear stats y mostrar tabla
function Parse-WorkerStats($log) {
    $stats = @{}
    $cola  = ""
    foreach ($line in $log) {
        # Detectar cola (puede tener caracteres raros por encoding del em-dash)
        if ($line -match "cola:\s*(ticket_\w+)")       { $cola = $matches[1] }
        if (-not $cola) { continue }
        if ($line -match "Exitos\s*:\s*(\d+)")         { $stats["${cola}_ok"]  = [int]$matches[1] }
        if ($line -match "Fallos\s*:\s*(\d+)")         { $stats["${cola}_ko"]  = [int]$matches[1] }
        if ($line -match "Total ops\s*:\s*(\d+)")      { $stats["${cola}_tot"] = [int]$matches[1] }
        if ($line -match "Throughput:\s*([\d.]+)")     { $stats["${cola}_thr"] = [double]$matches[1] }
    }
    return $stats
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RESUMEN INDIRECT WORKERS" -ForegroundColor Cyan
Write-Host "============================================================"

$tableRows = @()
foreach ($r in ($results | Sort-Object Name)) {
    $s = Parse-WorkerStats $r.Log

    foreach ($cola in @("ticket_unnumbered", "ticket_numbered")) {
        $ok  = if ($null -ne $s["${cola}_ok"])  { $s["${cola}_ok"]  } else { "-" }
        $ko  = if ($null -ne $s["${cola}_ko"])  { $s["${cola}_ko"]  } else { "-" }
        $tot = if ($null -ne $s["${cola}_tot"]) { $s["${cola}_tot"] } else { "-" }
        $thr = if ($null -ne $s["${cola}_thr"]) { $s["${cola}_thr"] } else { "-" }
        $tableRows += [PSCustomObject]@{
            Worker     = $r.Name
            Cola       = $cola -replace "ticket_", ""
            Exitos     = $ok
            Fallos     = $ko
            Total      = $tot
            "ops/s"    = $thr
        }
    }
}

$tableRows | Format-Table -AutoSize

# 5. Reiniciar workers
Write-Host "Reiniciando workers para el siguiente benchmark..." -ForegroundColor Cyan
$restartJobs = @()
foreach ($w in $workerIps) {
    $restartJobs += Start-Job -ScriptBlock {
        param($ip, $sshOpts)
        ssh @sshOpts "ec2-user@$ip" "sudo systemctl start sd-worker 2>/dev/null && echo OK"
    } -ArgumentList $w.Value, (,$sshOpts)
}
$restartJobs | Wait-Job | Out-Null
$restartJobs | Remove-Job

Write-Host "Listo para el siguiente benchmark." -ForegroundColor Green
