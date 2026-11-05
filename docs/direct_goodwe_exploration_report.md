# Direct deterministic GoodWe exploration

Date: 30 October 2026 (Australia/Sydney)

## Implementation

`/explore` and `start-demo.ps1 -ExploreGoodWe` execute the laptop-side explorer directly. The launcher branches before constructing `OpenClawClient`; the direct executor has neither a navigation-selector callback nor an ambiguity-resolver callback. Normal natural-language chat remains available separately.

Python ranks only freshly enumerated, package-scoped, clickable navigation candidates. It prioritises grid/protection/safety/configuration routes, derives coordinates from current accessibility bounds, tracks visited fingerprints and attempted routes, scrolls once when a route is exhausted, and backtracks. The total action limit is 20. Save/apply/submit, start/stop, switches, checkboxes, radio buttons, sliders, edit fields, title-bar labels and rows already displaying setting values are excluded.

The live Safety Setting page exposed `Safety Regulation, --`. That value row and its clickable title were preserved as evidence and excluded from navigation because opening them could cross from display into selection/edit behaviour.

## Live result

Command:

```powershell
.\start-demo.ps1 -ExploreGoodWe
```

The completed run performed 20 actual Android actions: 6 taps, 7 swipes and 7 back-button actions. It created 21 fresh accessibility/screenshot captures across 7 unique screen fingerprints. The navigation path included:

- Protection Settings and Safety Setting;
- More Control;
- General Settings and Modbus Settings;
- PV Settings and PID Settings.

The Device Start/Stop control was visible in the control menu but was never a navigation candidate and was not tapped. No save, apply, toggle, setting-value row, credential field or inverter operational control was used.

SEMS+ exposed headings and navigation entries but no numeric configured protection thresholds that map to the ten app-assessable catalog parameters. Several screens were sparse (10–15 accessibility nodes), and screenshots were preserved for each capture. No local OCR engine was installed, so screenshot-only values could not be extracted automatically.

Configuration parameters extracted: **0**. The deterministic compliance engine was therefore not run, and no empty or misleading compliance report was generated. This means only that the inspected SEMS+ screens did not expose assessable values; it does not show that the inverter lacks those capabilities.

Evidence outputs:

- `output/exploration/sems-exploration-20261029T221856Z.md`
- `output/exploration/sems-exploration-20261029T221856Z.json`
- per-screen private JSON trees and PNG screenshots under `output/android/`

All 56 automated tests passed after the live run, including driver-level assertions that scroll invokes MobileRun `swipe` and back invokes `press_button("back")`.
