$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Join-Path $PSScriptRoot "..")

docker compose run --rm backup
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo crear el respaldo."
}
