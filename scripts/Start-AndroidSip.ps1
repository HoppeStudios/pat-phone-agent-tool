param(
    [Parameter(Mandatory=$true)][string]$Config,
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe')
)
$ErrorActionPreference = 'Stop'
$Config = (Resolve-Path -LiteralPath $Config).ProviderPath
$Python = (Resolve-Path -LiteralPath $Python).ProviderPath
$state = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$distro = if($state.wsl_distro){$state.wsl_distro}else{'Debian'}
$directory = Split-Path -Parent $Config
$hostScript = Join-Path $directory 'android_sip_host.py'
if(-not(Test-Path -LiteralPath $hostScript)){throw 'Configure the reviewed SIP runtime first.'}

# Query the WSL-owned PID and exact script identity; never stop another process.
$probe = 'from pathlib import Path; p=Path("/var/lib/pat-codex-sip/runtime.pid"); alive=p.exists() and Path("/proc/"+p.read_text().strip()+"/cmdline").exists(); command=Path("/proc/"+p.read_text().strip()+"/cmdline").read_bytes() if alive else b""; print("owned" if b"/var/lib/pat-codex-sip/sip_runtime.py" in command else "foreign" if alive else "stopped")'
$linuxState = $probe | & wsl.exe -d $distro --exec python3 -
if($LASTEXITCODE -ne 0){throw 'The configured WSL distribution is unavailable.'}
if($linuxState -eq 'foreign'){throw 'Linux PID ownership mismatch; inspect it manually.'}
if($linuxState -ne 'owned'){
    Start-Process -FilePath wsl.exe -ArgumentList @('-d', $distro, '--exec', 'python3', '/var/lib/pat-codex-sip/sip_runtime.py', '--config', '/var/lib/pat-codex-sip/runtime-private.json') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $directory 'linux.stdout.log') -RedirectStandardError (Join-Path $directory 'linux.stderr.log') | Out-Null
}
$linuxAddress = ((& wsl.exe -d $distro --exec hostname -I) -split '\s+' | Where-Object {$_ -match '^\d+\.\d+\.\d+\.\d+$'} | Select-Object -First 1)
if(-not $linuxAddress){throw 'Could not discover the current WSL IPv4 address.'}
$hostPidFile = $state.windows_pid_file
$hostRunning = $false
if(Test-Path -LiteralPath $hostPidFile){
    $hostProcessId = [int](Get-Content -LiteralPath $hostPidFile -Raw)
    $owned = Get-CimInstance Win32_Process -Filter "ProcessId=$hostProcessId" -ErrorAction SilentlyContinue
    if($owned){
        if($owned.CommandLine -notlike ('*"' + $hostScript + '"*') -and $owned.CommandLine -notlike ('*' + $hostScript + ' --config*')){throw 'Windows PID ownership mismatch; inspect it manually.'}
        if($state.linux_address -ne $linuxAddress){throw 'WSL address changed. Finish calls, stop the verified owned Windows forwarder, then start again.'}
        $hostRunning = $true
    }
}
if(-not $hostRunning){
    $state.linux_address = $linuxAddress
    $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Config -Encoding UTF8
    Start-Process -FilePath $Python -ArgumentList @('"' + $hostScript + '"', '--config', '"' + $Config + '"') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $directory 'host.stdout.log') -RedirectStandardError (Join-Path $directory 'host.stderr.log') | Out-Null
}
Write-Output 'Owned Android SIP runtime started or reused. No call was placed. Run pat.py check to verify phone registration.'
