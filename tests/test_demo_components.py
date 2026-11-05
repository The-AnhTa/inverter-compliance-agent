from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android.mobile_client import collect_ui_text, foreground_package, tree_contains_sensitive_input
from android.parameter_extractor import ParameterExtractor
from client.chat import help_text
from client.openclaw_client import OpenClawClient, OpenClawTimeoutError
from compliance.engine import ComplianceEngine
from reports.generate_report import render_markdown


ROOT = Path(__file__).resolve().parents[1]


class DemoComponentTests(unittest.TestCase):
    def test_help_describes_conversation_and_read_only_boundary(self) -> None:
        text = help_text()
        self.assertIn("Chat normally", text)
        self.assertIn("read-only", text)
        self.assertNotIn("Supported requests", text)

    @patch("client.openclaw_client.subprocess.run")
    def test_raw_message_is_stdin_not_ssh_argument(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, '{"text":"ok"}', "")
        dangerous = "hello; Remove-Item C:\\important"
        client = OpenClawClient()
        reply = client.ask(dangerous)
        self.assertEqual(reply.text, "ok")
        args, kwargs = run.call_args
        self.assertNotIn(dangerous, args[0])
        self.assertEqual(kwargs["input"], dangerous)
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertIn("-EncodedCommand", args[0])
        self.assertNotIn("message-file", " ".join(args[0]))

    @patch("client.openclaw_client.subprocess.run")
    def test_python_timeout_is_not_retried_and_recovers_in_new_session(self, run) -> None:
        run.side_effect = [
            subprocess.TimeoutExpired(["ssh"], 90),
            subprocess.CompletedProcess([], 0, '{"text":"recovered"}', ""),
        ]
        client = OpenClawClient(
            session_id="timeout-test",
            timeout_seconds=60,
            process_timeout_seconds=90,
        )
        original_session = client.session_id

        with self.assertRaises(OpenClawTimeoutError) as first:
            client.ask("first request")
        self.assertTrue(first.exception.remote_completion_uncertain)
        self.assertEqual(run.call_count, 1)

        with self.assertRaisesRegex(OpenClawTimeoutError, "no retry was started"):
            client.ask("too-soon retry")
        self.assertEqual(run.call_count, 1)

        client._uncertain_until = 0
        reply = client.ask("safe recovery")
        self.assertEqual(reply.text, "recovered")
        self.assertEqual(run.call_count, 2)
        self.assertNotEqual(client.session_id, original_session)

    def test_python_deadline_must_exceed_openclaw_deadline(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 30 seconds longer"):
            OpenClawClient(timeout_seconds=600, process_timeout_seconds=610)

    def test_parameter_extraction_preserves_evidence(self) -> None:
        capture = json.loads((ROOT / "tests/fixtures/recorded_inverter_settings_ui.json").read_text(encoding="utf-8"))
        results = ParameterExtractor(ROOT / "standards/parameter_catalog.json").extract_page(capture)
        by_name = {item["parameter"]: item for item in results}
        self.assertEqual(by_name["volt_watt_vw1"]["value"], 253)
        self.assertEqual(by_name["upper_connection_reconnection_frequency"]["unit"].lower(), "hz")
        self.assertEqual(by_name["volt_var_vv4"]["metadata"]["evidence_ref"], capture["evidence_ref"])

    def test_non_synthetic_assessment_requires_evidence(self) -> None:
        engine = ComplianceEngine(ROOT / "standards/standards_rules.json", ROOT / "standards/parameter_catalog.json")
        with self.assertRaisesRegex(ValueError, "evidence-backed"):
            engine.assess({"metadata": {"dataset_id": "x", "synthetic": False, "region": "Australia A"}})

    def test_recorded_ui_fixture_runs_observed_pipeline_with_evidence(self) -> None:
        capture = json.loads((ROOT / "tests/fixtures/recorded_inverter_settings_ui.json").read_text(encoding="utf-8"))
        observations = ParameterExtractor(ROOT / "standards/parameter_catalog.json").extract_page(capture)
        engine = ComplianceEngine(ROOT / "standards/standards_rules.json", ROOT / "standards/parameter_catalog.json")
        assessment = engine.assess({
            "metadata": {
                "dataset_id": "SYNTHETIC-RECORDED-UI-PIPELINE",
                "synthetic": False,
                "region": "Australia A",
                "interface": "recorded synthetic Android UI fixture",
                "inspection": {"evidence_backed": True},
            },
            "observations": observations,
        })
        self.assertFalse(assessment.synthetic)
        self.assertTrue(any(result.evidence.get("evidence_ref") == capture["evidence_ref"] for result in assessment.results))
        report = render_markdown(assessment)
        self.assertIn("READ-ONLY OBSERVATION", report)
        self.assertIn(capture["evidence_ref"], report)

    def test_ui_tree_is_package_filtered(self) -> None:
        tree = {"children": [
            {"packageName": "approved.app", "text": "VW1 253 V"},
            {"packageName": "other.app", "text": "private"},
        ]}
        self.assertEqual(foreground_package(tree), "approved.app")
        self.assertEqual([item["text"] for item in collect_ui_text(tree, "approved.app")], ["VW1 253 V"])

    def test_sensitive_credential_nodes_are_never_collected(self) -> None:
        tree = {"children": [
            {"packageName": "approved.app", "resourceId": "login_password", "text": "do-not-copy", "password": True},
            {"packageName": "approved.app", "resourceId": "vw1", "text": "VW1 253 V"},
        ]}
        self.assertTrue(tree_contains_sensitive_input(tree))
        self.assertEqual([item["text"] for item in collect_ui_text(tree, "approved.app")], ["VW1 253 V"])

    def test_noneditable_account_navigation_is_not_a_credential_boundary(self) -> None:
        tree = {"children": [
            {
                "packageName": "approved.app",
                "className": "android.widget.TextView",
                "text": "Account",
                "isEditable": False,
            }
        ]}
        self.assertFalse(tree_contains_sensitive_input(tree))


if __name__ == "__main__":
    unittest.main()
