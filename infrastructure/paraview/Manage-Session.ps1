param(
    [ValidateSet('Check', 'Start', 'Connect', 'Open', 'Status', 'Stop')]
    [string]$Action = 'Check',
    [string]$Profile = 'config/paraview.local.json',
    [ValidateRange(5, 120)][int]$Minutes = 60,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
trap {
    if ($Json) { [Console]::Error.WriteLine((@{ok=$false; error=@{message=$_.Exception.Message}} | ConvertTo-Json -Compress -Depth 5)) }
    else { [Console]::Error.WriteLine($_.Exception.Message) }
    exit 1
}
function Result($Data) {
    if ($Json) { @{ok=$true; data=$Data} | ConvertTo-Json -Compress -Depth 8 }
    else { $Data | Format-List }
}
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not [IO.Path]::IsPathRooted($Profile)) { $Profile = Join-Path $project $Profile }
$settings = Get-Content -LiteralPath $Profile -Raw | ConvertFrom-Json
$case = Get-Content -LiteralPath (Join-Path $project $settings.case_profile) -Raw | ConvertFrom-Json
foreach ($value in @($settings.remote_runtime, $settings.image, $case.case_directory, $case.remote_workspace)) {
    if ($value -notmatch '^/[a-zA-Z0-9_./-]+$' -or $value -match '/\.\.?(/|$)') {
        throw 'Remote paths must be absolute simple paths without traversal.'
    }
}
foreach ($value in @($settings.ssh_alias, $case.partition)) {
    if ($value -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]*$') { throw 'Invalid SSH alias or partition.' }
}
if ([int]$case.cpus -lt 1 -or [int]$case.cpus -gt 16 -or [int]$case.memory_mb -lt 1024 -or [int]$case.memory_mb -gt 65536) {
    throw 'Expected 1-16 CPUs and 1024-65536 MiB.'
}
$stateDirectory = Join-Path $project 'state/paraview/session'
$stateFile = Join-Path $stateDirectory 'current.local.json'
$sshOptions = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=60')
function Remote([string]$Command) {
    $result = & ssh @sshOptions $settings.ssh_alias $Command
    if ($LASTEXITCODE -ne 0) { throw "SSH command failed (exit $LASTEXITCODE). Check connectivity; no automatic security fallback." }
    return ($result -join "`n").Trim()
}
function Save-State($State) {
    $State | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
}
function Owned-Tunnel($State) {
    if (-not $State.tunnel_pid) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($State.tunnel_pid)" -ErrorAction SilentlyContinue
    if ($process -and $process.Name -eq 'ssh.exe' -and
        $process.CommandLine.Contains('127.0.0.1:11111:127.0.0.1:11111') -and
        $process.CommandLine.Contains($State.node) -and
        $process.CommandLine.Contains($stateDirectory.Replace('\', '/'))) { return $process }
    return $null
}
if ($Action -eq 'Check') {
    [pscustomobject]@{ alias = $settings.ssh_alias; image = $settings.image;
        case = $case.case_directory; minutes = $Minutes; port = 11111;
        client_exists = Test-Path (Join-Path $settings.client_directory 'bin/paraview.exe') } | ForEach-Object { Result $_ }
    exit 0
}
$state = if (Test-Path $stateFile) { Get-Content $stateFile -Raw | ConvertFrom-Json } else { $null }
if ($state -and ($state.alias -ne $settings.ssh_alias -or $state.workspace -ne $case.remote_workspace)) {
    throw 'Saved session belongs to a different profile. Stop it using its original profile first.'
}
if ($state -and $state.job_id -notmatch '^\d+$') { throw 'Invalid saved job ID.' }
if ($Action -eq 'Start') {
    if ($state) { throw 'A session is recorded. Use Status/Connect or Stop before starting another.' }
    if (Get-NetTCPConnection -State Listen -LocalPort 11111 -ErrorAction SilentlyContinue) { throw 'Port 11111 is occupied.' }
    $null = New-Item -ItemType Directory -Path $stateDirectory -Force
    $workspace = $case.remote_workspace
    $launcher = "$($settings.remote_runtime)/scripts/run.sh"
    $null = Remote "test -f '$launcher' && test -f '$($settings.image)' && test -f '$workspace/portable-reader/case.foam'"
    $command = "sbatch --parsable --job-name=guanlan-expert --partition=$($case.partition) --nodes=1 --ntasks=1 --cpus-per-task=$($case.cpus) --mem=$($case.memory_mb)M --time=$Minutes --chdir='$workspace' --output='$workspace/expert-%j.log' --error='$workspace/expert-%j.err' --export=ALL,GUANLAN_SCRATCH_ROOT=/tmp '$launcher' server '$($settings.image)' '$($case.case_directory)' '$workspace'"
    $submitted = Remote $command
    if ($submitted -notmatch '^(\d+)(;[^\s]+)?$') { throw "Unexpected submission result: $submitted. Inspect squeue before retrying." }
    $state = [pscustomobject]@{ job_id = $Matches[1]; alias = $settings.ssh_alias;
        workspace = $workspace; node = ''; tunnel_pid = 0; minutes = $Minutes }
    Save-State $state
    Result @{job_id=$state.job_id; minutes=$Minutes; status='submitted'; next='Connect'}
    exit 0
}
if (-not $state) {
    if ($Action -in @('Connect', 'Open')) { throw 'No managed session. Run Start first.' }
    Result @{status='stopped'}; exit 0
}
$job = Remote "squeue -h -j $($state.job_id) -o '%T|%N|%j|%Z'"
if ($job -and ($job -notmatch '\|guanlan-expert\|' -or -not $job.EndsWith("|$($state.workspace)"))) {
    throw 'Job identity differs from saved session; refusing to manage it.'
}
if ($Action -eq 'Status') {
    $tunnel = Owned-Tunnel $state
    $listening = @(Get-NetTCPConnection -State Listen -LocalPort 11111 -ErrorAction SilentlyContinue |
        Where-Object { $tunnel -and $_.OwningProcess -eq $tunnel.ProcessId }).Count -gt 0
    [pscustomobject]@{ job_id = $state.job_id; scheduler = $job; tunnel_pid = $state.tunnel_pid;
        owned_listener = $listening; log = "$($state.workspace)/expert-$($state.job_id).log" } | ForEach-Object { Result $_ }
    exit 0
}
if ($Action -eq 'Stop') {
    if ($job) { $null = Remote "scancel $($state.job_id)" }
    $tunnel = Owned-Tunnel $state
    if ($tunnel) { Stop-Process -Id $tunnel.ProcessId }
    Move-Item -LiteralPath $stateFile -Destination (Join-Path $stateDirectory "stopped-$($state.job_id)-$([DateTime]::UtcNow.Ticks).local.json")
    Result @{job_id=$state.job_id; status='stopped'; history_retained=$true}
    exit 0
}
if ($job -notmatch '^RUNNING\|([a-zA-Z0-9_.-]+)\|') { throw "Not running yet (or ended): $job. Check Status; no second job submitted." }
$state.node = $Matches[1]
Save-State $state
if ($Action -eq 'Open') {
    if ($state.desktop_pid) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($state.desktop_pid)" -ErrorAction SilentlyContinue
        if ($existing -and $existing.Name -eq 'paraview.exe' -and $existing.CommandLine -like '*desktop-startup.py*') {
            throw 'The managed desktop is already open. Reuse it instead of connecting a second client.'
        }
    }
    $tunnel = Owned-Tunnel $state
    $listener = Get-NetTCPConnection -State Listen -LocalPort 11111 -ErrorAction SilentlyContinue |
        Where-Object { $tunnel -and $_.OwningProcess -eq $tunnel.ProcessId }
    if (-not $listener) { throw 'Owned tunnel is not listening. Run Connect first.' }
    $client = Join-Path $settings.client_directory 'bin/paraview.exe'
    if (-not (Test-Path -LiteralPath $client)) { throw 'Matching ParaView desktop is missing.' }
    $receipt = Join-Path $stateDirectory 'desktop-receipt.local.json'
    if (Test-Path $receipt) { Move-Item -LiteralPath $receipt -Destination "$receipt.$([DateTime]::UtcNow.Ticks)" }
    $request = @{receipt=$receipt; expected_url='cs://127.0.0.1:11111'; job_id=$state.job_id}
    $request | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stateDirectory 'desktop-request.local.json') -Encoding UTF8
    $startup = Join-Path $PSScriptRoot 'desktop-startup.py'
    # The visible window is explicitly requested; do not hide the interactive client.
    $previousRequest = $env:GUANLAN_DESKTOP_REQUEST
    try {
        $env:GUANLAN_DESKTOP_REQUEST = Join-Path $stateDirectory 'desktop-request.local.json'
        $desktop = Start-Process -FilePath $client -ArgumentList @('--url=cs://127.0.0.1:11111', "--script=`"$startup`"") -PassThru `
            -WorkingDirectory $project -RedirectStandardOutput (Join-Path $stateDirectory 'desktop.out.log') `
            -RedirectStandardError (Join-Path $stateDirectory 'desktop.err.log')
    } finally { $env:GUANLAN_DESKTOP_REQUEST = $previousRequest }
    $state | Add-Member -NotePropertyName desktop_pid -NotePropertyValue $desktop.Id -Force
    Save-State $state
    # The first-run welcome dialog blocks startup scripts. Close only this known
    # dialog in the newly launched process; do not change saved GUI preferences.
    Add-Type -AssemblyName UIAutomationClient
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $desktop.Refresh()
        if ($desktop.HasExited -or (Test-Path $receipt)) { break }
        if ($desktop.MainWindowHandle -ne 0) {
            $root = [System.Windows.Automation.AutomationElement]::FromHandle($desktop.MainWindowHandle)
            $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Welcome to ParaView')
            $welcome = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
            if ($welcome) {
                $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Close')
                $close = $welcome.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
                if ($close) { $close.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }
            }
        }
        Start-Sleep -Milliseconds 500
    }
    Result @{status='desktop-launched'; desktop_pid=$desktop.Id; receipt=$receipt; next='verify receipt and server log'}
    exit 0
}
$ready = Remote "tail -n 30 '$($state.workspace)/expert-$($state.job_id).log'"
if ($ready -notmatch 'Waiting for client') { throw "Server is still starting. Retry Connect. Log: $ready" }
if (Owned-Tunnel $state) { Result @{status='tunnel-process-exists'; next='Status or Open'}; exit 0 }
if (Get-NetTCPConnection -State Listen -LocalPort 11111 -ErrorAction SilentlyContinue) { throw 'Port 11111 is occupied by another process.' }
$keys = Remote "ssh-keygen -F '$($state.node)'"
if ($keys -notmatch '(ssh-|ecdsa-)') { throw 'Compute host key is not known on the authenticated login host.' }
$knownHosts = (Join-Path $stateDirectory 'known_hosts').Replace('\', '/')
$keys | Set-Content -LiteralPath $knownHosts -Encoding ASCII
$expanded = & ssh -G $settings.ssh_alias
if ($LASTEXITCODE -ne 0) { throw 'Cannot expand SSH configuration.' }
$identity = @($expanded | Where-Object { $_ -like 'identityfile *' } | ForEach-Object { $_.Substring(13) } |
    Where-Object { Test-Path -LiteralPath $_ }) | Select-Object -First 1
$remoteUser = @($expanded | Where-Object { $_ -like 'user *' })[0].Substring(5)
if (-not $identity -or $remoteUser -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Expected existing SSH identity path and user in alias.' }
$arguments = @('-NT', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=60',
    '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3',
    '-o', "UserKnownHostsFile=$knownHosts", '-i', $identity, '-J', $settings.ssh_alias,
    '-L', '127.0.0.1:11111:127.0.0.1:11111', "$remoteUser@$($state.node)")
# Start-Process joins arguments on Windows; quote individual paths explicitly.
$quoted = $arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }
$process = Start-Process ssh.exe -ArgumentList $quoted -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $stateDirectory 'tunnel.out.log') `
    -RedirectStandardError (Join-Path $stateDirectory 'tunnel.err.log')
$state.tunnel_pid = $process.Id
Save-State $state
for ($attempt = 0; $attempt -lt 45; $attempt++) {
    if ($process.HasExited) { throw 'Tunnel exited. Inspect state/paraview/session/tunnel.err.log; job remains bounded and can be stopped.' }
    $listener = Get-NetTCPConnection -State Listen -LocalPort 11111 -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $process.Id }
    if ($listener) { Result @{status='ready'; job_id=$state.job_id; node=$state.node; url='cs://127.0.0.1:11111'}; exit 0 }
    Start-Sleep -Seconds 1
}
throw 'Tunnel is still starting. Use Status before retrying; job and tunnel IDs have been saved.'
