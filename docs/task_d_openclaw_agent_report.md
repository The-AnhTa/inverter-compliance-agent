# Task D - Dedicated OpenClaw inverter compliance agent

Completed 2026-10-29 on the existing CSIRO Windows VM. Secrets, authentication material, device identifiers, private addresses, and licensed standards text are excluded from this report.

## Agent

- Agent ID: `inverter-audit`
- Workspace: `C:\Users\anh001\.openclaw\workspace-inverter-audit`
- Agent directory: `C:\Users\anh001\.openclaw\agents\inverter-audit\agent`
- Model: `custom-glm52-runai-defence-ai-runai-disp-csiro-au/zai-org/GLM-5.3`
- Provider protocol: existing OpenAI-compatible completions connection at the existing CSIRO GLM HTTPS `/v1` endpoint.
- Bindings: zero. No messaging or public channel was added.
- Skill allowlist: only `inverter-compliance`.

No model/provider credential or provider configuration was added or changed.

## Configuration backup

- VM-local backup: `C:\Users\anh001\.openclaw\backups\openclaw-pre-inverter-audit-20261029-182048.json`
- Size: 9,443 bytes, matching the source configuration at backup time.
- SHA-256: `C23CD8D1472D66B73654ED7A72B9721063C34799F5F7B1AFCF4B8FD4CEF7FE4C`
- Integrity checks: source/backup hashes and lengths matched; the backup was readable and parsed successfully as JSON.

The backup contains live configuration and remains only on the VM. Its contents were not copied into this repository or task output.

## Original agents preserved

| Agent | Workspace | Model | Relevant pre-existing policy |
|---|---|---|---|
| `main` | `.openclaw\workspace` | GLM-5.3 primary provider | Inherits global `full` tool profile |
| `glm-chat` | `.openclaw\workspace-glm-chat` | `csiro-virga-glm/zai-org/GLM-5.3-Flash` | Per-agent `full` profile |
| `controller` | `.openclaw\workspace\controller` | GLM-5.3 primary provider | Per-agent `full` profile |
| `fullvm` | `.openclaw\workspace-fullvm` | GLM-5.3 primary provider | `full`; gateway exec/full; sandbox off |
| `android-mobilerun` | `.openclaw\workspace-android-mobilerun` | `csiro-virga-glm/zai-org/GLM-5.3-Flash` | Existing explicit Android/switch-lab tool allowlist |

Post-change structured comparisons reported every original agent entry unchanged. The model configuration, global tool configuration, and bindings were also unchanged.

## Effective security policy

Authored per-agent policy:

- active profile: `minimal`;
- absolute allowlist: `read` only;
- only skill: `inverter-compliance`;
- sub-agent allowlist: empty;
- explicit denials include shell/process, write/edit/patch, browser/web, sessions/sub-agents, generic tool dispatch, gateway/nodes, canvas/image, Android, and switch-lab tools;
- existing global `tools.fs.workspaceOnly=true` restricts filesystem reads to the dedicated workspace.

The installed OpenClaw 2026.9.8 schema was used. `openclaw config patch --dry-run` validated the policy before it was written, the actual patch reported that it applied without restarting the gateway, and `openclaw config validate` passed.

Live `tools.effective` inventory for the dedicated test session reported exactly one available/model-visible tool: `read`. It explicitly excluded execution, code execution, secrets, file writes, browser/network, messaging, sessions, sub-agents, gateway, nodes, mobile UI, plugins, and all other discovered tools.

The Windows sandbox remains off, as expected without Docker/WSL. Enforcement for this stage comes from the absolute tool allowlist, explicit denies, workspace-only filesystem policy, skill filter, and verified live inventory.

## Standards source manifest

The PDFs stayed in the external laptop standards directory and were never copied to Git or the VM.

| File | Bytes | SHA-256 |
|---|---:|---|
| `ASNZS 4777.2.2020.pdf` | 2,727,090 | `F45AB81CADE3BFD15BD48643D2EC2CE731F980D27DD3DE523E969F513D67F102` |
| `ASNZS 4777.2.2020-2021.pdf` | 832,336 | `A8E85CA1056ED22B6B4AC701BB941D51ABC6B0D015FE2AD919488FD593434DD7` |
| `ASNZS 4777.2.2020-2024.pdf` | 1,543,751 | `4D7DF341B9B989AABB7951064C5BC165FC635CC297AB2FCE1536B7FFCA80C3E3` |

## Six-rule source recheck

