$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONDONTWRITEBYTECODE = '1'
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    & python -m unittest discover -s (Join-Path $projectRoot 'tests') -v
    if ($LASTEXITCODE -ne 0) { throw 'Guanlan verification failed' }
    & python -m guanlan check --recipes (Join-Path $projectRoot 'examples/recipes')
    if ($LASTEXITCODE -ne 0) { throw 'Recipe validation failed' }
    if (Get-Command node -ErrorAction SilentlyContinue) {
        & node --check (Join-Path $projectRoot 'src/guanlan/delivery/app.js')
        if ($LASTEXITCODE -ne 0) { throw 'Browser JavaScript syntax check failed' }
        & node --check (Join-Path $projectRoot 'src/guanlan/liveweb/app.js')
        if ($LASTEXITCODE -ne 0) { throw 'Live case JavaScript syntax check failed' }
        & node --check (Join-Path $projectRoot 'src/guanlan/media/viewer.js')
        if ($LASTEXITCODE -ne 0) { throw 'Media JavaScript syntax check failed' }
        & node (Join-Path $projectRoot 'viewer/check-media.mjs')
        if ($LASTEXITCODE -ne 0) { throw 'Media control logic check failed' }
        Get-ChildItem (Join-Path $projectRoot 'src/guanlan/portable') -Filter '*.js' | ForEach-Object {
            Get-Content -Raw $_.FullName | & node --input-type=module --check
            if ($LASTEXITCODE -ne 0) { throw "Portable JavaScript syntax check failed: $($_.Name)" }
        }
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
