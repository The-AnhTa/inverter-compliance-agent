# Environment inventory (read-only)

Inventory date: 2026-10-29 (Australia/Sydney). Secret values, authentication files, device identifiers, account data, and private network addresses are intentionally omitted.

## Laptop

- OS: Windows 10.0.26100.
- Python: CPython 3.13.5 at the per-user Python 3.13 installation.
- Relevant available packages/tools: `httpx 0.28.1`, `pydantic 2.10.3`, `requests 2.32.3`, and TeX Live `pdftotext`. No PDF Python library was needed. The new project itself uses only the standard library.
- ADB: Android Debug Bridge 1.0.41 / 37.0.1 in the per-user Android SDK. It is not on the current `PATH`.
- Android connectivity: one USB device was detected but was `unauthorized`. No authorization, package operation, forwarding, app launch, or Android setting change was attempted.
- Running `adb devices -l` automatically started the standard local ADB daemon on the laptop. This was the only transient process-side effect of inventory collection; it did not change device settings.

## Existing MobileRun experiment

The laptop repository `~/Downloads/android-switch-lab` contains the prior model-free MobileRun integration. Its documentation records:

- MobileRun Python package 0.6.22;
- MobileRun Portal 0.7.25;
- Python 3.13.5 and `uv` 0.13.0 in an isolated `.mobilerun-venv`;
- local `AndroidDriver` use through the Portal's ADB content-provider mode, with no MobileRun Cloud or LLM service;
- dummy Android package `com.example.dummyswitch`;
- loopback Flask service at `127.0.0.1:8000`, normally reached using ADB reverse forwarding;
- narrow loopback MCP endpoint at `127.0.0.1:8766/mcp`, exposing only `control` and `inspect_ui` for the dummy app;
- generated UI trees, screenshots, backend events, and results kept under an ignored local artifacts directory.

The phone's current unauthorized state prevents reuse of that working flow. This project did not start MobileRun or inspect/change the phone.

## CSIRO Windows VM (`ssh cerguardai`)

- OS: Windows Server build 10.0.20348; Node.js reported by OpenClaw status as 26.7.0.
- Python: CPython 3.13.15. Relevant installed packages include `httpx 0.28.1`, `pydantic 2.11.7`, and `pytest 8.4.1`.
- ADB: not found on the VM `PATH`.
- MobileRun: no `mobilerun.exe` was found in the inspected OpenClaw, Downloads, or per-user Programs locations.

### OpenClaw

- Version: OpenClaw 2026.9.8 (`fc23bc8`).
- Gateway: registered Windows Scheduled Task, running, loopback-only on port 18789, connectivity probe successful, capability reported as read-only. Host desktop and Tailscale exposure are disabled. No channels are configured.
- The gateway was not restarted, reconfigured, or deep-probed.
- Compatibility notices: status reports an abandoned update attempt and two active official plugins with gateway version drift. Neither issue was changed. These should be reviewed before a later integration phase, without combining that review with initial agent creation.

Configured agents observed:

| Agent | Configured model |
|---|---|
| `main` (default) | `custom-glm52-runai-defence-ai-runai-disp-csiro-au/zai-org/GLM-5.3` |
| `controller` | `custom-glm52-runai-defence-ai-runai-disp-csiro-au/zai-org/GLM-5.3` |
| `fullvm` | `custom-glm52-runai-defence-ai-runai-disp-csiro-au/zai-org/GLM-5.3` |
| `glm-chat` | `csiro-virga-glm/zai-org/GLM-5.3-Flash` |
| `android-mobilerun` | `csiro-virga-glm/zai-org/GLM-5.3-Flash` |

Model/provider inventory:

- The primary provider uses the OpenAI-compatible completions protocol at the user-supplied GLM service's HTTPS `/v1` endpoint and advertises model ID `zai-org/GLM-5.3`.
- A second CSIRO provider uses the same protocol and advertises `zai-org/GLM-5.3-Flash`.
- Credential fields are configured, but their values and storage material were not displayed or copied.
- `openclaw models list --plain` returned only the primary fully qualified GLM-5.3 identifier, even when queried with the Flash-agent IDs, while `openclaw agents list` reports the Flash provider for two agents. Treat that discovery inconsistency as a compatibility check for the future agent phase.

OpenClaw workspaces found include the default workspace plus `workspace-android-mobilerun`, `workspace-attestations`, `workspace-fullvm`, and `workspace-glm-chat`. No Git worktree was found in the inspected VM OpenClaw/Downloads scope. Workspace memories and personal data were not read.

## Existing laptop repositories and relevant directories

- `~/Downloads/compliance-agent`: Git repository pointing to the requested GitHub origin; the remote was empty when cloned. A local `standards_documents` directory is now present and was not modified by this task.
- `~/Downloads/android-switch-lab`: Git repository containing the dummy Android app, emulator, and local MobileRun integration.
- `~/Downloads/openclaw_setup`: non-Git directory with prior Windows OpenClaw runbooks.
- `~/Downloads/cerguardai`: non-Git directory; contents were not inspected beyond filenames.
- `~/Downloads/inverter-compliance-agent`: new standalone Git repository created by this task.

## Standards sources

The following user-supplied files were found under a separate Downloads directory and inspected locally with `pdftotext`:

- `ASNZS 4777.2.2020.pdf`
- `ASNZS 4777.2.2020-2021.pdf`
- `ASNZS 4777.2.2020-2024.pdf`

No PDF was copied into this repository. Temporary extracted text was kept outside the repository in the user's temporary directory. The implemented values were source-checked at Clauses 3.3.2.2, 3.3.2.3, 3.3.4.2, 4.5.4, and 4.7 and Tables 3.6, 3.7, 4.8, and 4.10. Independent standards-domain review remains mandatory.
