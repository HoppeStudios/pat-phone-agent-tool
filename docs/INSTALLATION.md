# Installation and first call

## Requirements

| Requirement | Why it is needed |
| --- | --- |
| Windows 11 on an Intel or AMD x64 PC | The helper uses Windows phone call APIs. Windows 10 and Windows on ARM are not supported by this build. |
| Bluetooth on the PC and an iPhone or Android phone | Calls use the phone's hands free link and its real SIM. |
| A working mobile SIM and outgoing call plan | The fork is not a telephone service and does not provide a number. |
| Codex CLI, verified with version 0.153.4, signed in through ChatGPT | Codex supplies the conversation model. Claude Code is not required. |
| Python 3.12 | Runs the local MCP server and speech components. |
| Windows Developer Mode | Required to register the helper's development package. This is a machine-wide setting and needs explicit approval and administrator access. |
| “Allow this PC to access your mobile devices” enabled | Required for Windows to expose the phone line. This affects the current Windows user. |
| VB CABLE and a second suitable virtual speaker | They separate the remote caller from the generated voice and prevent feedback. The standard silent setup uses Voicemeeter's virtual speaker. |
| Several GB of free disk space | Python packages and speech models are local. Czech model files occupy about 700 MB. |

Android also needs the Calls permission enabled for the PC in its Bluetooth settings. A phone may need to remain unlocked during pairing. On a dual SIM phone, select the intended default outgoing SIM on the phone. The helper uses that phone's calling configuration.

## Cost

This fork is free software under Apache 2.0. It does not need Twilio, Vapi or a paid telephone API. It uses your existing Codex access and mobile plan, so their limits and charges still apply. Do not assume that international calls or usage outside an existing plan are free.

Voicemeeter's standard functions are available under its donationware model. Optional paid features are not needed by this setup. No installer should purchase a license or change a service plan automatically.

## Get the Codex branch

Until the Codex pull request is merged, use the review branch explicitly:

```powershell
git clone --branch codex-czech-setup --single-branch https://github.com/HoppeStudios/pat-phone-agent-tool.git
cd pat-phone-agent-tool
```

Keep this folder in a stable location. Codex's MCP entry points to the local environment and server script. Moving or deleting the folder breaks that registration until it is updated.

## Install software

Install Python 3.12 and Codex CLI from their official sources. Sign in using `codex login` when needed. Then run from a normal PowerShell window as the Windows user who will use the phone:

```powershell
powershell -File .\setup-codex.ps1
```

The software step installs the hash pinned Python wheels, verifies the pinned Czech models and registers the stdio MCP server as `pat-phone`. It does not enable Developer Mode, install drivers, change Bluetooth pairings or start a call. It does not change Codex's selected model or copy account credentials. Existing Codex chats may need an MCP restart.

## Install the Windows helper

Read the security scope in the requirements table before approving the required settings:

```powershell
powershell -File .\scripts\Install-PhoneHelper.ps1 -EnableDeveloperMode -EnableMobileAccess
```

The script downloads the exact Microsoft SDK version in installation-manifest.json, verifies its hash and publisher, builds the helper with its own runtime, scans it and registers it for the current user. Developer Mode may trigger a Windows administrator prompt. Handle that prompt yourself. The script does not approve Windows prompts and does not restart the PC.

If those two settings are already enabled, omit the two switches. The script stops with an explanation if a required setting is disabled. It also stops when a helper process is already running or another installation owns the package identity.

## Audio setup

An existing working Steam Streaming Speakers endpoint is also supported as the silent speaker. In that case Voicemeeter is not required. If CABLE or Steam devices are installed but hidden or disabled in Windows Sound settings, enable only the endpoints used by Pat. Preserve the normal headset defaults. Confirm that both CABLE Input and CABLE Output are available before calling.

