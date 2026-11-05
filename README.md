# Inverter Compliance AI Demonstration

This Windows-only project combines a conversational local GLM-5.3 interface, a deterministic AS/NZS 4777.2 assessment engine, and a conservative read-only MobileRun Portal/ADB inspection boundary.

The OpenClaw compliance plugin is not used or configured. The existing `inverter-audit` agent remains unchanged and limited to `read`; laptop-side Python validates every requested operation, performs deterministic assessment, and generates local reports.

## Start chatting

From PowerShell in this directory:

```powershell
.\start-demo.ps1
```

For bounded deterministic SEMS+ exploration with no GLM/OpenClaw call:

```powershell
.\start-demo.ps1 -ExploreGoodWe
```

The same direct mode is available as `/explore` inside interactive chat. It launches only the fixed approved GoodWe package when needed, validates a fresh package-scoped accessibility tree before and after every action, and stops after at most 20 launch/tap/scroll/back actions. Normal natural-language chat remains separate and continues to use the local GLM through OpenClaw.

The terminal starts immediately with `You:` and `Agent:` prompts. Ask naturally—for example, what the agent can do, what was observed previously, what a parameter means, what app is open, or whether the current screen can be inspected. Exact command phrases, package names, and predefined menus are not required.

Optional local conveniences are `/help`, `/status`, `/debug`, and `/exit`. `/debug` shows tool calls and evidence diagnostics; ordinary chat hides internal JSON and traces.

For one-turn automation:

```powershell
.\start-demo.ps1 -Once "What does VW1 mean?"
```

The OpenClaw CLI deadline defaults to 600 seconds and the Python SSH-process deadline defaults to 690 seconds. They can be changed without editing code:

```powershell
.\start-demo.ps1 -OpenClawTimeoutSeconds 720 -ProcessTimeoutSeconds 810
```

Equivalent environment variables are `INVERTER_OPENCLAW_TIMEOUT_SECONDS` and `INVERTER_OPENCLAW_PROCESS_TIMEOUT_SECONDS`. The Python deadline must remain at least 30 seconds longer than the OpenClaw deadline. Redacted timing events are written locally to `output/logs/conversation-timing.jsonl`.

Direct Python and test commands:

```powershell
python -m client.chat --once "What did you find previously?"
python -m unittest discover -s tests -v
```

General conversation and standards explanations do not require Android or MobileRun. Android inspection requires the existing MobileRun environment, one authorized device, a working Portal accessibility service, and an approved foreground app.

## Safety and evidence

The model may choose only six operations: device status, current-screen inspection, approved-screen navigation, observation extraction, deterministic assessment, and local report generation. Python rejects unknown operations, arbitrary paths, shell commands, unsupported navigation, and all setting changes. Android UI text is treated as untrusted evidence, never instructions.

No region is assumed. An assessment requires a user-confirmed region and actual evidence-backed configuration values. A field not visible in the app is merely unobserved; it does not prove the inverter lacks that capability. Type-test requirements cannot be assessed from app settings.

The earlier GoodWe result remains historical only: five SEMS+ screens, 174 accessibility nodes, 15 numeric operating measurements, zero mapped standards configuration parameters, and therefore no compliance conclusion.

Reports are written locally under `output/reports/`. Licensed standards PDFs and raw Android captures are excluded from Git.

## Main components

- `client/chat.py`: clean interactive terminal and optional slash commands.
- `client/conversation.py`: conversation memory, GLM decision schema, bounded action loop, and laptop tool validation.
- `client/openclaw_client.py`: fixed-agent SSH transport using the Windows stdin temporary-file workaround.
- `android/mobile_client.py`: Portal decoding, approved-app checks, fresh evidence capture, and allow-listed navigation.
- `android/parameter_extractor.py`: deterministic contextual label mapping with local GLM fallback only for genuine ambiguity.
- `compliance/`: typed deterministic rule evaluation.
- `standards/`: 19 source-checked rules and their parameter catalog; all still require human review.
- `reports/generate_report.py`: local Markdown and JSON reports.
- `docs/conversational_interface_report.md`: implementation and verification results.
