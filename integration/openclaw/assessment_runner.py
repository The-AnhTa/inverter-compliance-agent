"""Fixed-path stdin/stdout adapter for the OpenClaw compliance tool.

This process performs no network access and accepts no command-line arguments,
paths, URLs, executable names, or shell text from the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


MAX_INPUT_BYTES = 32_768
MAX_OUTPUT_BYTES = 262_144
ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("integrity_manifest.json")
RULES_PATH = ROOT / "standards" / "standards_rules.json"
CATALOG_PATH = ROOT / "standards" / "parameter_catalog.json"
EVIDENCE_PATH = ROOT / "standards" / "synthetic_approved_variations.json"

KNOWN_PARAMETERS = {
    "power_rate_limit_gradient_increase",
    "power_rate_limit_gradient_decrease",
    "volt_watt_vw1",
    "volt_var_vv1",
    "upper_connection_reconnection_frequency",
    "voltage_disturbance_response",
}
AVAILABILITY = {"available", "unavailable_through_inspected_interface", "not_supplied"}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()+%-]*$")
SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9 ._()+:%-]*$")
SAFE_UNIT = re.compile(r"^[A-Za-z0-9 %._()+/-]*$")


class InputError(ValueError):
    """Safe validation failure that may be returned without input disclosure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def verify_integrity() -> None:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        files = manifest["files"]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("integrity manifest is unavailable or invalid") from exc
    if not isinstance(files, dict) or not files:
        raise RuntimeError("integrity manifest has no file entries")
    root_resolved = ROOT.resolve()
    for relative_name, expected_hash in files.items():
        if not isinstance(relative_name, str) or not isinstance(expected_hash, str):
            raise RuntimeError("integrity manifest contains an invalid entry")
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError("integrity manifest contains a non-local path")
        target = (ROOT / relative_path).resolve()
        if root_resolved not in target.parents:
            raise RuntimeError("integrity target escapes the project root")
        if not target.is_file() or _sha256(target) != expected_hash.upper():
            raise RuntimeError(f"integrity verification failed for {relative_name}")


