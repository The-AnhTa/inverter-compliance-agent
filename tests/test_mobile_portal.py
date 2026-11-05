from __future__ import annotations

import json
import unittest
from pathlib import Path

from android.mobile_client import (
    MobileInspectionError,
    ReadOnlyMobileClient,
    decode_content_provider_response,
    detect_screen,
    enumerate_navigation_candidates,
    normalize_accessibility_nodes,
)
from android.parameter_extractor import ParameterExtractor


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.goodwe.sems.plus"


def node(
    text: str = "",
    description: str = "",
    *,
    clickable: bool = False,
    children: list[dict] | None = None,
) -> dict:
    return {
        "className": "android.widget.TextView",
        "packageName": PACKAGE,
        "text": text,
        "contentDescription": description,
        "hint": "",
        "resourceId": "",
        "isClickable": clickable,
        "isVisibleToUser": True,
        "isPassword": False,
        "boundsInScreen": {"left": 0, "top": 0, "right": 100, "bottom": 100},
        "children": children or [],
    }


def portal_row(value: object) -> str:
    nested = json.dumps(value, separators=(",", ":"))
    outer = json.dumps({"status": "success", "result": nested}, separators=(",", ":"))
    return f"Row: 0 result={outer}"


class PortalCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = ParameterExtractor(ROOT / "standards/parameter_catalog.json")

    def test_nested_content_provider_json_is_decoded(self) -> None:
        result = decode_content_provider_response(portal_row({"packageName": PACKAGE}), "phone_state")
        self.assertEqual(result["packageName"], PACKAGE)

    def test_unsuccessful_malformed_or_empty_responses_are_rejected(self) -> None:
        with self.assertRaises(MobileInspectionError):
            decode_content_provider_response('Row: 0 result={"status":"error","result":"x"}', "ping")
        with self.assertRaises(MobileInspectionError):
            decode_content_provider_response("Row: 0 result=not-json", "phone_state")
        with self.assertRaises(MobileInspectionError):
            decode_content_provider_response('Row: 0 result={"status":"success","result":""}', "phone_state")

    def test_actual_accessibility_nodes_are_normalized_with_context(self) -> None:
        tree = node(children=[node("VW1"), node("253 V")])
        nodes = normalize_accessibility_nodes(tree, PACKAGE)
        self.assertEqual(len(nodes), 3)
        self.assertIn("253 V", nodes[1]["ui_context"]["sibling_text"])

    def test_goodwe_dashboard_measurements_are_not_configuration_parameters(self) -> None:
        tree = node(children=[
            node("Energy Generation"), node("Generation Revenue"), node(description="Devices", clickable=True),
            node("Grid Frequency 50.02 Hz"), node("Grid Voltage 241.2 V"),
        ])
        nodes = normalize_accessibility_nodes(tree, PACKAGE)
        capture = {"package": PACKAGE, "current_screen": detect_screen(nodes), "ui_text": nodes}
        self.assertEqual(capture["current_screen"], "GoodWe dashboard")
        self.assertEqual(self.extractor.extract_page(capture), [])
        self.assertTrue(self.extractor.last_diagnostics["rejected_live_measurements"])

    def test_goodwe_control_and_protection_screens_are_distinguished(self) -> None:
        control_nodes = normalize_accessibility_nodes(
            node(children=[node("More Control"), node("Protection Settings")]), PACKAGE
        )
        protection_nodes = normalize_accessibility_nodes(
            node(children=[node("Protection Settings")]), PACKAGE
        )
        self.assertEqual(detect_screen(control_nodes), "GoodWe control menu")
        self.assertEqual(detect_screen(protection_nodes), "GoodWe protection settings")

    def test_contextual_goodwe_configuration_labels_map_without_point_number_confusion(self) -> None:
        tree = node(children=[
            node("Parameter Settings"),
            node(children=[node("Volt Watt Point 1"), node("253 V")]),
            node(children=[node("Upper Reconnection Frequency"), node("50.15 Hz")]),
        ])
        nodes = normalize_accessibility_nodes(tree, PACKAGE)
        capture = {
            "package": PACKAGE,
            "page": "parameter-display",
            "current_screen": detect_screen(nodes),
            "captured_at": "2026-10-30T00:00:00Z",
            "evidence_ref": "SYNTHETIC-goodwe-parameters.json",
            "ui_text": nodes,
        }
        results = self.extractor.extract_page(capture)
        mapped = {item["parameter"]: item["value"] for item in results}
        self.assertEqual(mapped["volt_watt_vw1"], 253)
        self.assertEqual(mapped["upper_connection_reconnection_frequency"], 50.15)

    def test_navigation_candidates_resolve_clickable_parent_and_reject_controls(self) -> None:
        safe_row = node(clickable=True, children=[node("Protection Settings")])
        safe_row["boundsInScreen"] = {"left": 0, "top": 300, "right": 1000, "bottom": 420}
        unsafe_operational = node("Device Start/Stop", clickable=True)
        unsafe_submit = node("Apply", clickable=True)
        toggle = node("Grid Settings", clickable=True)
        toggle["className"] = "android.widget.Switch"
        tree = node(children=[safe_row, unsafe_operational, unsafe_submit, toggle])
        nodes = normalize_accessibility_nodes(tree, PACKAGE)
        capture = {
            "package": PACKAGE,
            "current_screen": "GoodWe control menu",
            "ui_text": nodes,
        }

        candidates = enumerate_navigation_candidates(capture)
        labels = [item["label"] for item in candidates]
        self.assertEqual(labels, ["Protection Settings"])
        self.assertEqual(candidates[0]["target_node_index"], 1)

    def test_navigation_candidates_reject_title_bar_and_setting_value_rows(self) -> None:
        capture = {
            "current_screen": "unclassified GoodWe screen",
            "ui_text": [
                {
                    "node_index": 1, "parent_index": None,
                    "labels": ["Safety Setting"], "clickable": True,
                    "enabled": True, "class_name": "android.view.ViewGroup",
                    "bounds": {"left": 169, "top": 110, "right": 939, "bottom": 191},
                    "child_count": 1,
                },
                {
                    "node_index": 2, "parent_index": None,
                    "labels": ["Safety Regulation, --"], "clickable": True,
                    "enabled": True, "class_name": "android.view.ViewGroup",
                    "bounds": {"left": 42, "top": 221, "right": 1038, "bottom": 383},
                    "child_count": 2,
                },
                {
                    "node_index": 3, "parent_index": 2,
                    "labels": ["Safety Regulation"], "clickable": False,
                    "enabled": True, "class_name": "android.widget.TextView",
                    "bounds": {"left": 84, "top": 263, "right": 881, "bottom": 341},
                    "child_count": 0,
                },
            ],
        }
        self.assertEqual(enumerate_navigation_candidates(capture), [])


class MobileGestureTests(unittest.IsolatedAsyncioTestCase):
    async def test_scroll_and_back_execute_driver_gestures(self) -> None:
        class Driver:
            def __init__(self) -> None:
                self.calls: list[tuple] = []

            async def swipe(self, *args, **kwargs) -> None:
                self.calls.append(("swipe", args, kwargs))

            async def press_button(self, value: str) -> None:
                self.calls.append(("press_button", value))

        client = ReadOnlyMobileClient("serial", {PACKAGE}, ROOT / "output-test")
        driver = Driver()
        client._driver = driver

        async def foreground(package: str) -> dict:
            self.assertEqual(package, PACKAGE)
            return {"packageName": PACKAGE}

        client._require_foreground_from_portal = foreground  # type: ignore[method-assign]
        await client.scroll_screen(PACKAGE)
        await client.go_back(PACKAGE)

        self.assertEqual(driver.calls[0][0], "swipe")
        self.assertEqual(driver.calls[0][1], (540, 1650, 540, 550))
        self.assertEqual(driver.calls[0][2], {"duration_ms": 500})
        self.assertEqual(driver.calls[1], ("press_button", "back"))


if __name__ == "__main__":
    unittest.main()
