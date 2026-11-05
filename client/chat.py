"""Conversational PowerShell entry point for the local compliance demonstration."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from client.conversation import (
    ConversationError,
    ConversationOrchestrator,
    ConversationState,
    GLMConversationModel,
    LaptopToolExecutor,
    ToolCall,
)
from client.openclaw_client import OpenClawClient


WELCOME = (
    "Inverter Compliance Agent (read-only)\n"
    "Ask a question or ask me to inspect the connected inverter. "
    "Type /help for optional shortcuts or /exit to leave."
)


def help_text() -> str:
    return (
        "Chat normally about the inverter, the inspected evidence, or the supported AS/NZS rules.\n"
        "Optional shortcuts: /explore runs direct deterministic GoodWe exploration without GLM, "
        "/status shows session state, /debug toggles research details, "
        "and /exit ends the session.\n"
        "Private timing diagnostics are written to output/logs/conversation-timing.jsonl.\n"
        "Inspection is read-only. I cannot change, save, toggle, reset, start, or stop inverter settings."
    )


def _render_direct_result(result: dict) -> str:
    counts = result.get("action_counts", {})
    summaries = result.get("exploration_summary", {})
    parameter_count = len(result.get("parameters_extracted", []))
    screen_count = len(result.get("screens_explored", []))
    lines = [
        "Direct GoodWe exploration complete.",
        f"App: {result.get('actual_app')}",
        (
            "Actions: "
            f"{result.get('actions_executed', 0)} total; "
            f"{counts.get('tap', 0)} taps, {counts.get('scroll', 0)} scrolls, "
            f"{counts.get('back', 0)} back actions, {counts.get('launch', 0)} launches."
        ),
        f"Unique screens visited: {screen_count}",
        f"Configuration parameters extracted: {parameter_count}",
        f"Stop reason: {result.get('stop_reason')}",
    ]
    if parameter_count:
        lines.append(
            "Compliance assessment: "
            + ("generated" if result.get("assessment") else "not generated")
        )
    else:
        lines.append(
            "Compliance assessment: not run because no genuine configuration values were accessible."
        )
    if summaries:
        lines.append(f"Exploration report: {summaries.get('markdown')}")
        lines.append(f"Structured evidence: {summaries.get('json')}")
    return "\n".join(lines)


async def _direct_explore(state: ConversationState | None = None) -> str:
    executor = LaptopToolExecutor(state or ConversationState())
    executor.progress = lambda value: print(f"Agent: {value}", flush=True)
    outcome = await executor.execute(
        ToolCall("explore_app_for_configuration", {"max_actions": 20})
    )
    if not outcome.get("ok"):
        raise ConversationError(str(outcome.get("error") or "Direct exploration failed"))
    return _render_direct_result(outcome["result"])


async def _answer(
    orchestrator: ConversationOrchestrator,
    message: str,
    *,
    show_progress: bool,
) -> str:
    progress = (lambda value: print(f"Agent: {value}", flush=True)) if show_progress else None
    debug = (
        (lambda value: print(f"[debug] {value}"))
        if orchestrator.state.debug
        else None
    )
    return await orchestrator.respond(message, progress=progress, debug=debug)


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="Conversational inverter compliance agent")
    parser.add_argument("--once", "-Once", dest="once", help="Send one conversational message and exit")
    parser.add_argument(
        "--explore-goodwe",
        action="store_true",
        help="Run bounded deterministic SEMS+ exploration without GLM/OpenClaw",
    )
    parser.add_argument(
        "--openclaw-timeout-seconds",
        type=int,
        help="OpenClaw CLI model deadline (default 600; env INVERTER_OPENCLAW_TIMEOUT_SECONDS)",
    )
    parser.add_argument(
        "--process-timeout-seconds",
        type=int,
        help="Python SSH deadline (default CLI timeout + 90 seconds)",
    )
    args = parser.parse_args()
    if args.explore_goodwe:
        try:
            print(await _direct_explore(), flush=True)
            return 0
        except ConversationError as error:
            print(f"Direct exploration could not be completed: {error}", file=sys.stderr)
            return 2

    client = OpenClawClient(
        session_id=f"inverter-chat-{uuid.uuid4().hex[:12]}",
        timeout_seconds=args.openclaw_timeout_seconds,
        process_timeout_seconds=args.process_timeout_seconds,
    )
    orchestrator = ConversationOrchestrator(model=GLMConversationModel(client=client))

    if args.once is not None:
        try:
            print(await _answer(orchestrator, args.once, show_progress=True), flush=True)
            return 0
        except ConversationError as error:
            print(f"The request could not be completed: {error}", file=sys.stderr)
            return 2

    print(WELCOME)
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue

        command = message.casefold()
        if command in {"exit", "quit", "/exit", "/quit"}:
            break
        if command in {"/help", "help"}:
            print(f"Agent: {help_text()}")
            continue
        if command == "/explore":
            try:
                print(f"Agent: {await _direct_explore(orchestrator.state)}")
            except ConversationError as error:
                print(f"Agent: Direct exploration could not be completed: {error}")
            continue
        if command == "/status":
            print(f"Agent: {orchestrator.state.local_status()}")
            continue
        if command == "/debug":
            orchestrator.state.debug = not orchestrator.state.debug
            setting = "on" if orchestrator.state.debug else "off"
            print(f"Agent: Debug output is {setting}.")
            continue

        try:
            answer = await _answer(orchestrator, message, show_progress=True)
        except ConversationError as error:
            answer = f"I couldn't complete that request safely: {error}"
        print(f"Agent: {answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
