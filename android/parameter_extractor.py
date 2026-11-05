"""Evidence-preserving extraction of canonical parameters from captured UI text."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


class ExtractionError(ValueError):
    pass


NUMBER = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(Hz|V|%/min|% rated power/min)?", re.I)
GOODWE_ALIASES = {
    "power_rate_limit_gradient_increase": [
        "Ramp Up Rate", "Active Power Ramp Up", "Power Ramp Rate Increase", "WGra",
    ],
    "power_rate_limit_gradient_decrease": [
        "Ramp Down Rate", "Active Power Ramp Down", "Power Ramp Rate Decrease", "WGrd",
    ],
    "volt_watt_vw1": ["VW1", "Volt-Watt V1", "P(U) V1", "Volt Watt Point 1"],
    "volt_watt_vw2": ["VW2", "Volt-Watt V2", "P(U) V2", "Volt Watt Point 2"],
    "volt_var_vv1": ["VV1", "Volt-Var V1", "Q(U) V1", "Volt Var Point 1"],
    "volt_var_vv2": ["VV2", "Volt-Var V2", "Q(U) V2", "Volt Var Point 2"],
    "volt_var_vv3": ["VV3", "Volt-Var V3", "Q(U) V3", "Volt Var Point 3"],
    "volt_var_vv4": ["VV4", "Volt-Var V4", "Q(U) V4", "Volt Var Point 4"],
    "upper_connection_reconnection_frequency": [
        "fURF", "Upper Reconnection Frequency", "Reconnect Upper Frequency",
        "Reconnect High Frequency", "Reconnection Frequency High",
    ],
}
LIVE_MEASUREMENT = re.compile(
    r"(?i)real.?time|live|current (?:power|voltage|frequency)|grid (?:power|voltage|frequency)|"
    r"pv\d* (?:power|voltage|current)|today(?:'s)? (?:yield|generation)|daily energy|load power"
)


class ParameterExtractor:
    def __init__(self, catalog_path: Path, ambiguity_resolver: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        document = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.parameters = document["parameters"]
        self.ambiguity_resolver = ambiguity_resolver
        self.last_diagnostics: dict[str, Any] = {}

    def extract_page(self, capture: dict[str, Any]) -> list[dict[str, Any]]:
        screen = str(capture.get("current_screen") or "unknown")
        items = [item for item in capture.get("ui_text", []) if isinstance(item, dict)]
        contexts: list[str] = []
        for item in items:
            values = [
                item.get("text", ""), item.get("content_description", ""), item.get("hint", ""),
                *item.get("ui_context", {}).get("sibling_text", []),
            ]
            contexts.append(" ".join(str(value) for value in values if value).strip())
        combined = "\n".join(contexts)
        if "dashboard" in screen.casefold():
            self.last_diagnostics = {
                "current_screen": screen,
                "parameter_labels_found": [],
                "canonical_parameters_mapped": [],
                "rejected_live_measurements": True,
                "reason": "Dashboard operating measurements are not configuration thresholds.",
            }
            return []
        observations: list[dict[str, Any]] = []
        labels_found: list[str] = []
        for parameter in self.parameters:
            aliases = [
                parameter["label"], *parameter.get("aliases", []),
                *GOODWE_ALIASES.get(parameter["id"], []),
            ]
            matches = [
                alias for alias in aliases
                if re.search(rf"(?i)(?<!\w){re.escape(alias)}(?!\w)", combined)
            ]
            if not matches:
                continue
            snippets = [
                line for line in contexts
                if any(re.search(rf"(?i)(?<!\w){re.escape(alias)}(?!\w)", line) for alias in matches)
                and not LIVE_MEASUREMENT.search(line)
            ]
            if not snippets:
                continue
            labels_found.extend(alias for alias in matches if alias not in labels_found)
            value_snippets = []
            for snippet in snippets:
                cleaned = snippet
                for alias in sorted(matches, key=len, reverse=True):
                    cleaned = re.sub(rf"(?i)(?<!\w){re.escape(alias)}(?!\w)", " ", cleaned)
                value_snippets.append(cleaned)
            values = [NUMBER.search(snippet) for snippet in value_snippets]
            parsed = [(float(match.group(1)), match.group(2)) for match in values if match]
            if len({value for value, _ in parsed}) != 1:
                # A label without any explicit numeric value is unavailable,
                # not a reason to ask a model to invent or infer a setting.
                if not parsed or self.ambiguity_resolver is None:
                    observations.append(self._uncertain(parameter, capture, snippets, "ambiguous_or_missing_value"))
                    continue
                candidate = self.ambiguity_resolver({"parameter": parameter, "snippets": snippets})
                self._validate_resolution(candidate, parameter["id"])
                value, observed_unit = candidate["value"], candidate.get("unit")
                confidence = candidate.get("confidence", "low")
            else:
                value, observed_unit = parsed[0]
                confidence = "high"
            observations.append({
                "parameter": parameter["id"], "value": value,
                "unit": observed_unit or parameter["unit"], "availability": "available",
                "source_interface": f"Android UI: {capture.get('package', 'unknown')}",
                "metadata": self._evidence(
                    capture, confidence, snippets, original_label=matches[0]
                ),
            })
        self.last_diagnostics = {
            "current_screen": screen,
            "parameter_labels_found": labels_found,
            "canonical_parameters_mapped": [item["parameter"] for item in observations if item["availability"] == "available"],
            "rejected_live_measurements": bool(LIVE_MEASUREMENT.search(combined)),
        }
        return observations

    @staticmethod
    def _evidence(
        capture: dict[str, Any],
        confidence: str,
        snippets: list[str],
        original_label: str | None = None,
    ) -> dict[str, Any]:
        screenshot = capture.get("screenshot_path")
        return {
            "evidence_ref": capture.get("evidence_ref"), "page": capture.get("page"),
            "captured_at": capture.get("captured_at") or datetime.now(UTC).isoformat(),
            "mapping_confidence": confidence,
            "original_label": original_label,
            "screenshot_ref": Path(str(screenshot)).name if screenshot else None,
            "source_snippets": snippets[:3],
        }

    def _uncertain(self, parameter: dict[str, Any], capture: dict[str, Any], snippets: list[str], reason: str) -> dict[str, Any]:
        return {
            "parameter": parameter["id"], "value": None, "unit": parameter["unit"],
            "availability": "unavailable_through_inspected_interface",
            "source_interface": f"Android UI: {capture.get('package', 'unknown')}",
            "metadata": {**self._evidence(capture, "uncertain", snippets), "uncertainty_reason": reason},
        }

    @staticmethod
    def _validate_resolution(value: Any, expected_parameter: str) -> None:
        if not isinstance(value, dict) or value.get("parameter") != expected_parameter:
            raise ExtractionError("Ambiguity resolver returned invalid JSON")
        if not isinstance(value.get("value"), (int, float)):
            raise ExtractionError("Ambiguity resolver must return a numeric value")
