param(
    [string]$EnvFile = "deployment/cloud/env/dashboard-tunnel.env",
    [string]$DashboardHost = "127.0.0.1",
    [int]$DashboardPort = 8000,
    [string]$Token = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ResolvedEnvFile = Join-Path $ProjectRoot $EnvFile

if (Test-Path $ResolvedEnvFile) {
    Get-Content $ResolvedEnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
        }
    }

    if ($env:DASHBOARD_HOST) { $DashboardHost = $env:DASHBOARD_HOST }
    if ($env:DASHBOARD_PORT) { $DashboardPort = [int]$env:DASHBOARD_PORT }
    if (-not $Token -and $env:CLOUDFLARE_TUNNEL_TOKEN) { $Token = $env:CLOUDFLARE_TUNNEL_TOKEN }
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared was not found in PATH. Install it first, then rerun this command."
}

$localUrl = "http://$DashboardHost`:$DashboardPort"
Write-Host "Starting dashboard tunnel for $localUrl"

if ($Token) {
    Write-Host "Mode: named tunnel"
    & cloudflared tunnel run --token $Token
    exit $LASTEXITCODE
}

Write-Host "Mode: quick tunnel"
Write-Host "Cloudflare will print a temporary trycloudflare.com URL below."
& cloudflared tunnel --url $localUrl
exit $LASTEXITCODE
