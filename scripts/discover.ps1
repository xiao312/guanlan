param([Parameter(Mandatory)][string]$Profile, [switch]$Execute)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $Profile -Raw | ConvertFrom-Json
$expected = @('schema_version', 'ssh_alias', 'job_ids')
$actual = @($config.PSObject.Properties.Name)
if (@(Compare-Object $expected $actual).Count -ne 0 -or $config.schema_version -cne 1) {
    throw 'Profile requires exactly schema_version: 1, ssh_alias, and job_ids.'
}
if ($config.ssh_alias -isnot [string] -or $config.ssh_alias -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') {
    throw 'ssh_alias must be a simple existing SSH config alias, not a command or URL.'
}
if ($config.job_ids -isnot [array] -or $config.job_ids.Count -lt 1 -or $config.job_ids.Count -gt 20) {
    throw 'job_ids must contain between 1 and 20 positive integer job IDs.'
}
foreach ($jobId in $config.job_ids) {
    if (($jobId -isnot [long] -and $jobId -isnot [int]) -or $jobId -le 0) {
        throw 'Every job ID must be a positive integer.'
    }
}
$jobList = $config.job_ids -join ','
$commands = @(
    "squeue -j $jobList -o '%.18i %.12T %.40j'",
    "sacct -j $jobList --format=JobID,JobName,State,WorkDir%160 -P -n"
)
if (-not $Execute) {
    [ordered]@{mode='read-only-plan'; ssh_alias=$config.ssh_alias; commands=$commands} | ConvertTo-Json
    return
}
foreach ($remoteCommand in $commands) {
    & ssh -o BatchMode=yes -o ConnectTimeout=15 $config.ssh_alias $remoteCommand
    if ($LASTEXITCODE -ne 0) { throw 'Read-only discovery failed. Check SSH access and Slurm availability.' }
}
