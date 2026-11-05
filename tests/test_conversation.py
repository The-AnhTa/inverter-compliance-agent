from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from typing import Any

from client.conversation import (
    ConversationOrchestrator,
    ConversationState,
    GLMConversationModel,
    LaptopToolExecutor,
    ModelCallTimeoutError,
    ModelDecision,
    ToolCall,
)
from client.openclaw_client import OpenClawReply


ROOT = Path(__file__).resolve().parents[1]


def decision(message: str = "", *calls: tuple[str, dict[str, Any]]) -> ModelDecision:
    return ModelDecision(message, tuple(ToolCall(name, arguments) for name, arguments in calls))


class ScriptedModel:
    def __init__(self, decisions: list[ModelDecision]) -> None:
        self.decisions = list(decisions)
        self.invocations: list[dict[str, Any]] = []

    def decide(
        self,
        user_message: str,
        state: ConversationState,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> ModelDecision:
        self.invocations.append(
            {
                "message": user_message,
                "context": state.model_context(),
                "tool_results": tool_results,
            }
        )
        return self.decisions.pop(0)


class FakeTools:
    def __init__(self, state: ConversationState) -> None:
        self.state = state
        self.calls: list[ToolCall] = []

    async def execute(self, call: ToolCall) -> dict[str, Any]:
        self.calls.append(call)
        if call.name == "get_device_status":
            self.state.current_package = "com.goodwe.sems.plus"
            self.state.current_app = "SEMS+"
            result = {"foreground_app": "SEMS+", "approved_for_inspection": True}
        elif call.name == "inspect_current_screen":
            self.state.last_screen = "GoodWe dashboard"
            self.state.captures.append(
                {
                    "current_screen": "GoodWe dashboard",
                    "page": "current",
                    "node_count": 64,
                    "readable_labels": ["Devices", "Current Power"],
                    "evidence_ref": "mock://fresh/dashboard",
                }
            )
            result = {"screen": "GoodWe dashboard", "nodes": 64}
        elif call.name == "get_observed_parameters":
            self.state.unavailable_parameters = ["volt_watt_vw1"]
            result = {
                "mapped_count": 0,
                "unavailable_parameters": ["volt_watt_vw1"],
                "conclusion": "Compliance cannot be assessed.",
            }
        elif call.name == "generate_report":
            result = {"error": "No deterministic assessment is available to report"}
            return {"operation": call.name, "ok": False, "error": result["error"]}
        else:
            result = {"destination": call.arguments.get("destination")}
        return {"operation": call.name, "ok": True, "result": result}


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def test_deterministic_navigation_prioritises_safety_without_a_model(self) -> None:
        candidates = [
            {"element_id": "nav-111111111111", "label": "Devices"},
            {"element_id": "nav-222222222222", "label": "General Settings"},
            {"element_id": "nav-333333333333", "label": "Safety Settings"},
        ]
        selected = LaptopToolExecutor._select_navigation_deterministically(
            candidates, ["tap"]
        )
        self.assertEqual(selected["action"], "tap")
        self.assertEqual(selected["candidate_id"], "nav-333333333333")

    async def test_bounded_autonomous_exploration_executes_scroll_back_and_safe_tap(self) -> None:
        def capture_for(screen: str, sequence: int) -> dict[str, Any]:
            if screen == "control":
                ui = [
                    {
                        "node_index": 0, "parent_index": None, "labels": ["More Control"],
                        "text": "More Control", "content_description": "", "hint": "",
                        "ui_context": {"sibling_text": []}, "clickable": False,
                        "enabled": True, "class_name": "android.widget.TextView",
                        "bounds": {"left": 0, "top": 0, "right": 100, "bottom": 100},
                        "child_count": 0,
                    },
                    {
                        "node_index": 1, "parent_index": None, "labels": ["General Settings"],
                        "text": "General Settings", "content_description": "", "hint": "",
                        "ui_context": {"sibling_text": []}, "clickable": True,
                        "enabled": True, "class_name": "android.widget.TextView",
                        "bounds": {"left": 10, "top": 200, "right": 500, "bottom": 300},
                        "child_count": 0,
                    },
                    {
                        "node_index": 2, "parent_index": None, "labels": ["Device Start/Stop"],
                        "text": "Device Start/Stop", "content_description": "", "hint": "",
                        "ui_context": {"sibling_text": []}, "clickable": True,
                        "enabled": True, "class_name": "android.widget.TextView",
                        "bounds": {"left": 10, "top": 320, "right": 500, "bottom": 420},
                        "child_count": 0,
                    },
                ]
                detected = "GoodWe control menu"
                labels = ["More Control", "General Settings", "Device Start/Stop"]
            else:
                title = "Protection Settings" if screen == "protection" else "General Settings"
                ui = [{
                    "node_index": 0, "parent_index": None, "labels": [title],
                    "text": title, "content_description": "", "hint": "",
                    "ui_context": {"sibling_text": []}, "clickable": False,
                    "enabled": True, "class_name": "android.widget.TextView",
                    "bounds": {"left": 0, "top": 0, "right": 500, "bottom": 100},
                    "child_count": 0,
                }]
                detected = f"GoodWe {screen} settings"
                labels = [title]
            return {
                "package": "com.goodwe.sems.plus",
                "page": f"mock-{sequence}",
                "captured_at": "2026-10-30T00:00:00Z",
                "evidence_ref": f"mock-{sequence}.json",
                "screenshot_path": f"mock-{sequence}.png",
                "node_count": len(ui),
                "current_screen": detected,
                "readable_labels": labels,
                "ui_text": ui,
            }

        class FakeMobile:
            def __init__(self) -> None:
                self.screen = "protection"
                self.executed: list[str] = []

            async def scroll_screen(self, package):
                self.executed.append("scroll")
                return {"direction": "down"}

            async def go_back(self, package):
                self.executed.append("back")
                self.screen = "control"
                return {"keyevent": "back"}

            async def tap_element(self, package, capture, element_id):
                self.executed.append("tap")
                self.screen = "general"
                return {"element_id": element_id, "label": "General Settings", "x": 255, "y": 250}

        state = ConversationState(
            current_package="com.goodwe.sems.plus", current_app="SEMS+"
        )
        selector_calls: list[dict[str, Any]] = []

        def selector(context):
            selector_calls.append(context)
            if context["allowed_actions"] == ["tap"]:
                return {"action": "tap", "candidate_id": context["candidates"][0]["candidate_id"]}
            return {"action": context["allowed_actions"][0], "candidate_id": None}

        with tempfile.TemporaryDirectory() as directory:
            executor = LaptopToolExecutor(
                state, Path(directory), navigation_selector=selector
            )
            mobile = FakeMobile()

            async def ensure_mobile():
                return mobile

            async def capture(page):
                value = capture_for(mobile.screen, len(state.captures) + 1)
                state.captures.append(value)
                state.last_screen = value["current_screen"]
                return {"screen": value["current_screen"], "nodes": value["node_count"]}

            executor._ensure_mobile = ensure_mobile  # type: ignore[method-assign]
            executor._capture = capture  # type: ignore[method-assign]
            result = await executor.execute(
                ToolCall("explore_app_for_configuration", {"max_actions": 5})
            )

        self.assertTrue(result["ok"])
        payload = result["result"]
        self.assertEqual(payload["actions_executed"], 5)
        self.assertIn("tap", mobile.executed)
        self.assertIn("scroll", mobile.executed)
        self.assertIn("back", mobile.executed)
        self.assertFalse(any("Start/Stop" in str(call["candidates"]) for call in selector_calls))
        self.assertIsNone(payload["assessment"])
        self.assertEqual(len(payload["unavailable_parameters"]), 10)

    async def test_navigation_operation_argument_validation(self) -> None:
        executor = LaptopToolExecutor(ConversationState(), ROOT / "output-test")
        too_many = await executor.execute(
            ToolCall("explore_app_for_configuration", {"max_actions": 31})
        )
        arbitrary_tap = await executor.execute(
            ToolCall("tap_element", {"element_id": "tap 50 50"})
        )
        self.assertFalse(too_many["ok"])
        self.assertFalse(arbitrary_tap["ok"])

    async def test_final_response_timeout_preserves_tool_evidence_without_duplicate(self) -> None:
        class TimeoutAfterToolModel:
            def __init__(self) -> None:
                self.calls = 0

            def decide(self, user_message, state, tool_results=None):
                self.calls += 1
                if self.calls == 1:
                    return decision("", ("inspect_current_screen", {}))
                raise ModelCallTimeoutError("final_response", "timed out")

        state = ConversationState()
        model = TimeoutAfterToolModel()
        orchestrator = ConversationOrchestrator(model=model, state=state)
        fake = FakeTools(state)
        orchestrator.tools = fake

        answer = await orchestrator.respond("Inspect it.")

        self.assertEqual([call.name for call in fake.calls], ["inspect_current_screen"])
        self.assertEqual(state.last_screen, "GoodWe dashboard")
        self.assertIn("evidence is preserved", answer)
        self.assertIn("No operation was repeated", answer)

    async def test_repeated_model_tool_call_reuses_result_without_execution(self) -> None:
        model = ScriptedModel(
            [
                decision("", ("get_device_status", {})),
                decision("", ("get_device_status", {})),
                decision("SEMS+ is open."),
            ]
        )
        orchestrator = ConversationOrchestrator(model=model)
        fake = FakeTools(orchestrator.state)
        orchestrator.tools = fake

        answer = await orchestrator.respond("Can you see my Android phone?")

        self.assertEqual([call.name for call in fake.calls], ["get_device_status"])
        self.assertTrue(model.invocations[2]["tool_results"][0]["reused_result"])
        self.assertIn("SEMS+", answer)

    def test_followup_prompt_omits_repeated_rules_and_current_message(self) -> None:
        state = ConversationState(
            history=[
                {"role": "user", "content": "Inspect it."},
                {"role": "assistant", "content": "Checking."},
                {"role": "user", "content": "What is visible?"},
            ]
        )
        prompt = GLMConversationModel._prompt(
            "What is visible?",
            state,
            [{"operation": "inspect_current_screen", "ok": True, "result": {"nodes": 10}}],
        )
        payload = __import__("json").loads(prompt)
        context = payload["session_context"]
        self.assertNotIn("rules", context["source_checked_standards_catalog"])
        self.assertNotEqual(
            context["recent_conversation"][-1]["content"],
            "What is visible?",
        )

    async def test_acceptance_conversation_a(self) -> None:
        model = ScriptedModel(
            [
                decision("Hello."),
                decision("I can explain rules and inspect approved screens read-only."),
                decision(
                    "",
                    ("get_device_status", {}),
                    ("inspect_current_screen", {}),
                    ("get_observed_parameters", {}),
                ),
                decision("I checked fresh evidence but found no configured standards values."),
                decision("The app showed operating measurements, not configuration thresholds."),
                decision("A read-only commissioning export or parameter display is the next safe source."),
            ]
        )
        orchestrator = ConversationOrchestrator(model=model)
        fake = FakeTools(orchestrator.state)
        orchestrator.tools = fake
        messages = [
            "Hi.",
            "What can you do?",
            "Can you check my GoodWe inverter?",
            "Why couldn't you find any settings?",
            "What should I try next?",
        ]
        answers = [await orchestrator.respond(message) for message in messages]
        self.assertEqual(len(model.invocations), 6)
        self.assertEqual(
            [call.name for call in fake.calls],
            ["get_device_status", "inspect_current_screen", "get_observed_parameters"],
        )
        self.assertIn("operating measurements", answers[3])
        self.assertIn("read-only", answers[4])

    async def test_acceptance_conversation_b(self) -> None:
        model = ScriptedModel(
            [
                decision("", ("get_device_status", {})),
                decision("SEMS+ is currently open."),
                decision("", ("inspect_current_screen", {}), ("get_observed_parameters", {})),
                decision("The current dashboard was read; it exposed no configured thresholds."),
                decision("No protection-setting value was observed in the current screen."),
                decision("VW1 is the first volt-watt voltage point; its rule depends on region."),
            ]
        )
        orchestrator = ConversationOrchestrator(model=model)
        fake = FakeTools(orchestrator.state)
        orchestrator.tools = fake
        messages = [
            "What app is open?",
            "Read this screen.",
            "Did you find any protection settings?",
            "Can you explain what VW1 means?",
        ]
        answers = [await orchestrator.respond(message) for message in messages]
        self.assertEqual(len(model.invocations), 6)
        self.assertIn("SEMS+", answers[0])
        self.assertIn("No protection-setting value", answers[2])
        self.assertIn("volt-watt", answers[3])

    async def test_acceptance_conversation_c(self) -> None:
        model = ScriptedModel(
            [
                decision("", ("get_observed_parameters", {})),
                decision("There are no observed configuration values to assess."),
                decision("A confirmed region and configured threshold values are missing."),
                decision("", ("generate_report", {})),
                decision("I cannot make a compliance report without a deterministic assessment."),
                decision("In simple terms, there is not enough evidence for a conclusion."),
            ]
        )
        state = ConversationState(
            captures=[
                {
                    "current_screen": "GoodWe protection settings",
                    "page": "protection",
                    "node_count": 10,
                    "readable_labels": ["Protection Settings"],
                    "evidence_ref": "mock://fresh/protection",
                }
            ]
        )
        orchestrator = ConversationOrchestrator(model=model, state=state)
        fake = FakeTools(state)
        orchestrator.tools = fake
        messages = [
            "Assess the values we have.",
            "What information is missing?",
            "Can you make a report?",
            "Explain the conclusion in simple language.",
        ]
        answers = [await orchestrator.respond(message) for message in messages]
        self.assertEqual(len(model.invocations), 6)
        self.assertIn("no observed", answers[0].lower())
        self.assertIn("confirmed region", answers[1])
        self.assertIn("cannot make", answers[2])
        self.assertIn("not enough evidence", answers[3])
        self.assertIsNone(state.latest_assessment)
        self.assertIsNone(state.latest_reports)

    async def test_every_normal_message_reaches_model_and_followup_has_context(self) -> None:
        model = ScriptedModel(
            [
                decision("Hello. I can help with read-only inverter evidence."),
                decision("I can inspect safely and explain the supported standards rules."),
                decision("Previously, five GoodWe screens had no mapped settings."),
            ]
        )
        orchestrator = ConversationOrchestrator(model=model)

        await orchestrator.respond("Hi.")
        await orchestrator.respond("What can you do?")
        answer = await orchestrator.respond("What did you find previously?")

        self.assertEqual(len(model.invocations), 3)
        prior = model.invocations[2]["context"]["recent_conversation"]
        self.assertTrue(any(item["content"] == "What can you do?" for item in prior))
        self.assertIn("five GoodWe screens", answer)

    async def test_tool_result_returns_to_model_for_natural_response(self) -> None:
        model = ScriptedModel(
            [
                decision("", ("get_device_status", {}), ("inspect_current_screen", {})),
                decision("SEMS+ is open on the GoodWe dashboard."),
            ]
        )
        orchestrator = ConversationOrchestrator(model=model)
        fake = FakeTools(orchestrator.state)
        orchestrator.tools = fake

        answer = await orchestrator.respond("What app is open, and read this screen.")

        self.assertEqual([call.name for call in fake.calls], ["get_device_status", "inspect_current_screen"])
        self.assertEqual(len(model.invocations), 2)
        self.assertEqual(len(model.invocations[1]["tool_results"]), 2)
        self.assertEqual(orchestrator.state.last_screen, "GoodWe dashboard")
        self.assertIn("SEMS+", answer)

    async def test_missing_values_do_not_create_assessment_or_report(self) -> None:
        model = ScriptedModel(
            [
                decision("", ("get_observed_parameters", {})),
                decision("No configured threshold values were observed, so I cannot assess them."),
                decision("", ("generate_report", {})),
                decision("There is no evidence-backed assessment to report yet."),
            ]
        )
        state = ConversationState(
            captures=[
                {
                    "current_screen": "GoodWe protection settings",
                    "page": "protection",
                    "node_count": 10,
                    "readable_labels": ["Protection Settings"],
                    "evidence_ref": "mock://fresh/protection",
                }
            ]
        )
        orchestrator = ConversationOrchestrator(model=model, state=state)
        fake = FakeTools(state)
        orchestrator.tools = fake

        first = await orchestrator.respond("Assess the values we have.")
        second = await orchestrator.respond("Can you make a report?")

        self.assertIn("cannot assess", first)
        self.assertIn("no evidence-backed assessment", second)
        self.assertIsNone(state.latest_assessment)
        self.assertIsNone(state.latest_reports)

    async def test_executor_rejects_unknown_navigation_and_write_arguments(self) -> None:
        state = ConversationState()
        executor = LaptopToolExecutor(state, ROOT / "output-test")

        unsafe_navigation = await executor.execute(
            ToolCall("inspect_approved_screen", {"destination": "edit_settings"})
        )
        unsafe_path = await executor.execute(
            ToolCall("generate_report", {"path": "C:/arbitrary/report.md"})
        )

        self.assertFalse(unsafe_navigation["ok"])
        self.assertFalse(unsafe_path["ok"])
        self.assertIn("Unsupported", unsafe_navigation["error"])
        self.assertIn("no arguments", unsafe_path["error"])

    def test_model_schema_rejects_unknown_operations(self) -> None:
        with self.assertRaisesRegex(Exception, "unknown operation"):
            GLMConversationModel._validate_decision(
                {
                    "assistant_message": "",
                    "tool_calls": [{"name": "run_shell", "arguments": {"command": "dir"}}],
                }
            )

    def test_model_repairs_one_malformed_schema_response(self) -> None:
        class RepairingClient:
            def __init__(self) -> None:
                self.requests: list[str] = []

            def ask(self, message: str) -> OpenClawReply:
                self.requests.append(message)
                if len(self.requests) == 1:
                    return OpenClawReply({}, "ordinary prose without JSON")
                return OpenClawReply(
                    {},
                    '{"assistant_message":"Hello safely.","tool_calls":[]}',
                )

        client = RepairingClient()
        model = GLMConversationModel(client=client)  # type: ignore[arg-type]
        result = model.decide("Hi", ConversationState())
        self.assertEqual(result.assistant_message, "Hello safely.")
        self.assertEqual(len(client.requests), 2)
        self.assertIn("previous response did not match", client.requests[1])

    def test_historical_goodwe_evidence_is_explicitly_not_current(self) -> None:
        context = ConversationState().model_context()
        historical = context["historical_goodwe_observation"]
        self.assertEqual(historical["status"], "historical_not_current")
        self.assertEqual(historical["accessibility_nodes"], 174)
        self.assertEqual(historical["visible_numeric_measurements"], 15)
        self.assertEqual(historical["standards_configuration_parameters_mapped"], 0)
        self.assertEqual(len(context["source_checked_standards_catalog"]["rules"]), 19)

    def test_natural_region_profile_wording_can_be_confirmed(self) -> None:
        state = ConversationState(history=[{"role": "user", "content": "Use region A for this comparison."}])
        executor = LaptopToolExecutor(state, ROOT / "output-test")
        self.assertTrue(executor._user_confirmed_region("Australia A"))
        self.assertFalse(executor._user_confirmed_region("Australia B"))


if __name__ == "__main__":
    unittest.main()
