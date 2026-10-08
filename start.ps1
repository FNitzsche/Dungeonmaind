# Start Dungeon M-AI-nd locally (backend + frontend).
# Prerequisites: Python venv at .venv, frontend deps installed, ffmpeg on PATH.
# Ollama should already be running (`ollama serve`) with the model pulled.

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path '.\.venv\Scripts\Activate.ps1')) {
    Write-Error "Missing .venv. Run: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r backend\requirements.txt"
}

if (-not (Test-Path '.\backend\.env')) {
    Copy-Item '.\backend\.env.example' '.\backend\.env'
    Write-Host 'Created backend\.env from .env.example — edit tokens if needed.'
}

if (-not (Test-Path '.\frontend\node_modules')) {
    Write-Host 'Installing frontend dependencies...'
    Push-Location '.\frontend'
    npm install
    Pop-Location
}

Write-Host 'Starting backend on http://localhost:8000 ...'
$backend = Start-Process -PassThru -NoNewWindow -FilePath '.\.venv\Scripts\python.exe' -ArgumentList @(
    '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'
) -WorkingDirectory (Join-Path $Root 'backend')

Write-Host 'Starting frontend on http://localhost:5173 ...'
$frontend = Start-Process -PassThru -NoNewWindow -FilePath 'npm' -ArgumentList @(
    'run', 'dev', '--', '--host', '0.0.0.0'
) -WorkingDirectory (Join-Path $Root 'frontend')

Write-Host ''
Write-Host 'Dungeon M-AI-nd is starting.'
Write-Host '  Frontend: http://localhost:5173'
Write-Host '  Backend:  http://localhost:8000'
Write-Host '  Ensure Ollama is running: ollama serve'
Write-Host 'Press Ctrl+C to stop both services.'

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    foreach ($proc in @($backend, $frontend)) {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