Keep an existing working VB CABLE installation. Do not install a second copy just to follow these steps. If it is missing, install it from [VB Audio's official site](https://vb-audio.com/Cable/) after checking its actual installer.

For the standard silent call route, install the reviewed Voicemeeter version pinned in installation-manifest.json. Verify the archive hash and the publisher signature, scan the extracted installer, then run `voicemeetersetup.exe -install` with Windows administrator approval. A reboot may be required. Restart only when you have saved your work. After installation, leave the Voicemeeter application closed. Only its virtual speaker is used.

Check that the normal speaker and microphone remain your Windows defaults. A driver installer can change them. Pat changes defaults while a call is active and restores the saved defaults afterwards. Do not run audio setup during another call.

## Profile and phone pairing

```powershell
.venv\Scripts\pythonw.exe .\note.py
```

Finish the profile with the introduction name you want, your region, time zone and date format. Read the terms and accept them only if you agree. Setup must not invent acceptance. Select Čeština if you want incoming AI calls in Czech. Leave unknown callers on Ask unless you deliberately want a different policy.

Choose “Set up the phone for Pat's calls” from the note's menu. Keep the phone's Bluetooth settings open. Select the correct device, compare the displayed pairing code and approve it on the phone. An assistant cannot verify the phone-side code without your response.

If Phone Link already owns the call pairing, Pat may need to recreate that selected phone's pairing. First finish any active call. Do not remove unrelated devices or stop an active call. Windows lets a phone use only one hands free host at a time.

This fork refuses pairing while Phone Link is running. It does not kill Phone Link or change its startup policy. Close that app yourself after ending any call.

## Wi-Fi and Tailscale

Wi-Fi and Tailscale do not replace the Bluetooth call-audio path in this fork. Tailscale can carry authenticated network traffic, but it does not grant access to Android's cellular call audio. Ordinary Android apps cannot capture the voice-call uplink and downlink using the privileged CAPTURE_AUDIO_OUTPUT permission. See [Android's audio-input rules](https://developer.android.com/media/platform/sharing-audio-input).

Remote command control and bidirectional SIM-call audio are separate requirements. An ADB connection or an online Tailscale peer alone is not a working voice gateway. Do not document either as proof of calling support.

There is experimental work on [scrcpy client audio injection](https://github.com/Genymobile/scrcpy/pull/7004). It targets VoIP, requires Android 13 or newer and a special client build, and its author warns that audio-policy behavior varies by device. Separate [reports for Android 16](https://github.com/Genymobile/scrcpy/issues/3880) describe call-audio injection, but this is not established SIM-call support for every phone. It is not integrated into this fork. A future network backend must verify receiving call audio, injecting the assistant's voice into the cellular uplink, call control and cleanup on the actual device before claiming compatibility.

A network-only implementation would need a separately verified device-specific privileged gateway, suitable external telephony hardware, or a supported VoIP carrier arrangement. Those are not implemented here. They may need extra hardware, fees or system changes. This installer does not root a phone, unlock its bootloader, purchase a service or promise free carrier calls.

## Checks before calling

```powershell
iphonecall self-test
iphonecall phones
iphonecall status
.venv\Scripts\python.exe .\pat.py check
```

The self test uses made-up phones. The other commands inspect or connect the selected phone without dialing. A successful connection is not proof that a real recipient can hear the AI or sees the intended caller ID.

For the first real test, use a second phone you own or a consenting person. Specify the exact test number and purpose. Do not use a pizza shop as an unannounced test. Confirm audio in both directions and the displayed caller ID. A real call can incur carrier charges.

## Using Codex

Ask for the specific call, recipient, purpose and budget. For Czech, request `language: "cs"`. The API keeps English as its default for compatibility. Example wording:

> Call my saved contact Test Phone in Czech and say this is an audio test. Do not order or agree to anything.

For an actual order, provide the exact restaurant, items, pickup or delivery details, allowed substitutions and maximum price. The agent must read back names, prices and times. Czech recognition can confuse product names, so its transcript alone is not proof of the order.

## Updating and removal

Quit Pat and finish any call before updating. Review a specific commit, run the checks and scan changed executable payloads. Do not run an upstream latest updater or deploy an unreviewed branch automatically. Update an existing startup shortcut only if you already use one. Software setup does not create an automatic answering policy.

Use `codex mcp remove pat-phone` only when that entry belongs to this installation. To remove the helper, unregister its package after closing it. Keep user contact and call data unless the user requests deletion. Do not remove shared audio drivers without checking their other users. Never keep an obsolete runtime as an automatic rollback installation after a replacement is verified.
