$ErrorActionPreference = 'Stop'

function Invoke-PatPayloadScan([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).ProviderPath
    $platform = Join-Path $env:ProgramData 'Microsoft\Windows Defender\Platform'
    $scanner = Get-ChildItem -LiteralPath $platform -Directory -ErrorAction SilentlyContinue |
        Where-Object {$_.Name -match '^\d'} | Sort-Object Name -Descending |
        ForEach-Object {Join-Path $_.FullName 'MpCmdRun.exe'} | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
    if(-not $scanner){throw 'Microsoft Defender command line scanner was not found. Scan the payload before installation.'}
    & $scanner -Scan -ScanType 3 -File $resolved -DisableRemediation
    if($LASTEXITCODE -ne 0){throw "Payload scan failed or detected a threat. Exit code: $LASTEXITCODE"}
}

function Get-PatVerifiedDownload([string]$Url, [string]$Destination, [string]$Hash, [string]$Algorithm='SHA256') {
    if($Url -notmatch '^https://'){throw 'Installer downloads require HTTPS.'}
    New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
    if(-not(Test-Path -LiteralPath $Destination)) {
        $temporary = $Destination + '.partial'
        try {
            Invoke-WebRequest -Uri $Url -OutFile $temporary -UseBasicParsing -TimeoutSec 600
            if((Get-FileHash -LiteralPath $temporary -Algorithm $Algorithm).Hash -ne $Hash){throw 'Downloaded payload hash verification failed.'}
            Move-Item -LiteralPath $temporary -Destination $Destination
        } finally {
            if(Test-Path -LiteralPath $temporary){Remove-Item -LiteralPath $temporary -Force}
        }
    }
    if((Get-FileHash -LiteralPath $Destination -Algorithm $Algorithm).Hash -ne $Hash){throw 'Cached payload hash verification failed. It was not executed.'}
    return $Destination
}

function Assert-PatPublisher([string]$Path, [string]$PublisherPattern) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch $PublisherPattern){throw 'The payload does not have the expected valid publisher signature.'}
}
