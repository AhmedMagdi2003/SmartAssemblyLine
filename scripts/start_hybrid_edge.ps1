param(
    [string]$EnvFile = "deployment/cloud/env/edge-hybrid.env",
    [string]$CondaEnv = $(if ($env:SMART_ASSEMBLY_CONDA_ENV) { $env:SMART_ASSEMBLY_CONDA_ENV } else { "torch" })
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ResolvedEnvFile = Join-Path $ProjectRoot $EnvFile

if (-not (Test-Path $ResolvedEnvFile)) {
    Write-Error "Hybrid edge env file not found: $ResolvedEnvFile"
    Write-Host "Create it from deployment/cloud/env/edge-hybrid.env.example first."
    exit 1
}

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

Write-Host "Running Smart Assembly Line hybrid edge mode"
Write-Host "Project root: $ProjectRoot"
Write-Host "Publishing to MQTT broker: $env:MQTT_HOST`:$env:MQTT_PORT"
Write-Host "Topic: $env:MQTT_TOPIC"

Push-Location $ProjectRoot
try {
    & conda run -n $CondaEnv python scripts/run_pipeline.py
}
finally {
    Pop-Location
}
