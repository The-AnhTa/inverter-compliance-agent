from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "integration" / "openclaw" / "assessment_runner.py"
FIXTURE = ROOT / "tests" / "fixtures" / "task_e_synthetic_request.json"


class TaskEIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def run_raw(self, raw: bytes, timeout: float = 10) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-I", str(RUNNER)],
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=ROOT,
            timeout=timeout,
            check=False,
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )

    def assess(self, value: object) -> dict[str, object]:
        completed = self.run_raw(json.dumps(value, separators=(",", ":")).encode())
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        return json.loads(completed.stdout)

    @staticmethod
    def by_parameter(result: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["parameter"]: item for item in result["results"]}  # type: ignore[index]

    def test_correct_synthetic_configuration_uses_engine(self) -> None:
        result = self.assess(self.request)
        by_parameter = self.by_parameter(result)
        self.assertEqual(by_parameter["power_rate_limit_gradient_increase"]["classification"], "compliant")
        self.assertEqual(by_parameter["volt_watt_vw1"]["classification"], "compliant")
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["inverter_metadata"]["model"], "Synthetic Model A")

    def test_out_of_range_parameter(self) -> None:
        request = copy.deepcopy(self.request)
        request["observations"][1]["value"] = 2
        result = self.by_parameter(self.assess(request))
        self.assertEqual(result["power_rate_limit_gradient_decrease"]["classification"], "outside_permitted_range")

    def test_missing_parameter_is_not_observed(self) -> None:
        request = copy.deepcopy(self.request)
        request["observations"] = []
        result = self.by_parameter(self.assess(request))
        self.assertEqual(result["volt_watt_vw1"]["classification"], "not_observed")

    def test_unknown_region_is_not_evaluated_as_known(self) -> None:
        request = copy.deepcopy(self.request)
        request["regional_profile"] = "Synthetic Unknown Region"
        result = self.assess(request)
        self.assertEqual(result["results"][0]["classification"], "unknown_regional_configuration")

    def test_unit_mismatch_is_not_compared(self) -> None:
        request = copy.deepcopy(self.request)
        request["observations"][2]["unit"] = "kV"
        result = self.by_parameter(self.assess(request))["volt_watt_vw1"]
        self.assertEqual(result["classification"], "not_observed")
        self.assertEqual(result["evidence"]["reason"], "unit_mismatch")

    def test_malformed_json_and_unexpected_fields_are_rejected(self) -> None:
        malformed = self.run_raw(b'{"assessment_mode":')
        self.assertEqual(malformed.returncode, 2)
        self.assertIn(b"valid JSON", malformed.stderr)
        request = copy.deepcopy(self.request)
        request["command"] = "whoami"
        unexpected = self.run_raw(json.dumps(request).encode())
        self.assertEqual(unexpected.returncode, 2)
        self.assertIn(b"unexpected fields", unexpected.stderr)

    def test_oversized_json_is_rejected(self) -> None:
        completed = self.run_raw(b" " * 32_769)
        self.assertEqual(completed.returncode, 2)
        self.assertIn(b"exceeds 32768 bytes", completed.stderr)

    def test_shell_command_and_path_injection_are_rejected(self) -> None:
        request = copy.deepcopy(self.request)
        request["inverter"]["model"] = "x; whoami"
        command = self.run_raw(json.dumps(request).encode())
        self.assertEqual(command.returncode, 2)
        request = copy.deepcopy(self.request)
        request["observations"][0]["path"] = "C:\\Windows\\System32"
        path_attempt = self.run_raw(json.dumps(request).encode())
        self.assertEqual(path_attempt.returncode, 2)

    def test_unverified_approved_override_is_not_approval(self) -> None:
        request = copy.deepcopy(self.request)
        observation = request["observations"][3]
        observation["metadata"] = {
            "approved_override": True,
            "approval_reference": "SYNTHETIC-UNVERIFIED-CLAIM",
        }
        result = self.by_parameter(self.assess(request))["volt_var_vv1"]
        self.assertEqual(result["classification"], "approval_not_verified")
        self.assertIs(result["evidence"]["approval_verified"], False)

    def test_verified_synthetic_evidence_is_resolved_outside_model_input(self) -> None:
        result = self.by_parameter(self.assess(self.request))["volt_var_vv1"]
        self.assertEqual(result["classification"], "compliant_with_approved_variation")
        self.assertIs(result["evidence"]["approval_verified"], True)
        self.assertEqual(result["evidence"]["evidence_id"], "SYNTHETIC-EVIDENCE-AU-A-VV1-210")


if __name__ == "__main__":
    unittest.main()
