param(
    [switch]$NoPipeline,
    [switch]$NoDashboard,
    [switch]$NoLogger,
    [switch]$NoInfra
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "deployment\docker-compose.local.yml"

function Invoke-InProject([string]$Command) {
    Push-Location $projectRoot
    try {
        Invoke-Expression $Command
    }
    finally {
        Pop-Location
    }
}

function Start-ServiceWindow([string]$Title, [string]$Command) {
    $windowCommand = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location '$projectRoot'
$Command
"@

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $windowCommand
    ) | Out-Null
}

function Wait-ForDockerService([string]$ContainerName, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $ContainerName 2>$null
        if ($LASTEXITCODE -eq 0 -and ($status -eq "healthy" -or $status -eq "running")) {
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "Timed out waiting for container '$ContainerName'."
}

Write-Host "Project root: $projectRoot"

if (-not $NoInfra) {
    Write-Host "Starting PostgreSQL and Mosquitto with Docker Compose..."
    Invoke-InProject "docker compose -f `"$composeFile`" up -d"

    Write-Host "Waiting for PostgreSQL..."
    Wait-ForDockerService -ContainerName "smart-assembly-db" -TimeoutSeconds 90

    Write-Host "Waiting for MQTT broker..."
    Wait-ForDockerService -ContainerName "smart-assembly-mqtt" -TimeoutSeconds 30

    Write-Host "Applying Alembic migrations..."
    Invoke-InProject "python -m alembic upgrade head"
}

if (-not $NoLogger) {
    Write-Host "Starting logger window..."
    Start-ServiceWindow -Title "Smart Assembly Logger" -Command "python src/utils/logger.py"
}

if (-not $NoDashboard) {
    Write-Host "Starting dashboard window..."
    Start-ServiceWindow -Title "Smart Assembly Dashboard" -Command "python -m uvicorn src.dashboard.main:app --host 0.0.0.0 --port 8000 --reload"
}

if (-not $NoPipeline) {
    Write-Host "Starting vision pipeline window..."
    Start-ServiceWindow -Title "Smart Assembly Pipeline" -Command "python scripts/run_pipeline.py"
}

Write-Host ""
Write-Host "Local stack is starting."
Write-Host "Dashboard: http://127.0.0.1:8000"
Write-Host "PostgreSQL: localhost:5433"
Write-Host "MQTT Broker: localhost:1883"
Write-Host ""
Write-Host "Optional flags:"
Write-Host "  -NoInfra      Skip docker compose + migrations"
Write-Host "  -NoLogger     Do not open the logger window"
Write-Host "  -NoDashboard  Do not open the dashboard window"
Write-Host "  -NoPipeline   Do not open the pipeline window"
