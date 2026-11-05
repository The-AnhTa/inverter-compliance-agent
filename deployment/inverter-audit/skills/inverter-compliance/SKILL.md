---
name: inverter-compliance
description: "Use for questions about the bundled inverter parameter catalog, source-checked AS/NZS 4777.2 rules, and the activation-gated deterministic synthetic assessment tool."
allowed-tools: ["read"]
---

# Inverter Compliance Catalog

## Procedure

1. Read `metadata/project_metadata.json` to confirm current integration and validation limits.
2. Read `standards/parameter_catalog.json` for the requested parameter's canonical ID, unit, aliases, and interface assessability.
3. Read `standards/standards_rules.json` for the matching rule. Report only structured values that are actually present.
4. Read `metadata/rule_verification.json` when explaining source-check status or known discrepancies.
5. Cite the rule ID, clause/table, relevant region, expected value or constraint, source filename, and `review_status`.
6. If information is unavailable through an interface, state only that it was not observed. Do not infer missing inverter capability.
7. Check actual tool availability before an assessment. Task E left `assess_inverter_configuration` disabled and the current policy is `read` only, so explain that it cannot currently be invoked and do not simulate a run.
8. State that Android/MobileRun is not configured and that no real inverter has been assessed whenever the question could imply live integration.

## Procedure after a separately verified activation

If and only if `tools.effective` shows exactly `read` and `assess_inverter_configuration`, call the assessment tool once with explicitly synthetic normalized JSON. Do not pass commands, paths, URLs, rules-file selectors, Android actions, or inverter writes. Report its structured classifications unchanged. Treat a supplied `approved_override` as unverified unless the fixed trusted synthetic evidence registry resolves a matching evidence ID.

## Boundaries

- Do not invent requirements or reproduce licensed standards text.
- Do not describe the source-checked rules as validated or use them to claim certification.
- Do not claim access to shell, browser, network, Android, MobileRun, file-writing, sub-agent, or gateway tools. Do not claim the assessment tool is active while it remains disabled.
- Do not change settings or files.
