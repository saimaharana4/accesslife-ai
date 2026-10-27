[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('preflight', 'up', 'fixture', 'health', 'migrate', 'test', 'persistence', 'down', 'logs')]
    [string]$Action = 'up',
    [switch]$UseProviders
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repo
$baseFile = Join-Path $repo 'compose.yaml'
$providerFile = Join-Path $repo 'compose.tasteduel.providers.yml'
$nonsecretEnv = Join-Path $repo 'compose.tasteduel.env'
$ports = if ($Action -eq 'fixture') { @(13002) } else { @(55436, 18005, 13001) }

function Invoke-Docker([string[]]$Arguments, [switch]$Quiet) {
    if ($Quiet) { & docker @Arguments *> $null }
    else { & docker @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed ($($Arguments -join ' ')). No volume was removed." }
}

function Get-ComposeArguments {
        $compose = @('compose', '--project-name', 'taste-duel', '--env-file', $nonsecretEnv, '-f', $baseFile)
    if ($UseProviders) { $compose += @('-f', $providerFile) }
    return ,$compose
}

function Assert-Configuration([switch]$CheckPorts) {
    if (-not (Test-Path -LiteralPath $baseFile) -or -not (Test-Path -LiteralPath $nonsecretEnv)) {
        throw 'The maintained Compose file or nonsecret local configuration is missing.'
    }
    if ($UseProviders) {
        $candidate = $env:TASTEDUEL_ADC_PATH
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            $candidate = Join-Path $env:APPDATA 'gcloud/application_default_credentials.json'
        }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            Write-Warning 'ADC is unavailable. Optional Qloo and Vertex providers stay disabled; using provider-free local mode.'
            $script:UseProviders = $false
        } else {
            $env:TASTEDUEL_ADC_PATH = (Resolve-Path -LiteralPath $candidate).Path
            Write-Host 'ADC file exists and will be mounted read-only. Its contents were not read.'
        }
    }
    if ($CheckPorts) {
        foreach ($port in $ports) {
            $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
            if ($listeners) {
                throw "Port $port is already in use. Stop the owning app yourself, then rerun; this script will not stop unrelated services."
            }
        }
    }
    Invoke-Docker -Arguments @('info') -Quiet
    $compose = Get-ComposeArguments
    Invoke-Docker -Arguments ($compose + @('config', '--quiet')) -Quiet
}

function Assert-DatabaseAndMigrations {
    $compose = Get-ComposeArguments
    Invoke-Docker -Arguments ($compose + @('exec', '-T', 'database', 'pg_isready', '-U', 'tasteduel_admin', '-d', 'tasteduel_prompt5')) -Quiet
    $revision = & docker @($compose + @('run', '--rm', 'migrate', 'alembic', '-c', 'apps/api/tasteduel-alembic.ini', 'current'))
    if ($LASTEXITCODE -ne 0 -or ($revision -join "`n") -notmatch '\btd0010\b') {
        throw 'Taste Duel database is not at the expected td0010 migration head. Run the explicit migrate action; no volume was changed.'
    }
    Write-Host 'Taste Duel database is ready at migration td0010.'
}

if ($Action -in @('preflight', 'up', 'fixture', 'migrate', 'health', 'test', 'persistence')) {
    try { Assert-Configuration }
    catch {
        if ($_.Exception.Message -notmatch 'Docker command failed') { throw }
        Write-Host 'Docker Engine is not ready; asking Docker Desktop to start.'
        & docker desktop start --timeout 60 *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and rerun. No database volume was changed.' }
        Assert-Configuration
    }
}

if ($Action -in @('preflight', 'fixture')) { Assert-Configuration -CheckPorts }

