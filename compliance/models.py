"""Typed models for standards rules, observations, and assessment results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class AssessmentStatus(StrEnum):
    COMPLIANT = "compliant"
    DEVIATION = "deviation_from_default"
    NON_COMPLIANT = "outside_permitted_range"
    NOT_OBSERVED = "not_observed"
    NOT_ASSESSABLE = "not_assessable_from_app_settings"
    APPROVED_VARIATION = "compliant_with_approved_variation"
    APPROVAL_NOT_VERIFIED = "approval_not_verified"
    UNKNOWN_REGION = "unknown_regional_configuration"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    clause: str
    parameter: str
    unit: str
    applicability: str
    relevant_regions: tuple[str, ...]
    expected: dict[str, Any]
    constraint: dict[str, Any]
    source_reference: dict[str, str]
    review_status: str
    assessment_method: str = "app_setting"
    modeling_caveat: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Rule":
        required = {
            "rule_id",
            "clause",
            "parameter",
            "unit",
            "applicability",
            "relevant_regions",
            "expected",
            "constraint",
            "source_reference",
            "review_status",
        }
        missing = required - value.keys()
        if missing:
            raise ValueError(f"Rule is missing required fields: {sorted(missing)}")
        if value["review_status"] == "validated":
            raise ValueError("Automatically prepared rules must not be marked validated")
        return cls(
            rule_id=value["rule_id"],
            clause=value["clause"],
            parameter=value["parameter"],
            unit=value["unit"],
            applicability=value["applicability"],
            relevant_regions=tuple(value["relevant_regions"]),
            expected=dict(value["expected"]),
            constraint=dict(value["constraint"]),
            source_reference=dict(value["source_reference"]),
            review_status=value["review_status"],
            assessment_method=value.get("assessment_method", "app_setting"),
            modeling_caveat=value.get("modeling_caveat", ""),
        )


@dataclass(frozen=True)
class Observation:
    parameter: str
    value: Any = None
    unit: str = ""
    availability: str = "available"
    source_interface: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Observation":
        return cls(
            parameter=value["parameter"],
            value=value.get("value"),
            unit=value.get("unit", ""),
            availability=value.get("availability", "available"),
            source_interface=value.get("source_interface", "unknown"),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class ApprovedVariation:
    parameter: str
    region: str
    approved_value: Any
    approval_reference: str
    evidence_verified: bool = False
    evidence_id: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ApprovedVariation":
        return cls(
            parameter=value["parameter"],
            region=value["region"],
            approved_value=value["approved_value"],
            approval_reference=value["approval_reference"],
            evidence_verified=value.get("evidence_verified", False) is True,
            evidence_id=value.get("evidence_id", ""),
        )


@dataclass(frozen=True)
class AssessmentResult:
    rule_id: str
    clause: str
    parameter: str
    status: AssessmentStatus
    observed_value: Any
    observed_unit: str
    expected: dict[str, Any]
    constraint: dict[str, Any]
    message: str
    source_reference: dict[str, str]
    review_status: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        result["classification"] = self.status.value
        return result


@dataclass(frozen=True)
class Assessment:
    dataset_id: str
    synthetic: bool
    region: str
    interface: str
    inverter_metadata: dict[str, Any]
    results: tuple[AssessmentResult, ...]

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status.value] = counts.get(result.status.value, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "synthetic": self.synthetic,
            "region": self.region,
            "interface": self.interface,
            "inverter_metadata": self.inverter_metadata,
            "counts": self.counts,
            "results": [result.to_dict() for result in self.results],
        }
