<#
Start the app on one address (Windows PowerShell). Run .\setup.ps1 once before.

    .\start.ps1             build the UI if it isn't built yet, then serve everything
    .\start.ps1 -Rebuild    rebuild the UI first (after changing frontend code)
    .\start.ps1 -Demo       load the demo plan first (only into an empty database)

UI: http://127.0.0.1:8000    API docs: http://127.0.0.1:8000/api/docs    Stop: Ctrl+C
For development with hot reload, see the README (Vite dev server + uvicorn --reload).
#>
param([switch]$Rebuild, [switch]$Demo, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No Python environment yet: run .\setup.ps1 first." }

if ($Rebuild -or -not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Host "== Building the UI" -ForegroundColor Cyan
    npm --prefix "$root\frontend" run build
    if ($LASTEXITCODE) { throw "The UI build failed (exit code $LASTEXITCODE)." }
}

Push-Location (Join-Path $root "backend")
try {
    if ($Demo) {
        Write-Host "== Loading the demo plan" -ForegroundColor Cyan
        & $python -m app.seed
        # Exit code 1 means the database already holds a plan: keep it and carry on.
        if ($LASTEXITCODE -gt 1) { throw "Loading the demo plan failed (exit code $LASTEXITCODE)." }
    }
    Write-Host "`n== Goal Simulator: http://127.0.0.1:$Port   (API docs: /api/docs, stop: Ctrl+C)`n" -ForegroundColor Green
    & $python -m uvicorn app.serve:create_site --factory --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
