param([switch]$Check, [ValidateRange(1, 65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONDONTWRITEBYTECODE = '1'
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    $command = if ($Check) { 'check' } else { 'demo' }
    & python -m guanlan $command --recipes (Join-Path $projectRoot 'examples/recipes') --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Guanlan exited with code $LASTEXITCODE" }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
