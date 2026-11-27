# Codex and Czech implementation

## Codex backend

The call and note agents use Codex CLI's documented app server protocol over local stdio. Claude Code and an Anthropic account are not required. Existing ChatGPT login state is used in place. Authentication files and API keys are not copied into this repository.

The implementation was verified against Codex CLI 0.153.4. It inherits the configured Codex model unless `PAT_CODEX_MODEL` is set. `VOICE_LOOP_CODEX` can specify an absolute native `codex.exe` path. Shell wrappers are not accepted for that override.

Voice threads are ephemeral and have no environment access. The child client disables inherited MCP servers, apps, plugins, hooks, memory, shell tools and browsing. Permission requests are declined. The note dispatcher enables the local tool host needed by this Codex version and exposes only `place_call`, `get_call`, `contact_notes` and `list_contacts` as client-defined functions. Its threads remain read only. This configuration is not an operating system isolation guarantee for future Codex versions.

Conversation state persists across turns within a call. Barge-in uses `turn/interrupt`. Timeouts and process exits are reported. A Windows job object closes only the child process tree owned by this client. It does not stop the main Codex app or unrelated chats.

Some internal upstream transcript labels and module names retain legacy model names for compatibility. Actual model traffic in this fork uses the Codex backend.

## Czech speech

Use `language: "cs"` in `place_call`. The note has a Čeština option for incoming calls and a Czech voice setting. English remains the API default. Czech requests submitted through the note select Czech unless another language is requested.

Czech recognition uses Parakeet TDT v3 in quantized ONNX form. Synthesis uses Piper `cs_CZ-jirka-medium`. The model revisions, sizes and hashes are in `voice-loop/czech_assets.py`. The recognizer loads verified ONNX and text data, without running Python from a remote model repository.

Czech support includes AI disclosure, identity questions, takeover and timeout messages, speaking rules, name controls and relative-date normalization. Product names can be misrecognized. Repeat important details for confirmation and do not treat a transcript alone as proof that an order was correct.

An optional `assistant_name` in the local user profile changes the assistant's introduction while retaining AI and listener disclosure. It is separate from the owner's name and must not be stored as the human owner's identity. Without it, the existing introduction is preserved.

## Installation boundaries

Python wheels are pinned in requirements.lock. Microsoft SDK and optional Voicemeeter versions are pinned in installation-manifest.json. The helper includes its own runtime and is registered as a Windows development package. Developer Mode and mobile-device access are explicit requirements, with their scopes described in docs/INSTALLATION.md.

The original transport uses a Bluetooth hands free connection to the phone's SIM. The experimental [Android SIP transport](docs/ANDROID_SIP.md) uses a separate Shizuku-enabled gateway over Tailscale and a local Asterisk/AudioSocket backend. It is outgoing-only, with incoming answering and handover disabled. Registration, permission preflight and local echo are verified separately from live cellular audio; a connected network device is not a verified completed telephone call.

No live telephone test is part of the default test suite or CI. Synthetic audio, a Codex text reply, a connected line and a completed call are different evidence and must be reported separately.

## Upstream and licenses

Based on upstream commit `1340f9e9a1cbbb8fba5329a030fa2d74aab21509` of [azizdaurov/pat-phone-agent-tool](https://github.com/azizdaurov/pat-phone-agent-tool). This is a HoppeStudios modification and is independent of Oasis Team and OpenAI. The original Apache 2.0 license and notices remain.

Speech models keep their own licenses. See the [NVIDIA model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) and [Piper Czech model card](https://huggingface.co/rhasspy/piper-voices/blob/e5349433ed883a32f893a434dc43a6c66b95ef7c/cs/cs_CZ/jirka/medium/MODEL_CARD).
