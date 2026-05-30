# Sobe backend + frontend para a demo (Windows / PowerShell).
# Uso (na raiz do projeto, terminal VS Code):
#   .\scripts\start-demo.ps1
#
# Abre duas janelas de terminal (backend e frontend) para voce ver os logs.
# Para encerrar: feche as janelas ou rode .\scripts\stop-demo.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Port = 8001

$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Setup incompleto. Rode primeiro: .\scripts\setup-demo.ps1"
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Error "Frontend sem node_modules. Rode: .\scripts\setup-demo.ps1"
}

# Libera porta se processo antigo ficou preso
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $existing) {
    if ($pid -and $pid -ne 0) {
        Write-Host "Encerrando processo na porta $Port (PID $pid)..." -ForegroundColor Yellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

Write-Host "=== Iniciando demo ===" -ForegroundColor Cyan
Write-Host "Backend  -> http://127.0.0.1:$Port/docs" -ForegroundColor Green
Write-Host "Frontend -> http://localhost:5173" -ForegroundColor Green
Write-Host "Login demo: admin@latam.com (sem senha)" -ForegroundColor Green
Write-Host ""

$backendCmd = @"
Set-Location '$Backend'
`$host.UI.RawUI.WindowTitle = 'LATAM Demo — Backend (:$Port)'
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port $Port
"@

$frontendCmd = @"
Set-Location '$Frontend'
`$host.UI.RawUI.WindowTitle = 'LATAM Demo — Frontend (:5173)'
`$env:VITE_API_TARGET = 'http://127.0.0.1:$Port'
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host "Duas janelas foram abertas. Aguarde ~10s e acesse http://localhost:5173" -ForegroundColor Cyan
