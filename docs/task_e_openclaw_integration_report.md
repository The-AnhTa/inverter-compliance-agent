# Task E - Deterministic engine integration with OpenClaw

Completed to the safe activation boundary on 2026-10-29. Offline implementation
and verification passed. Live activation was rolled back because the existing
Gateway did not remain reachable through the non-disruptive reload path.

No secret, authentication material, personal account data, licensed standards
text, or private API endpoint details are included here.

## Outcome

- Implemented exactly one tool: `assess_inverter_configuration`.
- OpenClaw 2026.9.8 authoring validation: passed.
- Python tests: 20 passed.
- JavaScript/plugin-wrapper tests: 5 passed locally and 5 passed again on the VM.
- Fixed VM Python runner integrity check and direct synthetic assessment: passed.
- Plugin artifact packing and runtime inspection: passed.
- Live hot reload: failed because the existing Gateway timed out.
- Live GLM end-to-end test: not run; activation gate was not met.
- Final agent policy: restored to `read` only.
- Final plugin state: installed but explicitly disabled.
- Final Gateway health: healthy on the original PID after rollback, without a restart.
- Gateway restart/stop/upgrade: none.
- Android, MobileRun, real inverter, GitHub push: none.

## Implementation

Plugin files:

```text
deployment/openclaw-plugin/
  openclaw.plugin.json
  package.json
  README.md
  schemas/
    assess_inverter_configuration.input.schema.json
    assess_inverter_configuration.output.schema.json
  src/
    index.js
    runtime.js
    schemas.js
  test/
    runtime.test.mjs
```

Python boundary:

```text
integration/openclaw/assessment_runner.py
integration/openclaw/integrity_manifest.json
standards/synthetic_approved_variations.json
```

The plugin uses the installed version's `defineToolPlugin` API. Its schemas reject
unknown fields and bound array/string/value sizes. It accepts only synthetic mode,
fixed normalized parameter names, constrained metadata, one regional profile, and
observations. There are no command, script, executable, path, URL, network,
Android, rules-file, or inverter-write arguments.

The JavaScript wrapper:

- invokes the fixed interpreter
  `C:\Users\anh001\AppData\Local\Programs\Python\Python313\python.exe`;
- invokes the fixed runner with fixed `-I` and no caller-selected arguments;
- uses `shell: false`, a fixed working directory, a controlled environment,
  hidden Windows process creation, a 5-second timeout, 32 KiB input limit,
  256 KiB output limit, and 8 KiB error-output limit;
- sends JSON on standard input and reads JSON on standard output;
- verifies the fixed manifest hash and every engine/rules/runner file before
  spawning Python.

The Python runner independently verifies the manifest entries, rejects malformed
or oversized JSON, rejects unknown fields and unsafe string characters, maps the
schema to the existing `ComplianceEngine`, and performs no network operation.

This plugin still runs trusted code on the OpenClaw Gateway host. It is not an
independent sandbox.

## Engine and standards semantics

The same six source-checked rules remain
`source_checked_human_review_required`; none was marked validated. The engine now
returns the observed unit and the rule constraint alongside its existing rule,
clause, expected value, source reference, and classification.

Preserved classifications and distinctions:

- published default match;
- deviation from a published default without automatically calling it
  noncompliance;
- outside an inclusive permitted range;
- parameter unavailable through the inspected interface without inferring a
  missing inverter capability;
- requirement not assessable from configuration alone;
- approved variation only when a fixed trusted synthetic evidence record matches;
- approval claimed but not verified;
- unknown/unsupported regional configuration.

Hard range checks occur before approved-variation handling. A model/user supplied
`approved_override` is only an unverified claim. The fixed synthetic evidence
registry is separate from caller input and cannot represent real distributor
approval.

The Table 4.10 caveat remains explicit: 50.15 Hz is presented by the source as
the upper connection/reconnection frequency while the current rule model stores
it under `expected.default`. The voltage-disturbance result also carries the
caveat that `type-test evidence` is an internal evidence abstraction, not a
physical source unit.

The catalog is still only a six-rule demonstration and cannot support
certification.

## Deterministic tests

`python -m unittest discover -s tests -v` covered:

1. correct synthetic values;
2. deviation and outside-range values;
3. missing parameter;
4. unknown region;
5. unit mismatch;
6. malformed JSON and unexpected fields;
7. oversized JSON;
8. shell-command and path injection attempts;
9. an unverified approved override;
10. fixed trusted synthetic approval evidence;
11. all original Task C demonstrations.

`node --test deployment/openclaw-plugin/test/runtime.test.mjs` covered schema
strictness, direct plugin-to-Python integration, pre-spawn size limits, child
process failure, and timeout termination. No dependency was installed globally.

## Installed-version compatibility findings

- A direct `registerTool` entry can load but is rejected by the 2026.9.8 authoring
  validator. The final plugin uses that version's `defineToolPlugin` interface.
- Generated manifest metadata is mandatory; `plugins build` generated and
  `plugins validate` accepted it.
- Artifact packing requires esbuild and rejects dynamic module-relative resource
  reads. The existing OpenClaw-bundled esbuild 0.28.2 was linked only inside the
  temporary staging tree; schemas use static JSON imports that the packer embeds.
- The packed artifact declares exactly the one accepted tool surface and no
  additional capabilities.
- Runtime inspection reports the local archive as `provenance-invalid`. This is
  another operational limitation for a future production deployment even though
  the accepted surface hash was recorded.
