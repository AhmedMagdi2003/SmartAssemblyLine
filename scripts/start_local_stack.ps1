# scripts/start_local_stack.ps1

param (
    [string]$CondaEnv = "torch_win",
    [switch]$NoInfra,
    [switch]$NoLogger,
    [switch]$NoDashboard,
    [switch]$NoPipeline
)

$ErrorActionPreference = "Stop"

# Setup Paths
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$ComposeFile = "$ProjectRoot\deployment\docker-compose.local.yml"
$RuntimeDir = "$ProjectRoot\data\runtime"
$PidDir = "$RuntimeDir\pids"
$LogDir = "$RuntimeDir\logs"

# Create directories if they don't exist
if (-not (Test-Path $PidDir)) { New-Item -ItemType Directory -Force -Path $PidDir | Out-Null }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

Set-Location $ProjectRoot

Write-Host "Project root: $ProjectRoot"
Write-Host "Assuming active Conda environment: $CondaEnv"

# --- INFRASTRUCTURE (Docker + DB) ---
if (-not $NoInfra) {
    Write-Host "Starting PostgreSQL and Mosquitto with Docker Compose..."
    docker compose -f $ComposeFile up -d

    Write-Host "Waiting for PostgreSQL..."
    $deadline = (Get-Date).AddSeconds(90)
    $dbReady = $false
    while ((Get-Date) -lt $deadline) {
        $status = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' smart-assembly-db 2>$null
        if ($status -match "healthy|running") { $dbReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $dbReady) { Write-Error "Timed out waiting for DB."; exit 1 }

    Write-Host "Waiting for MQTT broker..."
    $deadline = (Get-Date).AddSeconds(30)
    $mqttReady = $false
    while ((Get-Date) -lt $deadline) {
        $status = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' smart-assembly-mqtt 2>$null
        if ($status -match "healthy|running") { $mqttReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $mqttReady) { Write-Error "Timed out waiting for MQTT."; exit 1 }

    Write-Host "Applying Alembic migrations..."
    python -m alembic upgrade head
}

# --- BACKGROUND SERVICES ---
function Start-BackgroundService {
    param($name, $argsList)
    $logFile = "$LogDir\$name.log"
    $errFile = "$LogDir\$name.err.log" # NEW: Separate file for errors
    $pidFile = "$PidDir\$name.pid"

    # Check if already running
    if (Test-Path $pidFile) {
        $existingPid = Get-Content $pidFile
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "$name is already running with PID $existingPid"
            return
        }
        Remove-Item $pidFile # Cleanup stale PID file
    }

    Write-Host "Starting $name..."
    
    # FIX: Route StandardOutput and StandardError to two different files
    $proc = Start-Process -FilePath "python" -ArgumentList $argsList -RedirectStandardOutput $logFile -RedirectStandardError $errFile -WindowStyle Hidden -PassThru
    $proc.Id | Out-File -FilePath $pidFile -Encoding ASCII
    
    Start-Sleep -Seconds 1
    if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
        Write-Error "$name failed to stay running. Check the error log: $errFile"
        exit 1
    }
    
    Write-Host "$name started with PID $($proc.Id)"
    Write-Host "Logs: $logFile (Output) | $errFile (Errors)"
}

if (-not $NoLogger) {
    Start-BackgroundService -name "logger" -argsList @("-u", "src\utils\logger.py")
}

if (-not $NoDashboard) {
    Start-BackgroundService -name "dashboard" -argsList @("-u", "-m", "uvicorn", "src.dashboard.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload")
}

# --- SUMMARY ---
Write-Host "`nLocal stack is starting." -ForegroundColor Green
Write-Host "Dashboard: http://127.0.0.1:8000"
Write-Host "PostgreSQL: localhost:5433"
Write-Host "MQTT Broker: localhost:1883"
Write-Host "Logs directory: $LogDir`n"

# --- PIPELINE ---
if (-not $NoPipeline) {
    Write-Host "Starting vision pipeline in the current terminal..." -ForegroundColor Cyan
    python scripts\run_pipeline.py
} else {
    Write-Host "Pipeline not started because -NoPipeline was used."
}