def _expect_object(value: Any, label: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{label} must be an object")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise InputError(f"{label} contains unexpected fields: {sorted(unknown)}")
    if missing:
        raise InputError(f"{label} is missing required fields: {sorted(missing)}")
    return value


def _safe_string(value: Any, label: str, maximum: int, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not pattern.fullmatch(value):
        raise InputError(f"{label} is not an allowed string")
    return value


def _validate_value(value: Any, label: str) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            raise InputError(f"{label} must be finite")
        return
    if isinstance(value, str) and len(value) <= 128 and SAFE_VALUE.fullmatch(value):
        return
    raise InputError(f"{label} has an unsupported value type or characters")


def validate_request(value: Any) -> dict[str, Any]:
    request = _expect_object(
        value,
        "request",
        {"assessment_mode", "metadata", "inverter", "regional_profile", "observations"},
        {"assessment_mode", "metadata", "regional_profile", "observations"},
    )
    if request["assessment_mode"] != "synthetic":
        raise InputError("assessment_mode must be synthetic")

    metadata = _expect_object(
        request["metadata"], "metadata", {"dataset_id", "interface"}, {"dataset_id"}
    )
    dataset_id = _safe_string(metadata["dataset_id"], "metadata.dataset_id", 64, SAFE_REFERENCE)
    if not dataset_id.startswith("SYNTHETIC-"):
        raise InputError("metadata.dataset_id must start with SYNTHETIC-")
    if "interface" in metadata:
        _safe_string(metadata["interface"], "metadata.interface", 96, SAFE_LABEL)

    region = _safe_string(request["regional_profile"], "regional_profile", 64, SAFE_LABEL)
    if "inverter" in request:
        inverter = _expect_object(
            request["inverter"],
            "inverter",
            {"manufacturer", "model", "firmware_version", "nominal_power_kw"},
            set(),
        )
        for key in ("manufacturer", "model", "firmware_version"):
            if key in inverter:
                _safe_string(inverter[key], f"inverter.{key}", 64, SAFE_LABEL)
        if "nominal_power_kw" in inverter:
            power = inverter["nominal_power_kw"]
            if isinstance(power, bool) or not isinstance(power, (int, float)) or not 0 <= power <= 1_000_000:
                raise InputError("inverter.nominal_power_kw must be a bounded number")

    observations = request["observations"]
    if not isinstance(observations, list) or len(observations) > 32:
        raise InputError("observations must be an array with at most 32 items")
    seen: set[str] = set()
    for index, raw in enumerate(observations):
        label = f"observations[{index}]"
        observation = _expect_object(
            raw,
            label,
            {"parameter", "value", "unit", "availability", "source_interface", "metadata"},
            {"parameter", "value", "unit", "availability"},
        )
        parameter = observation["parameter"]
        if parameter not in KNOWN_PARAMETERS:
            raise InputError(f"{label}.parameter is not in the fixed catalog")
        if parameter in seen:
            raise InputError(f"{label}.parameter is duplicated")
        seen.add(parameter)
        _validate_value(observation["value"], f"{label}.value")
        unit = observation["unit"]
        if not isinstance(unit, str) or len(unit) > 48 or not SAFE_UNIT.fullmatch(unit):
            raise InputError(f"{label}.unit is not allowed")
        if observation["availability"] not in AVAILABILITY:
            raise InputError(f"{label}.availability is not allowed")
        if "source_interface" in observation:
            _safe_string(observation["source_interface"], f"{label}.source_interface", 96, SAFE_LABEL)
        if "metadata" in observation:
            observation_metadata = _expect_object(
                observation["metadata"],
                f"{label}.metadata",
                {"approved_override", "approval_reference", "approval_evidence_id"},
                set(),
            )
            if "approved_override" in observation_metadata and not isinstance(
                observation_metadata["approved_override"], bool
            ):
                raise InputError(f"{label}.metadata.approved_override must be boolean")
            for key in ("approval_reference", "approval_evidence_id"):
                if key in observation_metadata:
                    _safe_string(
                        observation_metadata[key], f"{label}.metadata.{key}", 80, SAFE_REFERENCE
                    )
    return request


def _load_evidence() -> tuple[dict[str, Any], ...]:
    document = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    if document.get("metadata", {}).get("synthetic_demo_only") is not True:
        raise RuntimeError("approval evidence registry is not marked synthetic")
    records = document.get("records")
    if not isinstance(records, list):
        raise RuntimeError("approval evidence registry is invalid")
    if any(record.get("evidence_verified") is not True for record in records):
        raise RuntimeError("approval evidence registry contains an unverified record")
    return tuple(records)


def build_engine_request(request: dict[str, Any]) -> dict[str, Any]:
    from compliance.normalize import values_equal

    region = request["regional_profile"]
    registry = _load_evidence()
    observations: list[dict[str, Any]] = []
    approved_variations: list[dict[str, Any]] = []
    for raw in request["observations"]:
        observation = dict(raw)
        input_metadata = dict(observation.get("metadata", {}))
        engine_metadata: dict[str, Any] = {}
        evidence_id = input_metadata.get("approval_evidence_id")
        verified = None
        if evidence_id:
            verified = next(
                (
                    record
                    for record in registry
                    if record["evidence_id"] == evidence_id
                    and record["parameter"] == observation["parameter"]
                    and record["region"] == region
                    and values_equal(record["approved_value"], observation["value"])
                ),
                None,
            )
        if verified is not None:
            approved_variations.append(dict(verified))
        elif input_metadata.get("approved_override") is True or evidence_id:
            engine_metadata["approval_claim"] = {
                "approved_override": input_metadata.get("approved_override") is True,
                "approval_reference": input_metadata.get("approval_reference", evidence_id or ""),
            }
        observation["metadata"] = engine_metadata
        observations.append(observation)

    return {
        "metadata": {
            "dataset_id": request["metadata"]["dataset_id"],
            "synthetic": True,
            "region": region,
            "interface": request["metadata"].get("interface", "unknown"),
            "inverter": dict(request.get("inverter", {})),
        },
        "observations": observations,
        "approved_variations": approved_variations,
    }


def run() -> int:
    if len(sys.argv) != 1:
        raise InputError("command-line arguments are not accepted")
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("input exceeds 32768 bytes")
    try:
        decoded = raw.decode("utf-8")
        value = json.loads(
            decoded,
            parse_constant=lambda token: (_ for _ in ()).throw(InputError(f"invalid number {token}")),
        )
    except UnicodeDecodeError as exc:
        raise InputError("input must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise InputError("input must be valid JSON") from exc

    verify_integrity()
    request = validate_request(value)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from compliance.engine import ComplianceEngine

    assessment = ComplianceEngine(RULES_PATH, CATALOG_PATH).assess(build_engine_request(request))
    output = json.dumps(assessment.to_dict(), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    encoded = output.encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise RuntimeError("assessment output exceeds the fixed size limit")
    sys.stdout.buffer.write(encoded)
    return 0


def main() -> int:
    try:
        return run()
    except InputError as exc:
        print(f"ASSESSMENT_INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # Fail closed without a traceback or request echo.
        print(f"ASSESSMENT_RUNTIME_ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
