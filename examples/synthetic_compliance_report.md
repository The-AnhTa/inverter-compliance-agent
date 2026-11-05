# Synthetic inverter compliance assessment

> **SYNTHETIC DATA - NOT A REAL INVERTER ASSESSMENT.**

- Dataset: `SYNTHETIC-DEMO-A-001`
- Region: `Australia A`
- Inspected interface: `synthetic inverter settings app`
- Rules are source-checked but require independent human validation before operational use.

## Summary

| Outcome | Count |
|---|---:|
| compliant | 1 |
| compliant_with_approved_variation | 1 |
| deviation_from_default | 1 |
| not_assessable_from_app_settings | 1 |
| not_observed | 5 |
| outside_permitted_range | 1 |

## Findings

| Rule | Clause | Parameter | Observed | Outcome | Evidence | Explanation |
|---|---|---|---|---|---|---|
| AS4777-3.3.4.2-INCREASE | 3.3.4.2 | power_rate_limit_gradient_increase | 16.67 | compliant | N/A | Observed value matches the standards default. |
| AS4777-3.3.4.2-DECREASE | 3.3.4.2 | power_rate_limit_gradient_decrease | 2 | outside_permitted_range | N/A | Observed value is outside the permitted inclusive range 5 to 100 % rated power/min. |
| AS4777-3.3.2.2-A-VW1 | 3.3.2.2 / Table 3.6 | volt_watt_vw1 | 250 | deviation_from_default | N/A | Observed value is within any stated constraint but differs from the standards default; approval evidence was not supplied. |
| AS4777-3.3.2.2-A-VW2 | 3.3.2.2 / Table 3.6 | volt_watt_vw2 | N/A | not_observed | {"availability": "not_supplied"} | The parameter was unavailable through the inspected interface; capability absence is not inferred. |
| AS4777-3.3.2.3-A-VV1 | 3.3.2.3 / Table 3.7 | volt_var_vv1 | 210 | compliant_with_approved_variation | {"approval_reference": "SYNTHETIC-DISTRIBUTOR-APPROVAL-001", "approval_verified": true, "evidence_id": "SYNTHETIC-EVIDENCE-AU-A-VV1-210"} | Observed value differs from the published value and matches verified approved-variation evidence. |
| AS4777-3.3.2.3-A-VV2 | 3.3.2.3 / Table 3.7 | volt_var_vv2 | N/A | not_observed | {"availability": "not_supplied"} | The parameter was unavailable through the inspected interface; capability absence is not inferred. |
| AS4777-3.3.2.3-A-VV3 | 3.3.2.3 / Table 3.7 | volt_var_vv3 | N/A | not_observed | {"availability": "not_supplied"} | The parameter was unavailable through the inspected interface; capability absence is not inferred. |
| AS4777-3.3.2.3-A-VV4 | 3.3.2.3 / Table 3.7 | volt_var_vv4 | N/A | not_observed | {"availability": "not_supplied"} | The parameter was unavailable through the inspected interface; capability absence is not inferred. |
| AS4777-4.7-A-FURF | 4.7 / Table 4.10 | upper_connection_reconnection_frequency | N/A | not_observed | {"availability": "unavailable_through_inspected_interface", "modeling_caveat": "Table 4.10 presents 50.15 Hz as the upper connection and reconnection frequency; the current data model stores that published value under expected.default."} | The parameter was unavailable through the inspected interface; capability absence is not inferred. |
| AS4777-4.5.4-VOLTAGE-DISTURBANCE | 4.5.4 / Table 4.8 | voltage_disturbance_response | N/A | not_assessable_from_app_settings | {"modeling_caveat": "The unit 'type-test evidence' is an internal evidence-model abstraction, not a physical unit stated by the Standard."} | This requirement needs evidence beyond app settings (for example, type-test evidence). |

## Interpretation limits

An unavailable app field means only that the inspected interface did not expose it. It does not show that the inverter lacks the capability. Requirements assigned to type testing cannot be concluded from app settings. Approved variations require authentic distributor/operator evidence in a future controlled workflow; this demonstration uses a clearly synthetic reference.
