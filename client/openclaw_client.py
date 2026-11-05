"""Safe SSH adapter for the existing read-only OpenClaw agent."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from client.diagnostics import DEFAULT_TIMING_LOGGER, TimingLogger


DEFAULT_OPENCLAW_TIMEOUT_SECONDS = 600
DEFAULT_PROCESS_GRACE_SECONDS = 90
DEFAULT_SSH_CONNECT_TIMEOUT_SECONDS = 20
DEFAULT_UNCERTAIN_COOLDOWN_SECONDS = 30
TIMING_MARKER = re.compile(r"\[inverter-timing\]\s+openclaw_ms=(\d+)")


def _configured_seconds(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer number of seconds") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum} seconds")
    return value


class OpenClawClientError(RuntimeError):
    pass


class OpenClawTimeoutError(OpenClawClientError):
    def __init__(
        self,
        message: str,
        *,
        remote_completion_uncertain: bool,
        retry_after_seconds: int = 0,
    ) -> None:
        super().__init__(message)
        self.remote_completion_uncertain = remote_completion_uncertain
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class OpenClawReply:
    raw: dict[str, Any]
    text: str
    timings: dict[str, float] = field(default_factory=dict)


class OpenClawClient:
    """Invoke one fixed agent/session. User text is sent only over stdin."""

    def __init__(
        self,
        host: str = "cerguardai",
        agent: str = "inverter-audit",
        session_id: str = "inverter-compliance-demo-v1",
        timeout_seconds: int | None = None,
        process_timeout_seconds: int | None = None,
        diagnostics: TimingLogger | None = None,
    ) -> None:
        self.host = host
        self.agent = agent
        self.session_id = session_id
        self.timeout_seconds = timeout_seconds or _configured_seconds(
            "INVERTER_OPENCLAW_TIMEOUT_SECONDS",
            DEFAULT_OPENCLAW_TIMEOUT_SECONDS,
            60,
            1800,
        )
        self.process_timeout_seconds = process_timeout_seconds or _configured_seconds(
            "INVERTER_OPENCLAW_PROCESS_TIMEOUT_SECONDS",
            self.timeout_seconds + DEFAULT_PROCESS_GRACE_SECONDS,
            90,
            2100,
        )
        if self.process_timeout_seconds < self.timeout_seconds + 30:
            raise ValueError(
                "The Python process timeout must be at least 30 seconds longer than the OpenClaw CLI timeout"
            )
        self.ssh_connect_timeout_seconds = _configured_seconds(
            "INVERTER_SSH_CONNECT_TIMEOUT_SECONDS",
            DEFAULT_SSH_CONNECT_TIMEOUT_SECONDS,
            5,
            120,
        )
        self.uncertain_cooldown_seconds = _configured_seconds(
            "INVERTER_OPENCLAW_TIMEOUT_COOLDOWN_SECONDS",
            DEFAULT_UNCERTAIN_COOLDOWN_SECONDS,
            5,
            300,
        )
        self.diagnostics = diagnostics or DEFAULT_TIMING_LOGGER
        self._uncertain_until = 0.0
        self._rotate_session_after_uncertain_timeout = False

    def _ssh_prefix(self) -> list[str]:
        return [
            "ssh",
            "-o", f"ConnectTimeout={self.ssh_connect_timeout_seconds}",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=22",
            self.host,
        ]

    def command(self) -> list[str]:
        return [
            *self._ssh_prefix(),
            "openclaw", "agent",
            "--agent", self.agent,
            "--session-id", self.session_id,
            "--message-file", "-",
            "--json",
            "--timeout", str(self.timeout_seconds),
        ]

    def _windows_stdin_file_command(self) -> list[str]:
        """Use stdin without putting message text in argv on the Windows VM.

        OpenClaw 2026.9.8 treats '-' as a literal message-file path. The
        encoded wrapper creates a temporary UTF-8 file, invokes the CLI, logs
        only its elapsed time, and removes the file in finally.
        """
        safe = re.compile(r"^[A-Za-z0-9._-]+$")
        if not all(safe.fullmatch(value) for value in (self.agent, self.session_id)):
            raise OpenClawClientError("Unsafe fixed OpenClaw identifier")
        script = f"""$ErrorActionPreference='Stop'
