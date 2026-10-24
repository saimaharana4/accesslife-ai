param([switch]$Stop)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Stop) { docker compose down; exit $LASTEXITCODE }
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    docker desktop start --timeout 60
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop, wait for its engine, then rerun this script.' }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
New-Item -ItemType Directory -Force -Path '.data/credentials' | Out-Null
$accesslifeAdc = Join-Path $env:APPDATA 'gcloud/application_default_credentials.json'
if (Test-Path -LiteralPath $accesslifeAdc) {
    $env:GCP_ADC_DIRECTORY = Split-Path $accesslifeAdc -Parent
} else { Write-Warning 'ADC is missing. Use gcloud auth application-default login for Vertex; deterministic planning still works.' }
foreach ($accesslifePort in @(3000,8000,5432)) {
    $accesslifeListener = Get-NetTCPConnection -State Listen -LocalPort $accesslifePort -ErrorAction SilentlyContinue
    if ($accesslifeListener) { Write-Host "Port $accesslifePort already has a listener; Compose will verify whether it belongs to this application." }
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid.' }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Startup failed; inspect docker compose logs.' }
Write-Host 'App: http://localhost:3000 | API: http://localhost:8000/docs'
Write-Host 'Optional guidance index: docker compose --profile tools run --rm ingest'
Write-Host 'Stop: docker compose down (keeps data). Do not add -v unless you intend to erase local data.'
