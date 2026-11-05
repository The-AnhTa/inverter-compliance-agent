# End-to-end inverter compliance AI demonstration report

Date: 30 October 2026 (Australia/Sydney)

## Outcome

The Windows-only demonstration is implemented and tested through the laptop orchestrator, existing read-only OpenClaw agent, local GLM-5.3 endpoint, deterministic compliance engine, evidence-aware extractor, and Markdown/JSON reporting. The synthetic end-to-end run completed successfully.

Physical Android validation reached the device and discovered the installed dummy and inverter-app environment, but MobileRun UI capture is blocked because the MobileRun Portal accessibility service is disabled. The software stopped without launching or changing either inverter app. No real inverter setting, Android setting, switch, login field, OpenClaw configuration, agent permission, plugin, or Gateway process was modified.

## Architecture and trust boundary

1. `client/chat.py` classifies a small supported request set and maintains the fixed OpenClaw session `inverter-compliance-demo-v1`.
2. `client/openclaw_client.py` invokes only host `cerguardai` and agent `inverter-audit`. Raw user text is supplied through subprocess stdin with `shell=False`.
3. The Windows VM's OpenClaw 2026.9.8 does not implement `--message-file -`; it treats `-` as a filename. The client therefore uses a fixed encoded PowerShell wrapper which reads SSH stdin, writes a GUID-named temporary UTF-8 file, invokes `--message-file <temporary-path> --json`, and removes the file in `finally`. No user text is interpolated into a command or filename.
4. The agent provides local-GLM interpretation only. It cannot execute the compliance plugin. Deterministic results come from the laptop `ComplianceEngine`.
5. `android/mobile_client.py` uses MobileRun `local-android-adb`, an explicit package allow-list, foreground-package checks, and only launch, hierarchy, screenshot, scroll, and back. It exposes no tap or text-entry API to the orchestrator. Credential-like fields cause capture to stop before hierarchy or screenshot artifacts are saved.
6. `android/parameter_extractor.py` maps unambiguous aliases deterministically. Only an ambiguous value may be sent to the same local GLM session, and the returned JSON is schema-checked and marked low/medium confidence.
7. Every non-synthetic assessment must carry `inspection.evidence_backed=true`; successful observations retain evidence reference, page, capture time, snippets, and mapping confidence.

## Environment verification

- Laptop Python: 3.13.5.
- Existing MobileRun environment Python: 3.13.5.
- MobileRun: 0.6.22; local core previously verified as 0.6.3; SDK 6.0.0.
- ADB: 1.0.41, platform-tools 37.0.1.
- Authorized device: `RF8XA040EKN` (`device`, not unauthorized or offline).
- Candidate packages discovered from third-party package names only: `com.goodwe.sems.plus` and `com.isolarcloud.manager`.
- OpenClaw: 2026.9.8. Gateway is running and healthy on loopback, PID 1136; RPC probe is read-only and successful.
- Existing local model invocation succeeded with provider `custom-glm52-runai-defence-ai-runai-disp-csiro-au` and model `zai-org/GLM-5.3`.
- Six agents remain present: the five pre-existing agents plus `inverter-audit`.
- Effective `inverter-audit` allow-list remains exactly `read`; its deny-list includes exec/process/write/edit/patch/browser/web/session/gateway/Android classes.
- The `inverter-compliance` plugin has no configuration entry and was not activated.

No credentials, provider profile contents, authentication files, or personal account values were copied into this report.

## Standards rule set

The supplied local PDFs under `C:\Users\anh001\Downloads\compliance-agent\standards_documents` were used as the authoritative source. The repository contains 19 structured rules:

| Scope | Rules | Source |
|---|---:|---|
| Increase/decrease active-power rate limits | 2 | Clause 3.3.4.2 |
| VW1/VW2 defaults for Australia A, B, C and New Zealand, with table permitted ranges | 8 | Clause 3.3.2.2, Table 3.6 |
| Australia A VV1–VV4 defaults, with table permitted ranges | 4 | Clause 3.3.2.3, Table 3.7 |
| fURF for Australia A, B, C and New Zealand | 4 | Clause 4.7, Table 4.10 |
| Voltage-disturbance response requiring evidence beyond app settings | 1 | Clause 4.5.4, Table 4.8 |

All rules are `source_checked_human_review_required`; none is marked validated. The licensed PDFs remain outside the repository and are ignored by Git.

## Validation results

The final standard-library suite passes 27 tests. It covers:

- default match, default deviation, out-of-range, unavailable interface field, not-assessable requirement, verified synthetic variation, and unknown region;
- non-synthetic evidence gating and evidence preservation;
- deterministic parameter extraction from a clearly synthetic recorded UI fixture;
- raw prompt isolation from SSH arguments and shell/path injection rejection;
- package filtering and refusal to collect credential nodes;
- malformed, oversized, unexpected-field, unit-mismatch, and unverified-approval inputs;
- integrity checking of the legacy fixed-path assessment adapter.

The real SSH/GLM smoke test returned valid OpenClaw JSON and correctly stated that an unavailable app field does not establish capability absence. The one-command synthetic run produced ten applicable findings and local reports. Example outputs are `examples/synthetic_compliance_report.md` and `examples/synthetic_compliance_report.json`; timestamped runtime outputs are under ignored `output/reports/`.

## Physical Android result and exact rerun

The MobileRun ping and dummy inspection both stopped with Portal unavailable because the Portal accessibility service is disabled. This is an external device-state blocker, not a code or ADB-authentication failure. The project did not enable the service because Android setting changes were prohibited.

To rerun after separate operator approval:

1. On the phone, manually enable the already-installed MobileRun Portal accessibility service. Do not enter credentials through automation.
2. For a real app, log in manually and leave a known read-only inverter settings page visible. Ensure no password or credential field is on screen.
3. From this repository run:

   ```powershell
   .\start-demo.ps1 -Once "inspect dummy app"
   .\start-demo.ps1 -Once "assess inverter Australia A package com.goodwe.sems.plus"
   # or, if that is the operator-approved app:
   .\start-demo.ps1 -Once "assess inverter Australia A package com.isolarcloud.manager"
   ```

4. Review the evidence and generated report. Do not use the result operationally until the rules and mappings receive independent human validation.

The package must be selected by the operator; discovery alone does not establish which app is connected to the intended inverter. No live integration should proceed until the Portal service and approved package choice are explicitly resolved.

## Compatibility and remaining issues

- OpenClaw's documented path form works, while `--message-file -` does not on this Windows release. The tested temporary-file wrapper is the safe compatibility path.
- The existing MobileRun environment is reused by `start-demo.ps1`. `requirements-demo.txt` pins the known working versions for a future project-local installation; the attempted fresh resolver was stopped after excessive dependency backtracking and installed nothing globally.
- The partially created `.venv` is ignored and is not selected because it cannot import MobileRun. The launcher selects the verified existing local environment first.
- Real app-specific navigation was deliberately not guessed. The current orchestrator captures only the operator-approved foreground package's initial page; its guarded scroll/back primitives can support a separately reviewed navigation map later.
- A UI-only assessment cannot establish type-test conformity or absence of an inverter capability.

## Commands used for final verification

```powershell
python -m unittest discover -s tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1 -Once "synthetic demo"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1 -Once "device status"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1 -Once "inspect dummy app"
```

The last command is expected to fail safely until the operator enables MobileRun Portal. This completes the requested work without proceeding to live inverter control.
