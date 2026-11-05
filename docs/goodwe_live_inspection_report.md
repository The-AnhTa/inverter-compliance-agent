# GoodWe live read-only inspection

Date: 30 October 2026 (Australia/Sydney)

## Result

The MobileRun Portal content-provider integration is working against the approved SEMS+ package. Every capture queried `phone_state` immediately before and after `a11y_tree_full`, and every accepted tree belonged exclusively to the approved foreground package.

The complete safe route inspected five screens:

| Screen | Accessibility nodes | Numeric visible values | Interpretation |
|---|---:|---:|---|
| GoodWe dashboard | 64 | 6 | Live generation/grid/load operating data |
| GoodWe devices | 35 | 4 | Device-list status/operating data |
| GoodWe device detail | 38 | 5 | Today/cumulative generation and rated/current power |
| GoodWe control menu | 27 | 0 | Navigation categories only |
| GoodWe protection settings | 10 | 0 | Title/status content; no configured threshold values |
| **Total** | **174** | **15** | **No assessable configuration threshold** |

Readable non-private labels included Energy Generation, Generation Revenue, Grid, Solar, Load, Devices, Today's Generation, Cumulative Generation, Rated Power, Current Power, More Control, PV Settings, Protection Settings and General Settings.

No labels for ramp increase/decrease, VW1/VW2, VV1–VV4 or upper reconnection frequency were exposed. The 15 numeric values were operating/status values and were deliberately not mapped to protection thresholds. The voltage-disturbance response remains not assessable from app settings.

Australia A was treated only as an illustrative comparison profile; actual regional applicability was not confirmed.

## Final acceptance command

```powershell
.\start-demo.ps1 -Once "assess inverter Australia A package com.goodwe.sems.plus"
```

The finalized command accepted a fresh ten-node GoodWe protection-settings tree, found zero visible values and zero canonical mappings, and explicitly reported all ten catalog parameters as unavailable through the inspected screen.

No compliance assessment or Markdown/JSON report was generated. This is intentional: generating a compliance report from dashboard data or an empty parameter page would be misleading. A read-only installer/commissioning parameter display, local inverter interface, or exported configuration containing the actual configured thresholds is required.

No device control, start/stop action, editable field, save, apply, reset, credential, OpenClaw configuration, plugin or Gateway setting was touched. Raw UI trees, screenshots and device identifiers remain local and Git-ignored.
