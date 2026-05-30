# Popula o banco SQLite e todos os dados demo (idempotente na maioria dos seeds).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
Set-Location $Backend

$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtualenv nao encontrado. Rode primeiro: scripts\setup-demo.ps1"
}

$seeds = @(
    "seed.py",
    "seed_dashboards.py",
    "seed_pipelines.py",
    "seed_forecasts.py",
    "seed_alerts.py",
    "seed_scheduled_jobs.py",
    "seed_report_tables.py",
    "seed_reports.py",
    "seed_audit_logs.py",
    "seed_phase9.py"
)

Write-Host "=== Executando seeds ===" -ForegroundColor Cyan
foreach ($s in $seeds) {
    Write-Host ">> $s" -ForegroundColor Yellow
    & $Python $s
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Host "=== Seeds concluidos ===" -ForegroundColor Green
