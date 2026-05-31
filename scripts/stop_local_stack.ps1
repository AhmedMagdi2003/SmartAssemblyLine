# scripts/stop_local_stack.ps1

$ErrorActionPreference = "Stop"

# Setup Paths
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$ComposeFile = "$ProjectRoot\deployment\docker-compose.local.yml"
$RuntimeDir = "$ProjectRoot\data\runtime"
$PidDir = "$RuntimeDir\pids"

# Function to stop background service by PID file
function Stop-BackgroundService {
    param($name)
    $pidFile = "$PidDir\$name.pid"

    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile
        if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
            Write-Host "Stopping $name (PID $pid)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "$name PID $pid is not running." -ForegroundColor Gray
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "$name is not running (no PID file found)." -ForegroundColor Gray
    }
}

# Stop the logger and dashboard services
Stop-BackgroundService -name "logger"
Stop-BackgroundService -name "dashboard"

# Stop the Docker infrastructure
if (Test-Path $ComposeFile) {
    Write-Host "Stopping Docker infrastructure..." -ForegroundColor Yellow
    docker compose -f $ComposeFile down
}

Write-Host "Local stack stopped." -ForegroundColor Green