$composeArgs = Get-ComposeArguments
switch ($Action) {
    preflight {
        Write-Host 'Taste Duel Compose configuration is valid. Dedicated ports 55436, 18005 and 13001 are free.'
    }
    up {
        Invoke-Docker -Arguments ($composeArgs + @('up', '--build', '--detach', '--wait'))
        Assert-DatabaseAndMigrations
        Write-Host 'Taste Duel is starting. Run: .\scripts\tasteduel-compose.ps1 health'
        Write-Host 'Web: http://127.0.0.1:13001 | API health: http://127.0.0.1:18005/v1/health/ready'
        Write-Host 'Local database credentials are fixed demo-only values. Never reuse them outside this isolated local stack.'
    }
    fixture {
        Invoke-Docker -Arguments ($composeArgs + @('--profile', 'fixture', 'up', '--build', '-d', 'fixture-demo'))
        Write-Host 'Synthetic in-memory DEVELOPMENT FIXTURE: http://127.0.0.1:13002'
        Write-Host 'No Qloo ranking or API persistence is used by this fixture profile.'
    }
    migrate {
        Invoke-Docker -Arguments ($composeArgs + @('run', '--rm', 'migrate'))
        Assert-DatabaseAndMigrations
        Write-Host 'Migrations completed. Existing data volume was retained.'
    }
    health {
        foreach ($uri in @('http://127.0.0.1:18005/v1/health/ready', 'http://127.0.0.1:13001/')) {
            try {
                $response = Invoke-WebRequest -Uri $uri -TimeoutSec 5 -UseBasicParsing
                Write-Host "$uri -> $([int]$response.StatusCode)"
            } catch { throw "Health check failed for $uri. Inspect logs with: .\scripts\tasteduel-compose.ps1 logs" }
        }
        Assert-DatabaseAndMigrations
    }
    test {
        Invoke-Docker -Arguments ($composeArgs + @('ps'))
        Assert-DatabaseAndMigrations
        $names = @('TASTEDUEL_CONTAINER_MODE', 'TASTEDUEL_TEST_DATABASE_URL', 'TASTEDUEL_TEST_MIGRATION_DATABASE_URL', 'PYTHONPATH')
        $saved = @{}
        foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
        try {
            $env:TASTEDUEL_CONTAINER_MODE = 'true'
            $env:TASTEDUEL_TEST_DATABASE_URL = 'postgresql+psycopg://tasteduel_runtime:local_only_tasteduel_runtime@127.0.0.1:55436/tasteduel_prompt5'
            $env:TASTEDUEL_TEST_MIGRATION_DATABASE_URL = 'postgresql+psycopg://tasteduel_migrator:local_only_tasteduel_migrator@127.0.0.1:55436/tasteduel_prompt5'
            $env:PYTHONPATH = "$repo;$(Join-Path $repo 'apps/api/src')"
            corepack pnpm test:web-contracts
            if ($LASTEXITCODE -ne 0) { throw 'Frontend contract tests failed.' }
            uv run --no-sync python -m pytest -c pytest.tasteduel.ini --confcutdir=tests/tasteduel tests/tasteduel -q
            if ($LASTEXITCODE -ne 0) { throw 'Taste Duel tests against the Compose database failed.' }
        } finally {
            foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
        }
    }
    persistence {
        Invoke-Docker -Arguments ($composeArgs + @('exec', '-T', 'database', 'pg_isready', '-U', 'tasteduel_admin', '-d', 'tasteduel_prompt5')) -Quiet
        $artifactRoot = Join-Path $repo '.data/tasteduel-prompt14'
        New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
        $stateFile = Join-Path $artifactRoot 'persistence-state.json'
        $reportFile = Join-Path $artifactRoot 'container-persistence-verification.json'
        $names = @('TASTEDUEL_CONTAINER_MODE', 'TASTEDUEL_TEST_DATABASE_URL', 'TASTEDUEL_TEST_MIGRATION_DATABASE_URL', 'TASTEDUEL_PERSISTENCE_STATE_FILE')
        $saved = @{}
        foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
        try {
            $env:TASTEDUEL_CONTAINER_MODE = 'true'
            $env:TASTEDUEL_TEST_DATABASE_URL = 'postgresql+psycopg://tasteduel_runtime:local_only_tasteduel_runtime@127.0.0.1:55436/tasteduel_prompt5'
            $env:TASTEDUEL_TEST_MIGRATION_DATABASE_URL = 'postgresql+psycopg://tasteduel_migrator:local_only_tasteduel_migrator@127.0.0.1:55436/tasteduel_prompt5'
            $env:TASTEDUEL_PERSISTENCE_STATE_FILE = $stateFile
            uv run --no-sync python -m pytest -c pytest.tasteduel.ini --confcutdir=tests/tasteduel tests/tasteduel/gameplay/test_compose_restart_persistence.py -q
            if ($LASTEXITCODE -ne 0) { throw 'Synthetic game/challenge preparation against the Compose database failed.' }
            Invoke-Docker -Arguments ($composeArgs + @('restart', 'api'))
            $ready = $false
            for ($attempt = 0; $attempt -lt 30; $attempt++) {
                try {
                    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:18005/v1/health/ready' -TimeoutSec 3 -UseBasicParsing
                    if ($response.StatusCode -eq 200) { $ready = $true; break }
                } catch { }
                Start-Sleep -Seconds 1
            }
            if (-not $ready) { throw 'The restarted Taste Duel API did not become ready.' }
            uv run --no-sync python scripts/tasteduel-compose-persistence-verify.py
            if ($LASTEXITCODE -ne 0) { throw 'The restarted API did not return the saved game/challenge/fixed replay.' }
            $report = [ordered]@{
                checked_at_utc = [DateTime]::UtcNow.ToString('o')
                compose_project = 'taste-duel'
                migrated_database = 'tasteduel_prompt5'
                api_restarted = $true
                creator_result_retained = $true
                public_invitation_retained = $true
                fixed_replay_started_with_same_first_round = $true
                provider_calls = 0
                state_file_removed_after_check = $true
            }
            $report | ConvertTo-Json | Set-Content -LiteralPath $reportFile -Encoding utf8
            Remove-Item -LiteralPath $stateFile -Force
            Write-Host 'Synthetic game/challenge persistence passed across API container restart. Opaque session/slug test state was removed.'
        } finally {
            if (Test-Path -LiteralPath $stateFile) { Remove-Item -LiteralPath $stateFile -Force }
            foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
        }
    }
    down {
        # Explicit project and file; no -v/--volumes, so application data remains.
        Invoke-Docker -Arguments ($composeArgs + @('--profile', 'fixture', 'down'))
        Write-Host 'Taste Duel containers stopped. The taste-duel-data volume remains. No other Compose project was targeted.'
    }
    logs { Invoke-Docker -Arguments ($composeArgs + @('logs', '--tail', '100')) }
}
