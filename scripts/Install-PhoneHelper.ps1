param(
    [switch]$EnableDeveloperMode,
    [switch]$EnableMobileAccess,
    [string]$StateDirectory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PatCodex'),
    [string]$PackageDirectory
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Verify-Payload.ps1')
$root = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $root 'installation-manifest.json') -Raw | ConvertFrom-Json
$sdk = $manifest.dotnetSdk
if([Environment]::OSVersion.Version.Build -lt 22000 -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'This helper requires Windows 11 x64.'}
if(Get-Process iphonecall -ErrorAction SilentlyContinue){throw 'A phone helper is active. Finish the call and close it before installing.'}
$StateDirectory = [IO.Path]::GetFullPath($StateDirectory)
if(-not $PackageDirectory){$PackageDirectory = Join-Path $StateDirectory 'phone-helper'}
$PackageDirectory = [IO.Path]::GetFullPath($PackageDirectory).TrimEnd([IO.Path]::DirectorySeparatorChar)
$existing = Get-AppxPackage 'OasisTeam.PatPhone'
if($existing -and $existing.InstallLocation.TrimEnd([IO.Path]::DirectorySeparatorChar) -ne $PackageDirectory){throw 'Another installation owns the phone helper package. Inspect it before replacing it.'}
New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
$archive = Join-Path $StateDirectory "downloads\dotnet-sdk-$($sdk.version)-win-x64.zip"
[void](Get-PatVerifiedDownload -Url $sdk.url -Destination $archive -Hash $sdk.sha512 -Algorithm SHA512)
Invoke-PatPayloadScan $archive
$sdkDirectory = Join-Path $StateDirectory "tools\dotnet-$($sdk.version)"
if(-not(Test-Path -LiteralPath (Join-Path $sdkDirectory 'dotnet.exe'))){
    New-Item -ItemType Directory -Path $sdkDirectory -Force | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $sdkDirectory
}
$dotnet = Join-Path $sdkDirectory 'dotnet.exe'
Assert-PatPublisher -Path $dotnet -PublisherPattern 'Microsoft Corporation'
$environment = @{}
foreach($name in 'DOTNET_CLI_HOME','DOTNET_CLI_TELEMETRY_OPTOUT','DOTNET_GENERATE_ASPNET_CERTIFICATE','NUGET_PACKAGES'){
    $environment[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:DOTNET_CLI_HOME = Join-Path $StateDirectory 'dotnet-home'
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    $env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
    $env:NUGET_PACKAGES = Join-Path $StateDirectory 'nuget'
    Push-Location $root
    try {
        $actual = (& $dotnet --version) -join ''
        if($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $sdk.version){throw 'The downloaded SDK does not match its pinned version.'}
        & $dotnet publish (Join-Path $root 'iphone-hfp\iphonecall\iphonecall.csproj') --configuration Release --runtime win-x64 --self-contained true --source https://api.nuget.org/v3/index.json --output $PackageDirectory -p:DebugType=None -p:DebugSymbols=false -p:NuGetAudit=true --verbosity minimal
        if($LASTEXITCODE -ne 0){throw 'Phone helper build failed.'}
    } finally {Pop-Location}
} finally {
    foreach($name in $environment.Keys){[Environment]::SetEnvironmentVariable($name,$environment[$name],'Process')}
}
$runtime = Get-Content -LiteralPath (Join-Path $PackageDirectory 'iphonecall.runtimeconfig.json') -Raw | ConvertFrom-Json
if($runtime.runtimeOptions.includedFrameworks[0].version -ne $sdk.runtime){throw 'The helper runtime differs from the reviewed pin.'}
Invoke-PatPayloadScan $PackageDirectory
$developerKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
if((Get-ItemProperty -LiteralPath $developerKey -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense -ne 1){
    if(-not $EnableDeveloperMode){throw 'Developer Mode is required. Read its machine-wide scope, then rerun with -EnableDeveloperMode if you approve.'}
    $approved = Start-Process -FilePath "$env:WINDIR\System32\reg.exe" -ArgumentList @('add','HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock','/t','REG_DWORD','/f','/v','AllowDevelopmentWithoutDevLicense','/d','1') -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    if($approved.ExitCode -ne 0){throw 'Windows did not enable Developer Mode.'}
}
if((Get-ItemProperty -LiteralPath $developerKey).AllowDevelopmentWithoutDevLicense -ne 1){throw 'Developer Mode could not be verified.'}
if(-not $existing){Add-AppxPackage -Register (Join-Path $PackageDirectory 'AppxManifest.xml')}
$installed = Get-AppxPackage 'OasisTeam.PatPhone'
if(-not $installed -or $installed.InstallLocation.TrimEnd([IO.Path]::DirectorySeparatorChar) -ne $PackageDirectory){throw 'Phone helper registration could not be verified.'}
$mobileKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Mobility'
if((Get-ItemProperty -LiteralPath $mobileKey -ErrorAction SilentlyContinue).CrossDeviceEnabled -ne 1){
    if(-not $EnableMobileAccess){throw 'Enable Allow this PC to access your mobile devices, or explicitly approve -EnableMobileAccess.'}
    New-Item -Path $mobileKey -Force | Out-Null
    Set-ItemProperty -LiteralPath $mobileKey -Name CrossDeviceEnabled -Type DWord -Value 1
}
if((Get-ItemProperty -LiteralPath $mobileKey).CrossDeviceEnabled -ne 1){throw 'Mobile-device access could not be verified.'}
$receipt = [ordered]@{sdk=$sdk.version;runtime=$sdk.runtime;package=$installed.PackageFullName;directory=$PackageDirectory;helperSha256=(Get-FileHash -LiteralPath (Join-Path $PackageDirectory 'iphonecall.exe') -Algorithm SHA256).Hash}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StateDirectory 'helper-installation.json') -Encoding utf8
Write-Host 'The Windows helper is registered. No call was placed. Continue with the name, terms, audio and Bluetooth phone setup.'
