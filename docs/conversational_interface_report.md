# Conversational Interface Implementation Report

Date: 2026-10-30  
Scope: Windows laptop application only; no OpenClaw, Gateway, agent, plugin, Android-setting, or inverter-setting changes.

## Outcome

The fixed phrase classifier in `client/chat.py` was replaced by a genuine GLM-5.3 conversation loop. Every normal user message is sent through the existing local SSH/OpenClaw adapter. The model returns a schema-constrained decision; laptop Python validates and executes any approved operations, returns their structured results to the model, and displays only the model's natural-language answer.

The loop is bounded to three model rounds and four laptop operations per user turn. A malformed model envelope receives one schema-repair attempt and then fails closed. Each application run uses a fresh private OpenClaw session identifier, while the Python session preserves conversational state for the life of the terminal.

## Conversation memory

The session retains up to 24 recent user/assistant messages and sends the most recent 12 back as context. It also retains the foreground package and app, last inspected screen, fresh capture summaries, observed values and evidence references, confirmed region, latest deterministic assessment, report paths, previous errors, and parameters unavailable through the inspected interface.

Historical GoodWe evidence is stored separately and labelled `historical_not_current`: five screens, 174 accessibility nodes, 15 numeric measurements, zero mapped configuration parameters, and no possible compliance conclusion. A request to inspect again always uses a fresh Portal capture.

## Model-selected operations

Only these laptop operations are exposed:

1. `get_device_status`
2. `inspect_current_screen`
3. `inspect_approved_screen`
4. `get_observed_parameters`
5. `assess_configuration`
6. `generate_report`

The model receives a compact source-grounded index of the 19 local standards rules for ordinary standards explanations. It is instructed not to use OpenClaw-side tools. Compliance decisions remain deterministic: the model cannot create observed values, select an unconfirmed region, perform the comparison itself, or generate a report without an assessment.

## Enforcement boundary

Python accepts exact JSON fields and exact operation names. Approved navigation destinations are limited to Devices, the unique device-detail card, More Control, Protection Settings, and Back. No operation accepts shell text, arbitrary file paths, free-form Android navigation, text entry, toggle/save/apply/reset actions, or inverter control.

The foreground package is checked against the approved package set. Capture verifies the package before and after reading a fresh accessibility tree, rejects malformed/empty/stale data and credential fields, and treats every UI string as untrusted evidence. Reports are written only to the fixed local output directory.

## Verification

`python -m unittest discover -s tests -v` passed all 49 tests. This includes the pre-existing tests plus the exact acceptance Conversations A, B, and C, timeout/recovery coverage, and conversational coverage for:

- model invocation on every normal message and follow-up context retention;
- multiple safe operations and tool-result feedback to the model;
- no assessment or report when observations are absent;
- rejection of unknown navigation, shell-like operations, and caller-supplied report paths;
- one bounded malformed-schema repair;
- natural region-profile wording without silently assuming a region;
- separation of historical evidence from current state.

A real three-turn GLM-5.3 session completed successfully:

1. `Hi.` produced a conversational capability summary.
2. `What did you find previously?` accurately recalled the five-screen/174-node/15-measurement/zero-mapping historical result and labelled it non-current.
3. `Why couldn't you conclude compliance from that?` used the prior turn's context and explained the lack of mapped settings, unconfirmed region, and app-unassessable type-test requirements without fabricating values.

A live action-selection probe asked what app was open. GLM selected `get_device_status` and `inspect_current_screen`; Python executed both and returned their results for a second model response. At verification time, all Portal endpoints returned an accessibility-service error, so both operations failed safely and the final answer explicitly said there was no current evidence. The Android device was authorized and awake, but no accessibility-service or phone setting was changed. A fresh live inspection requires the existing MobileRun Portal accessibility service to be restored manually by the operator.

The one-shot launcher was also verified with `Hi.`. It returned a normal conversational response with no internal JSON. The launcher now prefers the known MobileRun Python environment but can use ordinary local Python for conversation and standards questions when MobileRun is unavailable.
