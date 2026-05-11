# restart_workers.ps1
# Reinicia el servicio sd-worker en todos los workers de direct o indirect
# Uso: .\restart_workers.ps1 [-arch direct|indirect]

param(
    [string]$arch = "direct"
)

$tfDir  = Join-Path $PSScriptRoot "terraform\$arch"
$keyFile = Join-Path $PSScriptRoot "sd-$arch-key.pem"

if (-not (Test-Path $keyFile)) {
    Write-Error "No se encuentra la clave: $keyFile"
    exit 1
}

# Obtener IPs de los workers desde terraform output
Write-Host "Obteniendo IPs de workers ($arch)..." -ForegroundColor Cyan
Push-Location $tfDir
$ipsJson = terraform output -json ips | ConvertFrom-Json
Pop-Location

# Filtrar solo las IPs de workers
$workerIps = $ipsJson.PSObject.Properties |
    Where-Object { $_.Name -match "^worker" } |
    Sort-Object Name |
    Select-Object -ExpandProperty Value

if ($workerIps.Count -eq 0) {
    Write-Error "No se encontraron workers en el output de Terraform"
    exit 1
}

Write-Host "Workers encontrados: $($workerIps.Count)" -ForegroundColor Green
Write-Host ""

# Reiniciar en paralelo con jobs
$jobs = @()
foreach ($ip in $workerIps) {
    Write-Host "  Reiniciando $ip..." -ForegroundColor Yellow
    $jobs += Start-Job -ScriptBlock {
        param($ip, $key)
        $result = ssh -i $key -o StrictHostKeyChecking=no -o ConnectTimeout=10 `
            "ec2-user@$ip" "sudo systemctl restart sd-worker && echo OK"
        [PSCustomObject]@{ IP = $ip; Result = $result }
    } -ArgumentList $ip, $keyFile
}

# Esperar y mostrar resultados
$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

Write-Host ""
Write-Host "Resultado:" -ForegroundColor Cyan
foreach ($r in $results) {
    $status = if ($r.Result -match "OK") { "OK" } else { "ERROR" }
    $color  = if ($status -eq "OK") { "Green" } else { "Red" }
    Write-Host "  $($r.IP) -> $status" -ForegroundColor $color
}

Write-Host ""
Write-Host "Todos los workers reiniciados." -ForegroundColor Green

# Reiniciar el LB (solo en direct, indirect no tiene LB)
if ($arch -eq "direct") {
    $lbIp = $ipsJson.PSObject.Properties | Where-Object { $_.Name -eq "loadbalancer" } | Select-Object -ExpandProperty Value
    if ($lbIp) {
        Write-Host ""
        Write-Host "Reiniciando Load Balancer ($lbIp)..." -ForegroundColor Cyan
        # Esperar a que los workers se registren en el NameServer
        Start-Sleep -Seconds 10
        $lbResult = ssh -i $keyFile -o StrictHostKeyChecking=no -o ConnectTimeout=10 `
            "ec2-user@$lbIp" "sudo systemctl restart sd-lb && echo OK"
        $status = if ($lbResult -match "OK") { "OK" } else { "ERROR" }
        $color  = if ($status -eq "OK") { "Green" } else { "Red" }
        Write-Host "  Load Balancer -> $status" -ForegroundColor $color
    }
}
