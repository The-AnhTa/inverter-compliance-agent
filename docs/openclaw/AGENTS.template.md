# Inverter compliance agent boundaries

Work only with the standalone inverter-compliance-agent repository and local synthetic JSON unless the operator gives a separate, explicit integration instruction.

- Run deterministic Python assessment and report commands locally.
- Treat `standards/standards_rules.json` as human-review-required, not validated.
- Never claim certification or final regulatory compliance.
- Do not retrieve, reproduce, or commit licensed standards PDFs.
- Do not expose credentials, authentication files, device identifiers, or personal data.
- Do not use cloud LLM or MobileRun services.
- Do not connect to or change a real inverter.
- Do not change Android settings or launch device automation.
- Do not alter or restart the OpenClaw gateway or other agents.
- Preserve the meaning of unavailable fields: interface non-observation is not evidence of missing capability.

