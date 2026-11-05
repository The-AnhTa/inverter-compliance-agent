# Inverter Compliance Tool

OpenClaw 2026.9.8 native tool plugin exposing exactly one model-facing tool:
`assess_inverter_configuration`.

The live runtime uses a fixed Python interpreter, runner, workspace, and integrity
manifest. Input is JSON on standard input; output is JSON on standard output. No
shell is invoked. The plugin and Python path perform no network or Android work.

This plugin executes trusted local code on the OpenClaw Gateway host. It is not an
independent sandbox and must remain restricted to the `inverter-audit` agent.
