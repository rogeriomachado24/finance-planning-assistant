<#
First-time setup (Windows PowerShell): Python environment, backend and frontend packages.
Needs Python 3.12+ and Node.js 20+ on PATH. Safe to run again.

    .\setup.ps1
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# PowerShell 5.1 doesn't stop on a failing external command, so check each exit code.
function Invoke-Step([string]$Label, [scriptblock]$Command) {
    Write-Host "`n== $Label" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE) { throw "$Label failed (exit code $LASTEXITCODE)" }
}

$venv = Join-Path $root "backend\.venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
    Invoke-Step "Create the Python environment (backend\.venv)" { python -m venv $venv }
}
Invoke-Step "Install backend packages" { & $python -m pip install --quiet -e "$root\backend[dev]" }
Invoke-Step "Install frontend packages" { npm --prefix "$root\frontend" ci --no-audit --no-fund }

$envFile = Join-Path $root "backend\.env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root "backend\.env.example") $envFile
    Write-Host "`nCreated backend\.env from .env.example (chat: Ollama with rules as fallback)."
}

Write-Host "`nReady. Start the app with .\start.ps1 (add -Demo to load a sample plan)." -ForegroundColor Green
Write-Host "Optional, for the chat's language model: install Ollama, then 'ollama pull qwen2.5:3b'."
