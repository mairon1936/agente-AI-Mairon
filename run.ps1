$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & $uv.Source run main.py
    exit $LASTEXITCODE
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "No se encontró uv ni el entorno .venv. Instala uv y ejecuta 'uv sync' en la carpeta del proyecto."
    exit 1
}

& $python main.py
exit $LASTEXITCODE
