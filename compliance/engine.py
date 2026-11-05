"""Deterministic standards-rule evaluation with no network or LLM dependency."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import (
    ApprovedVariation,
    Assessment,
    AssessmentResult,
    AssessmentStatus,
    Observation,
    Rule,
)
from .normalize import normalize_unit, normalize_value, values_equal


class ComplianceEngine:
    def __init__(self, rules_path: str | Path, catalog_path: str | Path) -> None:
        rules_document = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        self.rules = tuple(Rule.from_dict(item) for item in rules_document["rules"])
        self.known_regions = tuple(rules_document["metadata"]["known_regions"])
        self.catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))

    def assess_file(self, configuration_path: str | Path) -> Assessment:
        data = json.loads(Path(configuration_path).read_text(encoding="utf-8"))
        return self.assess(data)

    def assess(self, data: dict[str, Any]) -> Assessment:
        metadata = data["metadata"]
        synthetic = metadata.get("synthetic")
        if not isinstance(synthetic, bool):
            raise ValueError("metadata.synthetic must be an explicit boolean")
        if not synthetic:
            inspection = metadata.get("inspection", {})
            if not isinstance(inspection, dict) or inspection.get("evidence_backed") is not True:
                raise ValueError("Observed assessments require evidence-backed inspection metadata")

        region = metadata["region"]
        if region not in self.known_regions:
            result = AssessmentResult(
                rule_id="REGION-KNOWN",
                clause="3.5 / 4.9",
                parameter="regional_configuration",
                status=AssessmentStatus.UNKNOWN_REGION,
                observed_value=region,
                observed_unit="",
                expected={"allowed": list(self.known_regions)},
                constraint={"type": "known_region"},
                message="Regional configuration is unknown; region-dependent rules were not evaluated.",
                source_reference={
                    "standard": "AS/NZS 4777.2:2020 including Amendments 1:2021 and 2:2024",
                    "clause": "3.5 and 4.9",
                },
                review_status="source_checked_human_review_required",
            )
            return self._assessment(metadata, (result,))

        observations = {
            item.parameter: item
            for item in (Observation.from_dict(item) for item in data.get("observations", []))
        }
        variations = tuple(
            ApprovedVariation.from_dict(item) for item in data.get("approved_variations", [])
        )
        results = tuple(
            self._evaluate_with_evidence(rule, region, observations.get(rule.parameter), variations)
            for rule in self.rules
            if region in rule.relevant_regions or "ALL" in rule.relevant_regions
        )
        return self._assessment(metadata, results)

    def _evaluate_with_evidence(
        self,
        rule: Rule,
        region: str,
        observation: Observation | None,
        variations: tuple[ApprovedVariation, ...],
    ) -> AssessmentResult:
        result = self._evaluate(rule, region, observation, variations)
        if observation is None or not observation.metadata:
            return result
        evidence = dict(observation.metadata)
        evidence.update(result.evidence)
        return replace(result, evidence=evidence)

    @staticmethod
    def _assessment(metadata: dict[str, Any], results: tuple[AssessmentResult, ...]) -> Assessment:
        return Assessment(
            dataset_id=metadata["dataset_id"],
            synthetic=metadata["synthetic"],
            region=metadata["region"],
            interface=metadata.get("interface", "unknown"),
            inverter_metadata=dict(metadata.get("inverter", {})),
            results=results,
        )

    def _evaluate(
        self,
        rule: Rule,
        region: str,
        observation: Observation | None,
        variations: tuple[ApprovedVariation, ...],
    ) -> AssessmentResult:
        if rule.assessment_method != "app_setting":
            return self._result(
                rule,
                AssessmentStatus.NOT_ASSESSABLE,
                observation.value if observation else None,
                observation.unit if observation else rule.unit,
                "This requirement needs evidence beyond app settings (for example, type-test evidence).",
            )
        if observation is None or observation.availability != "available":
            return self._result(
                rule,
                AssessmentStatus.NOT_OBSERVED,
                observation.value if observation else None,
                observation.unit if observation else rule.unit,
                "The parameter was unavailable through the inspected interface; capability absence is not inferred.",
                {"availability": observation.availability if observation else "not_supplied"},
            )
        if normalize_unit(observation.unit) != normalize_unit(rule.unit):
            return self._result(
                rule,
                AssessmentStatus.NOT_OBSERVED,
                observation.value,
                observation.unit,
                f"Unit {observation.unit!r} cannot be safely compared with {rule.unit!r}.",
                {"reason": "unit_mismatch", "expected_unit": rule.unit},
            )

        value = normalize_value(observation.value)
        constraint = rule.constraint
        if constraint.get("type") == "range":
            if not isinstance(value, Decimal):
                return self._result(
                    rule,
                    AssessmentStatus.NOT_OBSERVED,
                    observation.value,
                    observation.unit,
                    "A numeric value is required for the permitted-range assessment.",
                )
            minimum = Decimal(str(constraint["minimum"]))
            maximum = Decimal(str(constraint["maximum"]))
            if value < minimum or value > maximum:
                return self._result(
                    rule,
                    AssessmentStatus.NON_COMPLIANT,
                    observation.value,
                    observation.unit,
                    f"Observed value is outside the permitted inclusive range {minimum} to {maximum} {rule.unit}.",
                )

        default = rule.expected.get("default")
        if default is not None and values_equal(observation.value, default):
            return self._result(
                rule,
                AssessmentStatus.COMPLIANT,
                observation.value,
                observation.unit,
                "Observed value matches the standards default.",
            )

        matching_variations = tuple(
            variation
            for variation in variations
            if variation.parameter == rule.parameter
            and variation.region == region
            and values_equal(observation.value, variation.approved_value)
        )
        verified_variation = next(
            (variation for variation in matching_variations if variation.evidence_verified),
            None,
        )
        if verified_variation is not None:
            return self._result(
                rule,
                AssessmentStatus.APPROVED_VARIATION,
                observation.value,
                observation.unit,
                "Observed value differs from the published value and matches verified approved-variation evidence.",
                {
                    "approval_reference": verified_variation.approval_reference,
                    "evidence_id": verified_variation.evidence_id,
                    "approval_verified": True,
                },
            )

        approval_claim = observation.metadata.get("approval_claim")
        if matching_variations or approval_claim:
            evidence: dict[str, Any] = {"approval_verified": False}
            if matching_variations:
                evidence["approval_reference"] = matching_variations[0].approval_reference
            if isinstance(approval_claim, dict):
                reference = approval_claim.get("approval_reference")
                if isinstance(reference, str) and reference:
                    evidence["claimed_approval_reference"] = reference
            return self._result(
                rule,
                AssessmentStatus.APPROVAL_NOT_VERIFIED,
                observation.value,
                observation.unit,
                "An approval was claimed, but no matching verified evidence was resolved; the claim is not proof of approval.",
                evidence,
            )

        if default is not None:
            return self._result(
                rule,
                AssessmentStatus.DEVIATION,
                observation.value,
                observation.unit,
                "Observed value is within any stated constraint but differs from the standards default; approval evidence was not supplied.",
            )
        return self._result(
            rule,
            AssessmentStatus.NOT_ASSESSABLE,
            observation.value,
            observation.unit,
            "The rule has no deterministic app-setting comparison.",
        )

    @staticmethod
    def _result(
        rule: Rule,
        status: AssessmentStatus,
        observed: Any,
        observed_unit: str,
        message: str,
        evidence: dict[str, Any] | None = None,
    ) -> AssessmentResult:
        result_evidence = dict(evidence or {})
        if rule.modeling_caveat:
            result_evidence["modeling_caveat"] = rule.modeling_caveat
        return AssessmentResult(
            rule_id=rule.rule_id,
            clause=rule.clause,
            parameter=rule.parameter,
            status=status,
            observed_value=observed,
            observed_unit=observed_unit,
            expected=rule.expected,
            constraint=rule.constraint,
            message=message,
            source_reference=rule.source_reference,
            review_status=rule.review_status,
            evidence=result_evidence,
        )
