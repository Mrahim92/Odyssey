$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$env:PYTHONPATH = "src"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
    .\.venv\Scripts\python -m playwright install chromium
}

.\.venv\Scripts\python -m odyssey_bot run
