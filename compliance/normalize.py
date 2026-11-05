"""Conservative normalization for JSON observations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


UNIT_ALIASES = {
    "%/min": "% rated power/min",
    "% rated/min": "% rated power/min",
    "percent rated power per minute": "% rated power/min",
    "hz": "Hz",
    "v": "V",
}


def normalize_unit(unit: str) -> str:
    stripped = unit.strip()
    return UNIT_ALIASES.get(stripped.lower(), stripped)


def normalize_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        stripped = value.strip()
        try:
            return Decimal(stripped)
        except InvalidOperation:
            return stripped
    return value


def values_equal(left: Any, right: Any, tolerance: str = "0.000001") -> bool:
    normalized_left = normalize_value(left)
    normalized_right = normalize_value(right)
    if isinstance(normalized_left, Decimal) and isinstance(normalized_right, Decimal):
        return abs(normalized_left - normalized_right) <= Decimal(tolerance)
    return normalized_left == normalized_right

