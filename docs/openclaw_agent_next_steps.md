# Exact next steps for a dedicated OpenClaw agent

These steps were **not executed**. Perform them only after a separate instruction authorizes the OpenClaw phase.

1. Have a qualified standards reviewer validate each JSON rule against the licensed documents, record reviewer/date/evidence, and decide how approved distributor/operator variations will be authenticated. Do not change `review_status` to `validated` without that review.

2. Transfer or clone this repository into a user-writable VM path. From laptop PowerShell, one local-only option is:

   ```powershell
   scp -r "$env:USERPROFILE\Downloads\inverter-compliance-agent" cerguardai:inverter-compliance-agent
   ```

3. Verify the standalone code on the VM without calling any model or device:

   ```powershell
   ssh cerguardai
   Set-Location "$env:USERPROFILE\inverter-compliance-agent"
   python -m unittest discover -s tests -v
   python -m reports.generate_report tests/fixtures/synthetic_demo.json examples/synthetic_compliance_report.md
   ```

4. Confirm the intended model identifier still exists and resolve the current Flash-agent/model-list discrepancy before agent creation:

   ```powershell
   openclaw --version
   openclaw models list --plain
   openclaw agents list
   openclaw gateway status
   ```

   Do not restart the gateway as part of this check.

5. Prepare a separate agent workspace and review its guardrails:

   ```powershell
   $projectPath = Join-Path $env:USERPROFILE 'inverter-compliance-agent'
   $agentWorkspace = Join-Path $env:USERPROFILE '.openclaw\workspace-inverter-compliance'
   New-Item -ItemType Directory -Path $agentWorkspace -Force | Out-Null
   Copy-Item -LiteralPath (Join-Path $projectPath 'docs\openclaw\AGENTS.template.md') -Destination (Join-Path $agentWorkspace 'AGENTS.md')
   Get-Content -LiteralPath (Join-Path $agentWorkspace 'AGENTS.md')
   ```

6. After explicit approval, add the isolated agent using the model already proven on the default agent:

   ```powershell
   openclaw agents add inverter-compliance `
     --workspace "$env:USERPROFILE\.openclaw\workspace-inverter-compliance" `
     --model "custom-glm52-runai-defence-ai-runai-disp-csiro-au/zai-org/GLM-5.3" `
     --non-interactive `
     --json
   openclaw agents list
   ```

7. Run a synthetic-only smoke prompt that asks the new agent to execute the unit tests and render the included fixture. Inspect local output for secret leakage and unsupported compliance claims. Keep the agent unbound to channels and do not add MobileRun, ADB, or inverter tools.

8. Only in a later, separately authorized phase, design a read-only adapter for a dummy app interface. Require an evidence-capture schema, explicit package allowlist, no setting mutation, and a human approval gate before considering any real inverter workflow.

