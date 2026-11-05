# Task E-M - OpenClaw assessment-tool activation report

Date: 2026-10-30 (Australia/Sydney)  
Environment: existing CSIRO Windows VM, OpenClaw 2026.9.8  
Scope: one authorized non-restart activation attempt with verified rollback

No credential, authentication material, personal account data, licensed standards
content, or raw secret-bearing configuration is included in this report.

## Outcome

- The Task E timeout was not a demonstrated plugin activation failure. The saved
  activation configuration was eventually applied by the running Gateway after
  the CLI had timed out.
- The best-supported cause is a long Gateway host/event-loop timing gap during
  plugin replacement. It made loopback WebSocket health and reload calls
  temporarily unresponsive for longer than the CLI deadline.
- The plugin is installed under ID `inverter-compliance-tool`, selects the
  expected `dist/index.js`, and declares exactly
  `assess_inverter_configuration`.
- The authorized non-restart lifecycle activation completed and registered the
  tool, but runtime policy verification found that all four original
  full-profile agents also received it. That violated the requirement to expose
  the tool only to `inverter-audit`.
- The inverter allowlist was therefore never changed, no agent/model tool call
  was attempted, and the plugin was disabled using the tested rollback path.
- A Gateway restart is not currently justified. There is no demonstrated plugin
  registration defect to repair.
- Final recovery is verified: the saved configuration is byte-for-byte identical
  to the fresh backup, all six effective policies match their pre-attempt state,
  the Gateway is healthy on unchanged PID 1136, and the plugin is disabled.

## Task E timeout diagnosis

The relevant Gateway log sequence is:

| Local time | Evidence |
|---|---|
| 19:12:30.950 | The two saved config updates were accepted without requiring a restart. |
| 19:12:32.588 | The Gateway detected changes to the inverter agent allowlist and plugin entry. |
| 19:13:09.701 | The CLI reported `ETIMEDOUT` to `ws://127.0.0.1:18789`. |
| 19:14:13.781 | Gateway liveness reported a 94,030 ms overdue heartbeat and 124,030 ms elapsed interval. |
| 19:14:13.782 | The Gateway reported that its process had been frozen for approximately 93,444 ms. |
| 19:14:13.795 | Channel recovery was deferred because the Gateway still reported active work. |
| 19:14:15.213 | `Plugin replacement applied: inverter-compliance-tool`. |
| 19:14:16.110 | The activation config hot reload was applied. |
| 19:14:16.165 | File configuration source revision 6 was accepted. |
| 19:14:41.582 | The later rollback change was detected. |
| 19:15:29.329 | A second 45,549 ms overdue heartbeat occurred during rollback replacement. |
| 19:15:30.239 | Rollback plugin replacement was applied. |
| 19:15:31.188 | The rollback config hot reload was applied. |
| 19:15:31.235 | File configuration source revision 7 was accepted. |

This sequence rules out several suspected causes:

- **Activation/import error:** no plugin error was logged, and replacement was
  explicitly reported as applied.
- **Configuration publication failure:** activation revision 6 and rollback
  revision 7 were both accepted.
- **Gateway process exit:** PID 1136 continued to own the listening port.
- **Required restart:** both the writer and hot-reload subsystem treated the
  change as restart-free.
- **Lifecycle lease at activation:** lifecycle-lease waiting was logged earlier
  during installation, but not in the activation interval.
- **Known active session as the root cause:** the log says active work existed,
  but does not identify it as an agent session. Current inspection finds no
  sessions updated within two hours. The repeated timing gap during both enable
  and disable replacement points more strongly to the plugin replacement path.

The precise low-level source of the Windows process freeze is not proven. It may
not be relabelled as a plugin-code defect, session defect, or lifecycle-lease
defect without additional evidence. The operational root cause is that the
Gateway's plugin replacement work blocked or was descheduled long enough for the
client deadline to expire.

The Task E explicit `plugins reload` call was therefore poorly timed: the config
write had already triggered automatic runtime replacement, while the Gateway was
unresponsive inside that work. Repeating that command or merely increasing its
timeout would not address the observed condition.

## Plugin identity and registration state

| Field | Observed state |
|---|---|
| Plugin ID | `inverter-compliance-tool` |
| Package version | `0.1.0` |
| Built for | OpenClaw 2026.9.8 |
| Selected module | `C:\Users\anh001\.openclaw\extensions\inverter-compliance-tool\dist\index.js` |
| Install source | reviewed local archive |
| Trust marker | `provenance-invalid` for the local archive |
| Saved state | explicitly disabled |
| Runtime state | disabled, not imported, not activated |
| Declared contract | exactly `assess_inverter_configuration` |
| Other capabilities | none |
| Hooks/services/routes | zero |
| Diagnostics | none |

The persisted plugin registry reports `stale` with reason `policy-changed`, but
reports no registry differences. Its target manifest, module path, version,
install record, and accepted one-tool surface are present and consistent. This
does not demonstrate a registration defect and is expected to be reconciled by
the supported lifecycle operation; an unrequested `registry --refresh` was not
performed.

