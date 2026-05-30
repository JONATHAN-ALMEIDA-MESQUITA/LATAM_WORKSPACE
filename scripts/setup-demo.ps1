# Setup inicial apos clonar o repo (Windows / PowerShell).
# Uso (na raiz do projeto, terminal VS Code):
#   .\scripts\setup-demo.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

function Require-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "Comando '$name' nao encontrado. Instale antes de continuar."
    }
}

Write-Host "=== LATAM Analytics Platform — Setup Demo ===" -ForegroundColor Cyan
Require-Command python
Require-Command npm

$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $pyVer"
if ([version]$pyVer -lt [version]"3.11") {
    Write-Warning "Recomendado Python 3.11+. Versao atual pode funcionar, mas nao e garantido."
}

Set-Location $Backend
if (-not (Test-Path ".venv")) {
    Write-Host "Criando virtualenv..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "Instalando dependencias Python..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

Set-Location $Root
& (Join-Path $Root "scripts\seed-all.ps1")

Set-Location $Frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "Instalando dependencias Node (npm install)..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "node_modules ja existe — pulando npm install." -ForegroundColor DarkGray
}

if (-not (Test-Path ".env.local")) {
    @"
VITE_API_TARGET=http://127.0.0.1:8001
"@ | Set-Content -Path ".env.local" -Encoding UTF8
    Write-Host "Criado frontend/.env.local" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Setup concluido ===" -ForegroundColor Green
Write-Host "Proximo passo: .\scripts\start-demo.ps1" -ForegroundColor Cyan
Write-Host "App: http://localhost:5173  |  API: http://127.0.0.1:8001/docs" -ForegroundColor Cyan