$messagePath = Join-Path $env:TEMP ('inverter-compliance-' + [guid]::NewGuid().ToString('N') + '.txt')
$exitCode = 1
try {{
  $message = [Console]::In.ReadToEnd()
  [IO.File]::WriteAllText($messagePath, $message, (New-Object Text.UTF8Encoding($false)))
  $openClawWatch = [Diagnostics.Stopwatch]::StartNew()
  try {{
    & openclaw agent --agent '{self.agent}' --session-id '{self.session_id}' --message-file $messagePath --json --timeout {int(self.timeout_seconds)}
    $exitCode = $LASTEXITCODE
  }} finally {{
    $openClawWatch.Stop()
    [Console]::Error.WriteLine('[inverter-timing] openclaw_ms=' + $openClawWatch.ElapsedMilliseconds)
  }}
}} catch {{
  [Console]::Error.WriteLine('OpenClaw wrapper failed')
  $exitCode = 1
}} finally {{
  if (Test-Path -LiteralPath $messagePath) {{ Remove-Item -LiteralPath $messagePath -Force }}
}}
exit $exitCode
"""
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        return [
            *self._ssh_prefix(),
            "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded,
        ]

    def _prepare_after_timeout(self) -> None:
        now = time.monotonic()
        if now < self._uncertain_until:
            remaining = max(1, int(self._uncertain_until - now + 0.999))
            raise OpenClawTimeoutError(
                "A previous SSH process deadline expired and its remote completion is still uncertain; "
                f"no retry was started. Retry after about {remaining} seconds.",
                remote_completion_uncertain=True,
                retry_after_seconds=remaining,
            )
        if self._rotate_session_after_uncertain_timeout:
            self.session_id = f"inverter-recovery-{uuid.uuid4().hex[:12]}"
            self._rotate_session_after_uncertain_timeout = False
            self.diagnostics.record("openclaw_session_recovery", 0.0, session_rotated=True)

    def ask(self, message: str) -> OpenClawReply:
        if not isinstance(message, str) or not message.strip():
            raise OpenClawClientError("A non-empty message is required")
        self._prepare_after_timeout()
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                self._windows_stdin_file_command(),
                input=message,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=self.process_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            elapsed = time.perf_counter() - started
            self._uncertain_until = time.monotonic() + self.uncertain_cooldown_seconds
            self._rotate_session_after_uncertain_timeout = True
            self.diagnostics.record(
                "ssh_openclaw_process",
                elapsed,
                success=False,
                outcome="python_process_timeout",
                cli_timeout_seconds=self.timeout_seconds,
                process_timeout_seconds=self.process_timeout_seconds,
                remote_completion_uncertain=True,
            )
            raise OpenClawTimeoutError(
                "The Python SSH process deadline expired after "
                f"{self.process_timeout_seconds} seconds. No automatic retry was started.",
                remote_completion_uncertain=True,
                retry_after_seconds=self.uncertain_cooldown_seconds,
            ) from error
        except OSError as error:
            elapsed = time.perf_counter() - started
            self.diagnostics.record(
                "ssh_openclaw_process", elapsed, success=False, outcome=type(error).__name__
            )
            raise OpenClawClientError(f"OpenClaw invocation failed: {type(error).__name__}") from error

        elapsed = time.perf_counter() - started
        marker = TIMING_MARKER.search(completed.stderr or "")
        remote_seconds = int(marker.group(1)) / 1000 if marker else None
        self.diagnostics.record(
            "ssh_openclaw_process",
            elapsed,
            success=completed.returncode == 0,
            outcome="completed" if completed.returncode == 0 else "nonzero_exit",
            cli_timeout_seconds=self.timeout_seconds,
            process_timeout_seconds=self.process_timeout_seconds,
            return_code=completed.returncode,
        )
        if remote_seconds is not None:
            self.diagnostics.record(
                "remote_openclaw_invocation",
                remote_seconds,
                success=completed.returncode == 0,
            )
            self.diagnostics.record(
                "ssh_connection_wrapper_overhead",
                max(0.0, elapsed - remote_seconds),
                success=completed.returncode == 0,
            )

        if completed.returncode != 0:
            stderr_without_marker = TIMING_MARKER.sub("", completed.stderr or "")
            looks_timed_out = bool(
                re.search(r"tim(?:e|ed)\s*out|timeout", stderr_without_marker, re.I)
            ) or elapsed >= self.timeout_seconds - 2
            if looks_timed_out:
                raise OpenClawTimeoutError(
                    f"OpenClaw reached its explicit {self.timeout_seconds}-second CLI deadline; "
                    "the completed turn was not retried.",
                    remote_completion_uncertain=False,
                )
            raise OpenClawClientError(f"OpenClaw returned exit code {completed.returncode}")
        try:
            payload = json.loads(completed.stdout.lstrip("\ufeff"))
        except json.JSONDecodeError as error:
            raise OpenClawClientError("OpenClaw returned malformed JSON") from error
        if not isinstance(payload, dict):
            raise OpenClawClientError("OpenClaw JSON response must be an object")
        text = self._extract_text(payload)
        return OpenClawReply(
            raw=payload,
            text=text,
            timings={
                "ssh_openclaw_seconds": elapsed,
                "remote_openclaw_seconds": remote_seconds or 0.0,
                "ssh_wrapper_overhead_seconds": max(0.0, elapsed - (remote_seconds or elapsed)),
            },
        )

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        candidates: list[Any] = [payload.get("text"), payload.get("message"), payload.get("output")]
        result = payload.get("result")
        if isinstance(result, dict):
            candidates.extend((result.get("text"), result.get("message"), result.get("output")))
            payloads = result.get("payloads")
            if isinstance(payloads, list):
                candidates.extend(item.get("text") for item in payloads if isinstance(item, dict))
            content = result.get("content")
            if isinstance(content, list):
                candidates.extend(item.get("text") for item in content if isinstance(item, dict))
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return json.dumps(payload, ensure_ascii=False)
