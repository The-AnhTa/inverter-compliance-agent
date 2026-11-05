"""Private, content-free timing diagnostics for the conversational demo."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class TimingLogger:
    """Append redacted operational timings without prompts, UI text, or identifiers."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or ROOT / "output/logs/conversation-timing.jsonl").resolve()
        self._lock = threading.Lock()

    def record(self, event: str, duration_seconds: float, **fields: Any) -> None:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        payload = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "event": event,
            "duration_ms": round(max(duration_seconds, 0.0) * 1000, 1),
            **safe_fields,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


DEFAULT_TIMING_LOGGER = TimingLogger()
