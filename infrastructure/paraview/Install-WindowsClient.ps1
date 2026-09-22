[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $Archive,
    [Parameter(Mandatory)][string] $Destination,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$release = Get-Content (Join-Path $PSScriptRoot 'release.json') -Raw | ConvertFrom-Json
$source = (Resolve-Path -LiteralPath $Archive).Path
$target = [IO.Path]::GetFullPath($Destination)
if (-not $target.StartsWith('D:\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Use a dedicated directory on D:.' }
if (Test-Path -LiteralPath $target) { throw 'Destination exists; choose a new directory.' }
if ((Get-FileHash -LiteralPath $source -Algorithm MD5).Hash.ToLowerInvariant() -ne $release.windows_published_md5) {
    throw 'Archive differs from the published release checksum.'
}
$prefix = "ParaView-$($release.version)-Windows-Python3.12-msvc2017-AMD64/"
$zip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    # Validate every destination before creating anything.
    foreach ($entry in $zip.Entries) {
        if (-not $entry.FullName.StartsWith($prefix, [StringComparison]::Ordinal)) { throw 'Unexpected archive root.' }
        $relative = $entry.FullName.Substring($prefix.Length)
        if (-not $relative) { continue }
        $path = [IO.Path]::GetFullPath((Join-Path $target $relative))
        if (-not $path.StartsWith($target + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive traversal rejected.' }
    }
    [pscustomobject]@{version=$release.version; destination=$target; entries=$zip.Entries.Count; apply=[bool]$Apply} | ConvertTo-Json
    if (-not $Apply) { return }
    [IO.Directory]::CreateDirectory($target) | Out-Null
    foreach ($entry in $zip.Entries) {
        $relative = $entry.FullName.Substring($prefix.Length)
        if (-not $relative) { continue }
        $path = [IO.Path]::GetFullPath((Join-Path $target $relative))
        if ($entry.FullName.EndsWith('/')) { [IO.Directory]::CreateDirectory($path) | Out-Null; continue }
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $path, $false)
    }
} finally { $zip.Dispose() }
