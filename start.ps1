#!/usr/bin/env pwsh
# InvoiceFactoringGuard — One-command startup script
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  InvoiceFactoringGuard — Starting Up" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# --- Backend ---
Write-Host ""
Write-Host "[1/2] Starting FastAPI backend on port 8000..." -ForegroundColor Yellow

$backendDir = Join-Path $ProjectRoot "backend"

# Check if .env exists, create from example if not
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $envFile
    Write-Host "    Created .env from .env.example" -ForegroundColor Gray
}

# Use the project's Python environment and invoke Uvicorn as a module. This avoids
# launching the separately blocked uvicorn.exe shim on managed Windows systems.
Push-Location $backendDir
$pythonExe = Join-Path $backendDir '.venv311\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
}
if (-not (Test-Path $pythonExe)) {
    Write-Host '    Creating Python 3.11 virtual environment...' -ForegroundColor Gray
    py -3.11 -m venv (Join-Path $backendDir '.venv311')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required to create backend/.venv311.' }
    $pythonExe = Join-Path $backendDir '.venv311\Scripts\python.exe'
}
if (-not (Test-Path $pythonExe)) { throw 'No backend Python environment was found.' }
& $pythonExe -m uvicorn --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '    Installing backend dependencies into the project environment...' -ForegroundColor Gray
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
$backendListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($backendListener) { throw ('Port 8000 is already in use by PID ' + $backendListener.OwningProcess + '. Stop the old backend first.') }
$backend = Start-Process -FilePath $pythonExe `
    -ArgumentList '-m uvicorn main:app --reload --host 127.0.0.1 --port 8000' `
    -WorkingDirectory $backendDir `
    -PassThru -WindowStyle Minimized
Pop-Location

Write-Host "    Backend PID: $($backend.Id)" -ForegroundColor Green
Write-Host "    API Docs: http://localhost:8000/api/docs" -ForegroundColor Gray

Start-Sleep -Seconds 2

# --- Frontend ---
Write-Host ""
Write-Host "[2/2] Starting React frontend on port 5173..." -ForegroundColor Yellow

$frontendDir = Join-Path $ProjectRoot "frontend"
Push-Location $frontendDir

$frontendListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($frontendListener) { throw ('Port 5173 is already in use by PID ' + $frontendListener.OwningProcess + '. Stop the old frontend first.') }

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "    Installing npm packages..." -ForegroundColor Gray
    npm install --silent
}

$frontend = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $frontendDir `
    -PassThru -WindowStyle Minimized
Pop-Location

Write-Host "    Frontend PID: $($frontend.Id)" -ForegroundColor Green
Write-Host "    App: http://localhost:5173" -ForegroundColor Gray

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  READY! Open http://localhost:5173" -ForegroundColor Green
Write-Host "  Demo invoice: INV-2026-02970" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host 'Press Ctrl+C to stop.' -ForegroundColor Gray

# Keep script alive
try { while ($true) { Start-Sleep -Seconds 10 } }
finally {
    Write-Host 'Stopping...' -ForegroundColor Yellow
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
}