The local-archive trust marker remains a production-governance issue. It does
not explain the Task E timeout because the surface was accepted at install and
the Gateway later applied the replacement without a trust error.

## Saved versus applied configuration

Current saved config projection:

- `plugins.entries.inverter-compliance-tool.enabled = false`
- `agents.entries.inverter-audit.tools.profile = minimal`
- `agents.entries.inverter-audit.tools.allow = ["read"]`
- file size: 10,634 bytes
- SHA-256:
  `E17FF14FDB4B4E458F178353D09DD95FFB68C2FC3B4099A3061529852526540C`
- last write: 2026-10-29 19:14:39 +11:00

The last accepted Gateway configuration source is rollback revision 7, logged at
19:15:31.235 after that file write. Current health reports active config hot
reload, no plugin errors, and does not list the disabled plugin as loaded. The
live effective policy also reports only `read` for `inverter-audit`. Together,
these observations support that the running Gateway matches the saved rollback
state. No pending, failed, or recovering config reload is visible.

## Gateway ownership and health

- Scheduled Task: `\OpenClaw Gateway`
- Scheduled Task state: Running
- listener: `127.0.0.1:18789`
- process: `node.exe`, PID 1136, parent PID 2252
- health before the authorization stop: healthy in 15 ms
- event loop: not degraded
- plugin errors/unavailable plugins: none
- config hot reload: active
- process restart, stop, upgrade, or Scheduled Task change in Task E-M: none

Session inventory found zero stored sessions updated during the preceding 120
minutes across all six agents. This is useful evidence but does not replace an
operator's confirmation that no critical external operation is in progress.

## Effective tool policies

Live `tools.effective` was queried against the same saved-session snapshots used
for the Task E baseline:

| Agent | Profile | Available tools | Assessment tool present |
|---|---|---:|---|
| `main` | full | 55 | no |
| `glm-chat` | full | 55 | no |
| `controller` | full | 55 | no |
| `fullvm` | full | 55 | no |
| `android-mobilerun` | full | 0 in the selected cron snapshot | no |
| `inverter-audit` | minimal | exactly `read` | no |

The Android zero count describes that selected stored cron-session snapshot; its
saved allowlist was not changed.

## Engine, schemas, and artifact verification

- Fixed VM integrity manifest SHA-256:
  `25B1A4A042D7DB2DAA4F0B3DE294376D8979625C8713DE9A656588E60631BC24`.
- All eight manifest file hashes match on the VM.
- Local Python suite: 20 tests passed.
- Local JavaScript wrapper suite, with its required fixed Python environment:
  5 tests passed.
- Fixed VM runner accepted the explicitly synthetic Task E request and returned
  six results:
  `compliant`, `deviation_from_default`, `compliant`,
  `compliant_with_approved_variation`, `not_observed`, and
  `not_assessable_from_app_settings`.
- Activation dry-run: two operations, schema valid, resolvability complete, no
  configuration write.
- Current config validation: valid with no warnings.

An initial maintenance verification invocation omitted the JavaScript harness's
required `TASK_E_PYTHON_PATH` and referenced a fixture not deployed in the VM
workspace. Those invocation errors were corrected; the properly configured
tests and fixed-runner check above passed.

## Authorized activation attempt and discovered blocker

Alternative **A** was exercised once. Alternatives **B** and **C** were not used.

Final preflight established:

1. Gateway PID 1136 was healthy and its event loop was not degraded.
2. No session had been updated during the preceding 30 minutes.
3. Config validation, all eight integrity hashes, and all six baseline effective
   policies passed.
4. Agent entries, models, global tools, and bindings matched the Task E baseline.
5. A fresh configuration backup was created, parsed, length-checked, and
   hash-checked.

The one activation command was:

```text
openclaw plugins enable inverter-compliance-tool --accept-capabilities
```

It completed successfully after approximately 90 seconds. No concurrent reload
was issued. Runtime inspection reported the plugin loaded and imported with
exactly `assess_inverter_configuration`, no hooks, services, routes, or plugin
diagnostics. Gateway log evidence was:

| Local time | Evidence |
|---|---|
| 06:00:13.257 | Waiting on the global plugin lifecycle lease. |
| 06:00:14.354 | The plugin enabled-state change was detected. |
| 06:00:49.032 | Plugin replacement was applied. |
| 06:00:49.831 | Config hot reload was applied. |
| 06:00:50.209 | Config source revision 10 was accepted. |
| 06:00:51.816 | The lifecycle command reported the plugin enabled. |

Live `tools.effective` then revealed the acceptance blocker:

| Agent | Pre-attempt tools | Enabled-plugin tools | Assessment tool |
|---|---:|---:|---|
| `main` | 55 | 56 | unexpectedly available |
| `glm-chat` | 55 | 56 | unexpectedly available |
| `controller` | 55 | 56 | unexpectedly available |
| `fullvm` | 55 | 56 | unexpectedly available |
| `android-mobilerun` | 0 | 0 | excluded by its allowlist |
| `inverter-audit` | exactly `read` | exactly `read` | not yet allowlisted |

