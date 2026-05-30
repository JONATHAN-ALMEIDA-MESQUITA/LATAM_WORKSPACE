# Encerra processos nas portas da demo (8001 backend, 5173 frontend).
$ErrorActionPreference = "SilentlyContinue"
foreach ($port in @(8001, 5173)) {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        if ($pid -and $pid -ne 0) {
            Stop-Process -Id $pid -Force
            Write-Host "Porta $port — processo $pid encerrado." -ForegroundColor Yellow
        }
    }
}
Write-Host "Demo encerrada." -ForegroundColor Green