- Plugin lifecycle commands repeatedly waited on the installed lifecycle lease.
  The disabled install copied successfully, but the live reload then timed out
  against the Gateway.

## VM locations

```text
Agent workspace:
C:\Users\anh001\.openclaw\workspace-inverter-audit

Runner:
C:\Users\anh001\.openclaw\workspace-inverter-audit\integration\openclaw\assessment_runner.py

Integrity manifest:
C:\Users\anh001\.openclaw\workspace-inverter-audit\integration\openclaw\integrity_manifest.json

Installed disabled plugin:
C:\Users\anh001\.openclaw\extensions\inverter-compliance-tool

Temporary packed artifact:
C:\Users\anh001\AppData\Local\Temp\inverter-compliance-tool-0.1.0-task-e-03.tgz
```

Artifact SHA-256:
`116b2e47dfc96631e163d02d698fe36a2a5a5efd8173a338dcdc6d032d7ee65d`.

The repository and VM agent workspace contain zero PDFs.

## Backup and integrity

Configuration backup:

```text
C:\Users\anh001\.openclaw\backups\openclaw-pre-task-e-20261029-190332.json
```

- Source and backup size: 10,564 bytes.
- SHA-256:
  `6D034EF7477502AC799E5F52454167CD4CB7C4E85EA727F20B9835C5B776F5C2`.
- Length/hash comparison and JSON parse: passed.

Workspace backup:

```text
C:\Users\anh001\.openclaw\backups\workspace-inverter-audit-pre-task-e-20261029-190332
```

It contains the 12 pre-Task-E deployed files (29,944 bytes). The fixed runner
manifest has SHA-256
`25B1A4A042D7DB2DAA4F0B3DE294376D8979625C8713DE9A656588E60631BC24`,
matching locally and on the VM.

## Effective tool-policy verification

Before activation, live saved-session inspection reported:

| Agent | Profile | Available tools in inspected session |
|---|---|---:|
| `main` | `full` | 55 |
| `glm-chat` | `full` | 55 |
| `controller` | `full` | 55 |
| `fullvm` | `full` | 55 |
| `android-mobilerun` | `full` | 0 in the selected cron-session snapshot |
| `inverter-audit` | `minimal` | exactly `read` |

The Android agent's configured allowlist was preserved; the zero count describes
only the selected saved cron-session snapshot.

The desired live post-activation set of exactly `read` and
`assess_inverter_configuration` was not verified because the Gateway stopped
answering before reload. After rollback, both file-level comparison and recovered
live `tools.effective` checks showed the original saved-session policies:
`inverter-audit` had exactly `read`; the four inspected full-profile agents still
reported 55 tools; the selected Android cron-session snapshot still reported
zero. None exposed `assess_inverter_configuration`. Models, global tools, and
bindings were unchanged.

## Gateway and end-to-end status

The activation patch passed dry-run and live config validation. The config writer
reported that it did not require a restart. `plugins reload` then timed out at
`ws://127.0.0.1:18789`.

The same pre-existing Gateway PID 1136 remained listening on loopback while health
requests initially timed out. After the rollback, it recovered without a restart.
The final health call completed in 35 ms, reported active config hot reload and no
plugin errors, and did not list the disabled inverter plugin as loaded. No restart,
stop, process termination, update, or scheduled task change was performed.

Because safe activation failed, the GLM-5.3 end-to-end tool call was not attempted.
See `docs/task_e_end_to_end_transcript.md` for the exact completed and blocked
stages.

## Final configuration diff and rollback

Temporary activation changes were fully rolled back. Compared with the pre-Task-E
configuration, the only final config addition is:

```json
{
  "plugins": {
    "entries": {
      "inverter-compliance-tool": {"enabled": false}
    }
  }
}
```

All agent entries, model configuration, global tool configuration, and bindings
match the pre-Task-E backup.

To remove even the explicit disabled entry after the Gateway is healthy, validate
then apply this narrow patch:

```json
{"plugins":{"entries":{"inverter-compliance-tool":null}}}
```

The full config can instead be restored from the verified backup only during a
coordinated maintenance window and only after confirming no later legitimate
config changes would be overwritten. The workspace can be restored from the
workspace backup, and the installed plugin can be uninstalled, but those
destructive cleanup steps were intentionally not performed while the Gateway was
unhealthy.

## Exact next steps

1. Under a separate maintenance instruction, diagnose the transient reload timeout,
   lifecycle-lease behavior, and existing plugin version drift; authorize a
   restart only if needed.
2. Confirm Gateway health before touching plugin state.
3. Replace the local-archive provenance with an internally approved artifact if
   required by CSIRO policy.
4. Re-run installed runtime inspection and config dry-run.
5. Enable only `inverter-compliance-tool`, allow only the exact tool ID for
   `inverter-audit`, and use the supported reload path if it is healthy.
6. Create a fresh `inverter-audit` test session and verify `tools.effective` is
   exactly `read, assess_inverter_configuration`; verify the other five agents are
   unchanged.
7. Run the synthetic GLM tool-call test and compare the structured result byte-for-
   structure with a direct fixed-runner evaluation before accepting activation.
8. Update the skill's `allowed-tools` to include the tool only after that live
   verification.
9. MobileRun remains a later, separately authorized phase: design a read-only
   observation adapter, preserve unavailable-field semantics, prohibit inverter
   writes, and run synthetic/dummy-app tests before any real device or inverter.

Task E stops here. Android and inverter integration were not started.
