param([switch]$Check, [string]$Profile = '', [string]$Bind = '127.0.0.1', [int]$Port = 8766)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $Profile) { $Profile = Join-Path $projectRoot 'config/live.local.json' }
$env:PYTHONDONTWRITEBYTECODE = '1'
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    $arguments = @('-m', 'guanlan.live', '--profile', $Profile, '--bind', $Bind, '--port', $Port)
    if ($Check) { $arguments += '--check' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Guanlan live case exited with code $LASTEXITCODE" }
} finally { $env:PYTHONPATH = $previousPythonPath }
