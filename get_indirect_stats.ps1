# get_indirect_stats.ps1
# Espera a que las colas estén vacías, para workers, recoge stats y reinicia.
# Uso: .\get_indirect_stats.ps1

$keyFile = Join-Path $PSScriptRoot "sd-indirect-key.pem"
$tfDir   = Join-Path $PSScriptRoot "terraform\indirect"
$sshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15", "-i", $keyFile)

# 1. Obtener IPs
Write-Host "Obteniendo IPs..." -ForegroundColor Cyan
Push-Location $tfDir
$ips = terraform output -json ips | ConvertFrom-Json
Pop-Location

$infraIp   = $ips.PSObject.Properties | Where-Object { $_.Name -eq "infra" }   | Select-Object -ExpandProperty Value
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
    Write-Host "  Mensajes pendientes en cola: $total" -ForegroundColor Gray
    if ($total -eq 0) { break }
    Start-Sleep -Seconds 5
}
Write-Host "  Colas vacías!" -ForegroundColor Green
Start-Sleep -Seconds 2  # margen para que el último ack llegue al worker

# 3. Parar workers y recoger stats en paralelo
Write-Host ""
Write-Host "Parando workers y recogiendo stats..." -ForegroundColor Cyan

$jobs = @()
foreach ($w in $workerIps) {
    $jobs += Start-Job -Name $w.Name -ScriptBlock {
        param($name, $ip, $sshOpts)
        $log = ssh @sshOpts "ec2-user@$ip" `
            "sudo systemctl stop sd-worker 2>/dev/null; sleep 1; sudo journalctl -u sd-worker --no-pager -n 100 2>/dev/null"
        [PSCustomObject]@{ Name = $name; IP = $ip; Log = $log }
    } -ArgumentList $w.Name, $w.Value, (,$sshOpts)
}

$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

# 4. Mostrar stats
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " STATS INDIRECT WORKERS" -ForegroundColor Cyan
Write-Host "============================================================"

foreach ($r in ($results | Sort-Object Name)) {
    Write-Host ""
    Write-Host "--- $($r.Name) ($($r.IP)) ---" -ForegroundColor Yellow
    # Mostrar solo líneas con stats relevantes del worker
    $r.Log | Where-Object {
        $_ -match "STATS|Exitos|Fallos|Total|Throughput|ops/s|Success|Fail|sold|ticket|===|procesa"
    } | ForEach-Object { Write-Host "  $_" }
}

# 5. Reiniciar workers para el siguiente benchmark
Write-Host ""
Write-Host "Reiniciando workers..." -ForegroundColor Cyan
$restartJobs = @()
foreach ($w in $workerIps) {
    $restartJobs += Start-Job -ScriptBlock {
        param($ip, $sshOpts)
        ssh @sshOpts "ec2-user@$ip" "sudo systemctl start sd-worker && echo OK"
    } -ArgumentList $w.Value, (,$sshOpts)
}
$restartJobs | Wait-Job | Receive-Job | ForEach-Object { Write-Host "  $_" }
$restartJobs | Remove-Job

Write-Host ""
Write-Host "Listo para el siguiente benchmark." -ForegroundColor Green