The installed SDK confirms that the plugin registered the tool with
`optional: true`. In OpenClaw 2026.9.8, however, a full tool profile includes
that optional plugin tool; `optional` is not an agent-scoping mechanism. The
registration API exposes only `name`, `names`, and `optional` options and has no
per-agent selector. Meeting the requested scope with the current artifact would
therefore require changing the original agents/global policy, or rebuilding the
plugin with a context-aware tool factory. Neither was authorized.

Because runtime policy verification occurred before the inverter allowlist
patch, the five original agent configurations and all global policy remained
unchanged. The transient broad runtime exposure was removed by rollback before
any agent session or tool call was run.

## Rollback execution and verification

Because the inverter allowlist had not been changed, rollback required only the
supported lifecycle disable command. No second activation or restart was used.
The equivalent complete baseline patch remains:

```json
{
  "plugins": {
    "entries": {
      "inverter-compliance-tool": {"enabled": false}
    }
  },
  "agents": {
    "entries": {
      "inverter-audit": {
        "tools": {"allow": ["read"]}
      }
    }
  }
}
```

Observed rollback evidence:

| Local time | Evidence |
|---|---|
| 06:03:22.777 | Waiting on the global plugin lifecycle lease. |
| 06:03:23.895 | The plugin disabled-state change was detected. |
| 06:04:00.488 | Plugin replacement was applied. |
| 06:04:01.224 | Config hot reload was applied. |
| 06:04:01.332 | Config source revision 14 was accepted. |
| 06:04:02.725 | The lifecycle command reported the plugin disabled. |

Post-rollback verification found the plugin disabled and absent from the final
health loaded list, exactly `read` for `inverter-audit`, baseline policies for
the original agents, no active sessions, no plugin errors, and no pending,
failed, or recovering reload. The current config and fresh backup have identical
length and SHA-256; agent entries, models, global tools, and bindings all match.

Existing Task E backup (not a substitute for the required fresh backup):

`C:\Users\anh001\.openclaw\backups\openclaw-pre-task-e-20261029-190332.json`

Its recorded SHA-256 is
`6D034EF7477502AC799E5F52454167CD4CB7C4E85EA727F20B9835C5B776F5C2`.

Fresh Task E-M backup:

`C:\Users\anh001\.openclaw\backups\openclaw-pre-task-em-activation-20261030-055907.json`

- length: 10,634 bytes
- SHA-256:
  `E17FF14FDB4B4E458F178353D09DD95FFB68C2FC3B4099A3061529852526540C`
- JSON parse and source length/hash equality: passed

## Authorization, activation, and end-to-end status

- Maintenance window explicitly authorized: **yes**.
- Activation attempts made in Task E-M: **exactly one**.
- Plugin lifecycle activation: **succeeded**.
- Required agent-only activation acceptance: **failed because four original
  full-profile agents also received the tool**.
- Rollback: **succeeded and verified**.
- Final configuration difference from the fresh backup: **none; byte-for-byte
  identical**.
- Gateway PID before/after activation and rollback: **1136 / 1136**.
- Final Gateway health: **healthy in 14 ms**, no plugin errors or unavailable
  plugins, active hot reload, non-degraded event loop.
- Final effective policies: **55 / 55 / 55 / 55 / 0 / exactly `read`**, matching
  the baseline for `main`, `glm-chat`, `controller`, `fullvm`,
  `android-mobilerun`, and `inverter-audit` respectively.
- End-to-end GLM synthetic test: **not run**. The required tool set was never
  safely achieved, so running an agent session would have violated the task's
  acceptance gate. The fixed Python runner's six-result synthetic test remained
  successful during preflight.
- Android, MobileRun, real inverter, external production data, Gateway restart,
  global policy change, dependency install, and GitHub push: **none**.

## Outstanding issues and recommendation

1. The existing artifact cannot meet agent-only exposure while the four original
   agents retain unrestricted full profiles. A separate implementation task is
   needed to build and test a context-aware tool factory that returns the tool
   only for `inverter-audit`, or an explicitly approved policy redesign is
   required. Do not reactivate the current artifact as-is.
2. The long Windows plugin-replacement timing gap remains an operational risk.
   The attempt must be observed through accepted config revision and runtime
   state rather than judged only by a client timeout.
3. The local archive's `provenance-invalid` trust marker should be replaced by an
   internally approved artifact provenance before production use if CSIRO policy
   requires it.
4. The standards catalog remains a six-rule demonstration with human review
   required; it is not a certification system.

Do not begin MobileRun integration. First complete a separately authorized
agent-scoping fix, repeat offline/plugin tests, obtain a new activation approval,
and produce actual synthetic GLM invocation evidence. Any later MobileRun task
must preserve unavailable-field semantics, prohibit inverter writes, and use
synthetic/dummy-app verification before real device or inverter interaction.
