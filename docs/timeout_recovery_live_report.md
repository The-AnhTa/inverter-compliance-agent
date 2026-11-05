# GLM/OpenClaw Timeout and Live Inspection Report

Date: 2026-10-30  
Scope: laptop conversation client only. No Gateway, agent, plugin, Android-setting, or inverter-setting changes were made.

## Cause

`GLMConversationModel` previously constructed `OpenClawClient` with an explicit 180-second OpenClaw CLI timeout. `OpenClawClient.ask()` then imposed a Python `subprocess.run()` deadline of `timeout_seconds + 20`, or 200 seconds. OpenClaw 2026.9.8 documents `--timeout` in seconds and has a normal default of 600 seconds. The client was therefore terminating slow local GLM turns substantially earlier than the installed CLI's expected operating window.

The reproduced slow case occurred during GLM action selection for `Inspect it.`, before `inspect_current_screen` or any other MobileRun operation ran. The single SSH process remained silent until the Python safety deadline. No retry or Android operation was issued. This separates model latency from Android inspection failure.

## Changes

- OpenClaw's CLI deadline now defaults explicitly to 600 seconds.
- Python's SSH-process deadline defaults to 690 seconds and must be at least 30 seconds longer than the CLI deadline.
- Both values are configurable through CLI/PowerShell arguments or environment variables.
- SSH uses an explicit 20-second connection deadline and keepalives.
- The Windows UTF-8 temporary-message-file workaround is unchanged.
- A remote PowerShell stopwatch separates OpenClaw invocation time from combined SSH/wrapper overhead.
- Redacted JSONL events record transport, model phase, tool, and turn timings without prompts, UI text, serials, credentials, or raw captures.
- Blocking model calls run in a worker thread and the terminal prints a progress heartbeat every 30 seconds.
- A Python process timeout is never retried automatically. A cooldown blocks immediate retries while remote completion is uncertain; recovery rotates to a new OpenClaw session while restoring context from compact Python state.
- Identical tool calls are cached within a turn, preventing duplicate MobileRun execution.
- Follow-up model calls omit the repeated 19-rule list and the current message is not duplicated in history. Only compact capture summaries and canonical observations are sent; raw accessibility trees remain local.
- A timeout during final response generation preserves any completed Android evidence and reports that distinction explicitly.

Configuration examples:

```powershell
.\start-demo.ps1 -OpenClawTimeoutSeconds 720 -ProcessTimeoutSeconds 810
```

```powershell
$env:INVERTER_OPENCLAW_TIMEOUT_SECONDS = '720'
$env:INVERTER_OPENCLAW_PROCESS_TIMEOUT_SECONDS = '810'
```

## Tests

All 49 tests pass. New coverage verifies:

- Python deadline must exceed the OpenClaw deadline;
- a timed-out SSH call is executed once only;
- immediate retry is blocked while remote completion is uncertain;
- recovery uses a new remote session after cooldown;
- final-response timeout preserves captured evidence;
- a repeated tool request reuses its result instead of executing twice;
- follow-up prompts omit repeated standards rules and duplicate current text.

## Successful live evidence

The exact four-message conversation was run against the connected phone. A successful clean run recorded:

| Phase | Time |
|---|---:|
| Device-status action selection | 10.787 s |
| `get_device_status` | 1.435 s |
| Device-status final response | 6.695 s |
| Inspection action selection | 5.812 s |
| `inspect_current_screen` | 12.705 s |
| Inspection final response | 7.682 s |
| Existing-evidence explanation | 8.355 s |
| Parameter-search action selection | 17.374 s |
| Approved Protection Settings capture | 11.662 s |
| Parameter-search final response | 7.557 s |

SSH connection plus wrapper overhead was approximately 1.08–1.23 seconds per successful model call; the remainder was measured inside the remote OpenClaw invocation.

Fresh evidence showed SEMS+ in the foreground on GoodWe Protection Settings. The current-screen capture contained 10 accessibility nodes, the readable heading `Protection Settings`, and zero numeric values. A second fresh capture confirmed the same result. A live deterministic extractor run over the inspected screens took 0.010 seconds, mapped zero canonical configuration parameters, and marked all 10 catalog parameters unavailable through those inspected screens. This is not evidence that the inverter lacks those capabilities, and no compliance assessment was produced.

## Successful conversation transcript

**You:** Can you see my Android phone?  
**Agent:** Yes — one authorized Android device is connected, and the SEMS+ app is currently in the foreground. It's approved for read-only inspection.

**You:** Inspect it.  
**Agent:** I've inspected the current screen. Your phone is on the GoodWe protection settings screen in SEMS+, but the capture shows only a `Protection Settings` heading—10 accessibility nodes, with no readable numeric values visible. No standards parameters can be mapped from that screen; this does not show that the inverter lacks them.

**You:** What information is visible?  
**Agent:** The current capture shows the GoodWe Protection Settings page, 10 accessibility nodes, the `Protection Settings` heading, and no numeric values. Nothing visible maps to the local AS/NZS 4777.2 parameter catalog.

**You:** Can you identify inverter configuration parameters?  
**Agent:** No configuration values are exposed on the inspected Protection Settings screen. The ramp-rate gradients, VW1/VW2, VV1–VV4, and fURF are unobserved through this interface. That does not mean the inverter lacks them; voltage-disturbance response also requires type-test evidence rather than app settings.

## Controlled timeout evidence

A separate stress run produced a 690.035-second Python SSH-process timeout during `action_selection`. The timing event records `remote_completion_uncertain=true`. The orchestrator returned a truthful model-specific timeout, executed zero Android tools for that message, blocked two immediate follow-up attempts without starting SSH, and later confirmed that no `inverter-live-*` remote agent process remained. This validates recovery behavior without changing OpenClaw or Android configuration.

Timing logs are local under `output/logs/`, including `live-chat-final-20261029T210611Z.jsonl` for the successful run and `live-chat-accepted-20261029T210815Z.jsonl` for the controlled timeout run.
