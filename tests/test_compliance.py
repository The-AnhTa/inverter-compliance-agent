from __future__ import annotations

import json
import unittest
from pathlib import Path

from compliance.engine import ComplianceEngine
from compliance.models import AssessmentStatus
from reports.generate_report import render_markdown


ROOT = Path(__file__).resolve().parents[1]


class ComplianceDemonstrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ComplianceEngine(
            ROOT / "standards" / "standards_rules.json",
            ROOT / "standards" / "parameter_catalog.json",
        )
        cls.demo = cls.engine.assess_file(ROOT / "tests" / "fixtures" / "synthetic_demo.json")
        cls.by_parameter = {result.parameter: result for result in cls.demo.results}

    def test_parameter_matching_standards_default(self) -> None:
        self.assertEqual(
            self.by_parameter["power_rate_limit_gradient_increase"].status,
            AssessmentStatus.COMPLIANT,
        )

    def test_parameter_deviating_from_default(self) -> None:
        self.assertEqual(
            self.by_parameter["volt_watt_vw1"].status,
            AssessmentStatus.DEVIATION,
        )

    def test_parameter_outside_permitted_range(self) -> None:
        self.assertEqual(
            self.by_parameter["power_rate_limit_gradient_decrease"].status,
            AssessmentStatus.NON_COMPLIANT,
        )

    def test_unavailable_field_does_not_imply_missing_capability(self) -> None:
        result = self.by_parameter["upper_connection_reconnection_frequency"]
        self.assertEqual(result.status, AssessmentStatus.NOT_OBSERVED)
        self.assertIn("capability absence is not inferred", result.message)

    def test_requirement_not_assessable_from_app_settings(self) -> None:
        self.assertEqual(
            self.by_parameter["voltage_disturbance_response"].status,
            AssessmentStatus.NOT_ASSESSABLE,
        )

    def test_documented_approved_variation(self) -> None:
        result = self.by_parameter["volt_var_vv1"]
        self.assertEqual(result.status, AssessmentStatus.APPROVED_VARIATION)
        self.assertEqual(result.evidence["approval_reference"], "SYNTHETIC-DISTRIBUTOR-APPROVAL-001")

    def test_unknown_regional_configuration(self) -> None:
        assessment = self.engine.assess_file(
            ROOT / "tests" / "fixtures" / "synthetic_unknown_region.json"
        )
        self.assertEqual(len(assessment.results), 1)
        self.assertEqual(assessment.results[0].status, AssessmentStatus.UNKNOWN_REGION)

    def test_all_fixture_data_is_explicitly_synthetic(self) -> None:
        for fixture in (ROOT / "tests" / "fixtures").glob("*.json"):
            data = json.loads(fixture.read_text(encoding="utf-8"))
            if "assessment_mode" in data:
                self.assertEqual(data["assessment_mode"], "synthetic", fixture.name)
            else:
                self.assertIs(data["metadata"]["synthetic"], True, fixture.name)

    def test_automatic_rules_are_not_marked_validated(self) -> None:
        rules = json.loads(
            (ROOT / "standards" / "standards_rules.json").read_text(encoding="utf-8")
        )["rules"]
        self.assertTrue(rules)
        self.assertTrue(all(rule["review_status"] != "validated" for rule in rules))

    def test_markdown_report_carries_synthetic_warning(self) -> None:
        report = render_markdown(self.demo)
        self.assertIn("SYNTHETIC DATA", report)
        self.assertIn("capability", report)
        self.assertIn("compliant_with_approved_variation", report)


if __name__ == "__main__":
    unittest.main()
