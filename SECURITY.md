# Security and privacy

This fork starts real phone calls only when its call tools are invoked. A five minute call limit, AI disclosure, identity checks and brief restrictions reduce risk but cannot make an unauthorized call authorized.

Keep the MCP server local over stdio. Do not expose it as a public unauthenticated service. Call content is transcribed locally and sent to OpenAI through Codex. Local contact masking has limits. Do not put sensitive information into a call brief unless it is necessary and approved for that recipient.

Python dependencies are pinned with hashes in requirements.lock. Czech model revisions and hashes are in voice-loop/czech_assets.py. Microsoft SDK and optional Voicemeeter payloads are pinned in installation-manifest.json. The helper is built from source and published with its own .NET runtime. It is registered as a development package and is not an official Microsoft or Oasis Team package.

Developer Mode permits development app registration across Windows. Mobile-device access allows this Windows user to connect mobile devices. Audio drivers are machine-wide components. Setup must make these scopes clear and obtain the user's approval before changing them. An administrator prompt must be handled by the user. Setup never approves it for them.

Do not publish a report containing phone numbers, names, Bluetooth addresses, account details, file paths or transcripts. Public GitHub issues are unsuitable for sensitive reports. Use GitHub private vulnerability reporting when it is available, or contact the repository maintainers privately through an agreed channel. Do not send personal information to an unverified address.

Hash verification, signatures, antivirus scans and tests are bounded evidence. They are not a guarantee that software or a future dependency is safe. Phone makers, Windows versions, Bluetooth drivers and model responses can behave differently.