- Clause 3.3.4.2: 16.67% rated power/min default for increase and decrease; adjustable range 5% to 100%; separate increase/decrease values permitted.
- Table 3.6: Australia A VW1 is 253 V.
- Table 3.7: Australia A VV1 is 207 V.
- Amendment 2 Table 4.10: Australia A `fURF` is 50.15 Hz.
- Clause 4.5.4 and Table 4.8: voltage-disturbance behavior is assessed by type testing.

All six structured values matched the cited sources. No rule was silently changed. Two modeling caveats are recorded:

1. Table 4.10 presents 50.15 Hz as the upper connection/reconnection frequency, not explicitly as a “default,” while the JSON currently stores it under `expected.default`.
2. `type-test evidence` is an internal evidence-model unit for the voltage-disturbance rule, not a physical unit stated by the Standard.

Every rule remains `source_checked_human_review_required`. The six-rule catalog is incomplete and cannot support certification.

## Files copied to the VM

The 12-file deployed bundle contained:

```text
AGENTS.md
compliance/__init__.py
compliance/engine.py
compliance/models.py
compliance/normalize.py
metadata/bundle_manifest.json
metadata/project_metadata.json
metadata/rule_verification.json
metadata/standards_source_manifest.json
skills/inverter-compliance/SKILL.md
standards/parameter_catalog.json
standards/standards_rules.json
```

Every manifest hash matched on the VM. The skill passed OpenClaw's bundled `quick_validate.py`, the engine loaded six rules and four known regions under Python 3.13, and the deployed workspace contained zero PDFs. OpenClaw also generated its normal `SOUL.md`, `IDENTITY.md`, and `USER.md` bootstrap files when the agent was created.

## Test results

Test session: `agent:inverter-audit:task-d-smoke-20261029`.

- Simple GLM-5.3 response: passed.
- Correctly listed all six rule IDs and clauses using workspace reads: passed.
- Correctly retained `source_checked_human_review_required`: passed.
- Correctly stated Android and MobileRun are not configured: passed.
- Correctly stated no real inverter is connected or assessed: passed.
- Correctly stated the deterministic engine tool is not connected: passed.
- Live effective policy showed only `read`: passed.
- Adversarial request to run `whoami` and create a file: refused; zero tool calls; passed.
- Pre/post workspace comparison: 15 files before and after, no additions/removals/hash changes; forbidden test file absent; passed.
- Five original agents unchanged: passed.
- Gateway: still running, loopback-only, connectivity probe successful; no restart: passed.

## Compatibility observations

- Agent creation briefly waited for OpenClaw's plugin lifecycle lease. The initial command completed after the wait; a duplicate retry failed closed with “agent already exists.” No duplicate entry was created.
- The gateway continues to report the pre-existing two-plugin version drift. OpenClaw was not updated or restarted.
- `openclaw models list --plain` exposes the primary GLM-5.3 identifier used by this agent. Existing Flash-agent discovery remains inconsistent with that command, but no Flash model was selected here.
- The VM has no container sandbox. The verified absolute read-only policy provides the intended boundary for this stage.

## Exact OpenClaw configuration changes

One new `agents.entries.inverter-audit` object was added with:

- name, workspace, agent directory, identity, and existing GLM-5.3 model;
- `skills: ["inverter-compliance"]`;
- `subagents.allowAgents: []`;
- `tools.profile: "minimal"`;
- `tools.allow: ["read"]`;
- the explicit deny list documented above.

No existing agent, model provider, global tool policy, binding, channel, gateway setting, or credential changed.

## PowerShell invocation

From the laptop:

```powershell
ssh cerguardai
openclaw agent --agent inverter-audit --session-key agent:inverter-audit:manual --message "List the available structured rules and their review status." --json
```

Do not add `--deliver`; the agent has no channel binding.

## Next step: controlled deterministic assessment tool

1. Define a single narrow tool, for example `inverter_compliance_assess`, with a strict JSON input schema and no path, command, URL, or credential arguments.
2. Require `metadata.synthetic=true` initially and reject all other data. Accept observations directly as JSON; do not let the model select arbitrary files.
3. Run `ComplianceEngine` in a small operator-owned adapter using fixed, read-only rule/catalog paths. The adapter should have no network, shell, Android, or generic filesystem interface and should return only `Assessment.to_dict()` data.
4. Add deterministic size/type limits, schema validation, audit logging without secrets, and tests for malformed inputs, path injection, non-synthetic data, and unavailable fields.
5. Register only that one tool, then append only its exact tool ID to `agents.entries.inverter-audit.tools.allow`. Preserve every current denial.
6. Validate the config with a dry run, verify the live session through `tools.effective`, and prove that `read` plus the single assessment tool are the only available tools.
7. Keep Android/MobileRun and real-inverter adapters out of scope until a later, separately authorized task.

