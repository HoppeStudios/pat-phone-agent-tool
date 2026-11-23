# Software setup only by default. Phone and audio changes require -ConfigurePhone.
param([switch]$ConfigurePhone)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) { throw 'Install Codex CLI and run codex login first.' }
if (-not (Test-Path -LiteralPath $python)) {
    & py -3.12 -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
}
& $python -m ensurepip
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the bundled pip installer.' }
& $python -m pip install --disable-pip-version-check --require-hashes --only-binary=:all: -r (Join-Path $root 'requirements.lock')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $codex.Source login status
if ($LASTEXITCODE -ne 0) { throw 'Run codex login, then run this setup again.' }
& $python (Join-Path $root 'voice-loop\czech_assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Czech model download or verification failed.' }
& $codex.Source mcp add pat-phone --env PYTHONUTF8=1 -- $python (Join-Path $root 'phone_mcp.py')
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
if ($ConfigurePhone) {
    Write-Host 'Phone setup requires machine-wide Developer Mode and mobile-device access for this Windows user.'
    & (Join-Path $root 'scripts\Install-PhoneHelper.ps1') -EnableDeveloperMode -EnableMobileAccess
    Write-Host 'Check the audio requirements in docs/INSTALLATION.md, then finish the profile and Bluetooth pairing.'
} else {
    Write-Host 'Codex and Czech software setup finished. No phone, audio-driver, pairing or startup settings were changed.'
    Write-Host "Finish the name and terms setup by running: $root\.venv\Scripts\pythonw.exe $root\note.py"
}
