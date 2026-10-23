$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No encuentro el entorno virtual. Créalo con: python -m venv .venv; luego instala requirements.txt."
}

& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
