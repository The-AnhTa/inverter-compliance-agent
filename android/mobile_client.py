"""Conservative local MobileRun/ADB inspection boundary for Windows."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


class MobileInspectionError(RuntimeError):
    pass


PORTAL_AUTHORITY = "com.mobilerun.portal"
PORTAL_ENDPOINTS = frozenset({"ping", "phone_state", "a11y_tree_full"})
GOODWE_PACKAGE = "com.goodwe.sems.plus"
GOODWE_READ_ONLY_DESTINATIONS = frozenset({
    "Devices", "Device Information", "Parameters", "Parameter Settings",
    "Grid Parameters", "Safety Parameters", "Protection Parameters",
    "Protection Settings", "More Control",
})
SAFE_NAVIGATION_TARGET = re.compile(
    r"(?i)\b(devices?|device details?|details?|settings?|control|protection|safety|grid|"
    r"connection|active power|volt[\s-]*watt|p\s*\(\s*u\s*\)|volt[\s-]*var|"
    r"q\s*\(\s*u\s*\)|reconnect(?:ion)?|frequency|parameters?|information|general|pv)\b"
)
UNSAFE_ACTION_TARGET = re.compile(
    r"(?i)\b(save|apply|submit|confirm|start|stop|reset|restart|factory|update|upgrade|"
    r"firmware|enable|disable|turn\s+on|turn\s+off|switch|toggle|edit|change|delete|"
    r"remove|pair|bind|commission|calibrat|export\s+control|set\s+value)\b"
)
AUTHENTICATION_BOUNDARY = re.compile(
    r"(?i)\b(log[ -]?in|sign[ -]?in|password|passcode|pin|verification|authori[sz]e|permission)\b"
)
UNSAFE_WIDGET_CLASS = re.compile(r"(?i)(Switch|CheckBox|RadioButton|SeekBar|EditText|Spinner)$")
SETTING_VALUE_ROW = re.compile(
    r"(?i),\s*(?:--|not set|on|off|enabled|disabled|[-+]?\d+(?:\.\d+)?\s*(?:v|hz|s|w|var|%|a)?)\s*$"
)
SENSITIVE = re.compile(
    r"password|passwd|credential|secret|token|email|account|username|login", re.I
)


def decode_content_provider_response(raw_output: str, endpoint: str) -> Any:
    """Strictly decode one Android `content query` row and nested Portal JSON."""
    if endpoint not in PORTAL_ENDPOINTS:
        raise MobileInspectionError(f"Unapproved Portal endpoint: {endpoint}")
    cleaned = raw_output.lstrip("\ufeff").strip()
    rows = re.findall(r"(?:^|\r?\n)Row:\s*\d+\s+result=(.*?)(?=\r?\nRow:|\Z)", cleaned, re.S)
    if len(rows) != 1:
        raise MobileInspectionError(
            f"Portal {endpoint} returned {len(rows)} rows; exactly one fresh row is required"
        )
    try:
        value: Any = json.loads(rows[0].strip())
    except json.JSONDecodeError as error:
        raise MobileInspectionError(f"Portal {endpoint} returned malformed JSON") from error

    for _ in range(6):
        if isinstance(value, dict) and "status" in value:
            if value.get("status") != "success":
                raise MobileInspectionError(f"Portal {endpoint} did not report success")
            if "result" not in value and "data" not in value:
                raise MobileInspectionError(f"Portal {endpoint} success response has no result")
            value = value.get("result", value.get("data"))
            continue
        if isinstance(value, str) and value.strip().startswith(("{", "[", '"')):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise MobileInspectionError(f"Portal {endpoint} contains malformed nested JSON") from error
            continue
        break
    if value in (None, "", [], {}):
        raise MobileInspectionError(f"Portal {endpoint} returned an empty result")
    return value


def query_portal_content_provider(
    serial: str,
    endpoint: str,
    adb_path: Path | None = None,
) -> Any:
    """Query one approved Portal endpoint without exposing the device serial in output."""
    if not serial or any(character.isspace() for character in serial):
        raise MobileInspectionError("A valid Android device serial is required")
    if endpoint not in PORTAL_ENDPOINTS:
        raise MobileInspectionError(f"Unapproved Portal endpoint: {endpoint}")
    adb = (adb_path or default_adb_path()).resolve()
    if not adb.is_file():
        raise MobileInspectionError(f"ADB was not found: {adb}")
    completed = subprocess.run(
        [
            str(adb), "-s", serial, "shell", "content", "query",
            "--uri", f"content://{PORTAL_AUTHORITY}/{endpoint}",
        ],
        capture_output=True,
        text=True,
        shell=False,
        timeout=25,
        check=False,
    )
    if completed.returncode != 0:
        raise MobileInspectionError(f"Portal {endpoint} query failed")
    return decode_content_provider_response(completed.stdout, endpoint)


def iter_accessibility_nodes(tree: dict[str, Any]) -> Iterator[tuple[dict[str, Any], int, int | None]]:
    """Walk only accessibility nodes (not bounds/actions metadata dictionaries)."""
    stack: list[tuple[dict[str, Any], int, int | None]] = [(tree, 0, None)]
    index = 0
    while stack:
        node, depth, parent = stack.pop()
        if not isinstance(node, dict) or "className" not in node:
            continue
        current = index
        index += 1
        yield node, depth, parent
        children = [child for child in node.get("children", []) if isinstance(child, dict)]
        for child in reversed(children):
            stack.append((child, depth + 1, current))


def normalize_accessibility_nodes(tree: dict[str, Any], package: str) -> list[dict[str, Any]]:
    walked = list(iter_accessibility_nodes(tree))
    normalized: list[dict[str, Any]] = []
    for index, (node, depth, parent_index) in enumerate(walked):
        node_package = node.get("packageName")
        if node_package and node_package != package:
            continue
        resource = str(node.get("resourceId") or "")
        if node.get("isPassword") is True or node.get("password") is True or SENSITIVE.search(resource):
            continue
        text = str(node.get("text") or "").strip()
        description = str(node.get("contentDescription") or "").strip()
        hint = str(node.get("hint") or "").strip()
        labels = [value for value in (text, description, hint) if value]
        siblings: list[str] = []
        if parent_index is not None and 0 <= parent_index < len(walked):
            parent_node = walked[parent_index][0]
            for sibling in parent_node.get("children", []):
                if sibling is node or not isinstance(sibling, dict):
                    continue
                sibling_text = str(sibling.get("text") or sibling.get("contentDescription") or "").strip()
                if sibling_text and not SENSITIVE.search(str(sibling.get("resourceId") or "")):
                    siblings.append(sibling_text)
        normalized.append({
            "node_index": index,
            "parent_index": parent_index,
            "depth": depth,
            "class_name": str(node.get("className") or ""),
            "resource_id": resource,
            "text": text,
            "content_description": description,
            "hint": hint,
            "labels": labels,
            "value": text if re.search(r"-?\d", text) else "",
            "ui_context": {"sibling_text": siblings[:8]},
            "clickable": node.get("isClickable") is True,
            "enabled": node.get("isEnabled") is not False,
            "checked": node.get("isChecked") is True,
            "selected": node.get("isSelected") is True,
            "scrollable": node.get("isScrollable") is True,
            "child_count": int(node.get("childCount") or len(node.get("children", []))),
            "visible": node.get("isVisibleToUser") is not False,
            "bounds": node.get("boundsInScreen"),
        })
    return normalized


def _valid_bounds(bounds: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(bounds, dict):
        return None
    try:
        left, top, right, bottom = (
            int(bounds[key]) for key in ("left", "top", "right", "bottom")
        )
    except (KeyError, TypeError, ValueError):
        return None
    if left < 0 or top < 0 or right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def enumerate_navigation_candidates(capture: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve visible safe labels to clickable nodes or clickable parents."""
    nodes = [item for item in capture.get("ui_text", []) if isinstance(item, dict)]
    by_index = {item.get("node_index"): item for item in nodes}
    candidates: dict[tuple[str, tuple[int, int, int, int]], dict[str, Any]] = {}
    for source in nodes:
        labels = [
            str(value).strip()
            for value in source.get("labels", [])
            if isinstance(value, str) and value.strip()
        ]
        for label in labels:
            if (
                not SAFE_NAVIGATION_TARGET.search(label)
                or UNSAFE_ACTION_TARGET.search(label)
                or AUTHENTICATION_BOUNDARY.search(label)
            ):
                continue
            target = source
            seen: set[int] = set()
            while not target.get("clickable"):
                parent_index = target.get("parent_index")
                if not isinstance(parent_index, int) or parent_index in seen:
                    target = {}
                    break
                seen.add(parent_index)
                target = by_index.get(parent_index, {})
            bounds = _valid_bounds(target.get("bounds"))
            class_name = str(target.get("class_name") or "")
            target_labels = [str(value) for value in target.get("labels", [])]
            if (
                not target
                or bounds is None
                or target.get("enabled") is False
                or UNSAFE_WIDGET_CLASS.search(class_name)
                or bounds[3] <= 225
                or any(SETTING_VALUE_ROW.search(value) for value in target_labels)
            ):
                continue
            context = " ".join([label, *target_labels])
            if UNSAFE_ACTION_TARGET.search(context) or AUTHENTICATION_BOUNDARY.search(context):
                continue
            key = (label.casefold(), bounds)
            digest = hashlib.sha256(
                json.dumps([label.casefold(), bounds], separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:12]
            candidates[key] = {
                "element_id": f"nav-{digest}",
                "label": label[:100],
                "class_name": class_name,
                "bounds": {
                    "left": bounds[0], "top": bounds[1],
                    "right": bounds[2], "bottom": bounds[3],
                },
                "source_node_index": source.get("node_index"),
                "target_node_index": target.get("node_index"),
                "safety": "read_only_navigation",
            }

    if capture.get("current_screen") == "GoodWe devices":
        device_cards = []
        for node in nodes:
            bounds = _valid_bounds(node.get("bounds"))
            if not (
                node.get("clickable") is True
                and node.get("enabled") is not False
                and int(node.get("child_count") or 0) >= 4
                and bounds is not None
                and 250 <= bounds[1] < bounds[3] <= 1900
            ):
                continue
            device_cards.append((node, bounds))
        if len(device_cards) == 1:
            node, bounds = device_cards[0]
            digest = hashlib.sha256(
                json.dumps(["single inverter device details", bounds]).encode("utf-8")
            ).hexdigest()[:12]
            candidates[("single inverter device details", bounds)] = {
                "element_id": f"nav-{digest}",
                "label": "Single inverter device details",
                "class_name": str(node.get("class_name") or ""),
                "bounds": {
                    "left": bounds[0], "top": bounds[1],
                    "right": bounds[2], "bottom": bounds[3],
                },
                "source_node_index": node.get("node_index"),
                "target_node_index": node.get("node_index"),
                "safety": "read_only_navigation",
            }
    return sorted(candidates.values(), key=lambda item: (item["label"].casefold(), item["element_id"]))


def screen_fingerprint(capture: dict[str, Any]) -> str:
    """Stable private screen identity used for loop prevention."""
    summary = [
        {
            "labels": item.get("labels", []),
            "bounds": item.get("bounds"),
            "clickable": item.get("clickable"),
        }
        for item in capture.get("ui_text", [])
        if isinstance(item, dict) and (item.get("labels") or item.get("clickable"))
    ]
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"{capture.get('current_screen', 'unknown')}:{digest}"


def local_ocr_capability() -> dict[str, Any]:
    executable = shutil.which("tesseract")
    return {
        "available": bool(executable),
        "engine": "tesseract" if executable else None,
        "reason": None if executable else "No existing local OCR engine is installed.",
    }


def detect_screen(nodes: list[dict[str, Any]]) -> str:
    strings = {
        label.casefold()
        for node in nodes
        for label in node.get("labels", [])
        if isinstance(label, str)
    }
    if {"energy generation", "generation revenue"} <= strings and "devices" in strings:
        return "GoodWe dashboard"
    if "devices" in strings and any("inverter" in value or "device" in value for value in strings):
        return "GoodWe devices"
    if "more control" in strings and "protection settings" in strings:
        return "GoodWe control menu"
    if "protection settings" in strings:
        return "GoodWe protection settings"
    if any("parameter" in value or "protection" in value for value in strings):
        return "GoodWe parameter display"
    if "more control" in strings and (
        "current power" in strings or "today's generation" in strings
    ):
        return "GoodWe device detail"
    if any("device information" in value or "firmware" in value for value in strings):
        return "GoodWe device information"
    return "unclassified GoodWe screen"


def public_diagnostic_labels(nodes: list[dict[str, Any]], limit: int = 40) -> list[str]:
    allowed = re.compile(
        r"(?i)^(home|devices?|inverters?|overview|details?|parameters?|parameter settings|"
        r"grid parameters|safety parameters|protection parameters|protection settings|device information|"
        r"energy generation|generation revenue|grid|solar|load|today|total|capacity|status|"
        r"model|firmware|version|more control|device start/stop|environmental control|"
        r"pv settings|general settings|today's generation|cumulative generation|"
        r"rated power:?|current power|vw[12]|vv[1-4]|furf|.+(?:ramp|reconnect).*)$"
    )
    labels: list[str] = []
    for node in nodes:
        for value in node.get("labels", []):
            if allowed.fullmatch(value) and value not in labels:
                labels.append(value)
        if len(labels) >= limit:
            break
    return labels


def default_adb_path() -> Path:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    base = Path(sdk) if sdk else Path.home() / "AppData/Local/Android/Sdk"
    return (base / "platform-tools/adb.exe").resolve()


def discover_devices(adb_path: Path | None = None) -> dict[str, list[str]]:
    adb = (adb_path or default_adb_path()).resolve()
    if not adb.is_file():
        raise MobileInspectionError(f"ADB was not found: {adb}")
    result = subprocess.run([str(adb), "devices"], capture_output=True, text=True,
                            shell=False, timeout=15, check=False)
    states: dict[str, list[str]] = {"device": [], "unauthorized": [], "offline": []}
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 2:
            states.setdefault(columns[1], []).append(columns[0])
    return states


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def foreground_package(tree: dict[str, Any]) -> str | None:
    for node in _walk(tree):
        package = node.get("packageName") or node.get("package")
        if isinstance(package, str) and package:
            return package
    return None


def collect_ui_text(tree: dict[str, Any], package: str, limit: int = 500) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in _walk(tree):
        node_package = node.get("packageName") or node.get("package")
        if node_package and node_package != package:
            continue
        resource = str(node.get("resourceId") or node.get("resource-id") or "")
        sensitive = re.compile(r"password|passwd|credential|secret|token|email|account|username|login", re.I)
        if node.get("password") is True or sensitive.search(resource):
            continue
        text = node.get("text") or ""
        description = node.get("contentDescription") or node.get("content-desc") or ""
        if text or description:
            items.append({
                "text": str(text), "content_description": str(description),
                "resource_id": resource,
            })
        if len(items) >= limit:
            break
    return items


def tree_contains_sensitive_input(tree: dict[str, Any]) -> bool:
    for node in _walk(tree):
        resource = str(node.get("resourceId") or node.get("resource-id") or "")
        class_name = str(node.get("className") or node.get("class") or "")
        visible_labels = " ".join(
            str(node.get(key) or "") for key in ("text", "contentDescription", "hint")
        )
        editable = node.get("isEditable") is True or class_name.endswith("EditText")
        if (
            node.get("password") is True
            or node.get("isPassword") is True
            or (editable and (SENSITIVE.search(resource) or SENSITIVE.search(visible_labels)))
        ):
            return True
    return False


class ReadOnlyMobileClient:
    """MobileRun driver exposing only approved launch, observation, scroll and back."""

    def __init__(self, serial: str, approved_packages: set[str], artifact_dir: Path) -> None:
        if not serial or any(char.isspace() for char in serial):
            raise MobileInspectionError("A valid device serial is required")
        self.serial = serial
        self.approved_packages = frozenset(approved_packages)
        self.artifact_dir = artifact_dir.resolve()
        self.adb_path = default_adb_path()
        self._driver: Any = None

    async def connect(self) -> None:
        if not self.adb_path.is_file():
            raise MobileInspectionError(f"ADB was not found: {self.adb_path}")
        pong = await asyncio.to_thread(self._query_portal, "ping")
        if not (isinstance(pong, str) and pong.casefold() == "pong"):
            raise MobileInspectionError("MobileRun Portal ping did not return pong")
        try:
            from mobilerun.tools import AndroidDriver
        except ImportError as error:
            raise MobileInspectionError("MobileRun is not installed in this Python environment") from error
        # Portal content-provider queries are the primary observation path.
        # Keep the MobileRun driver in ADB mode for explicitly approved navigation;
        # this avoids enabling Portal's keyboard or changing an input-method setting.
        driver = AndroidDriver(serial=self.serial, use_tcp=False, portal_mode="disabled")
        try:
            await driver.connect()
        except Exception as error:
            raise MobileInspectionError(f"MobileRun Portal connection failed: {error}") from error
        required = {"start_app", "screenshot", "tap", "swipe", "press_button"}
        if not required <= set(driver.supported):
            raise MobileInspectionError("Required read-only MobileRun capabilities are unavailable")
        self._driver = driver

    def _query_portal(self, endpoint: str) -> Any:
        return query_portal_content_provider(self.serial, endpoint, self.adb_path)

    @staticmethod
    def _phone_package(state: Any) -> str | None:
        if not isinstance(state, dict):
            return None
        value = state.get("packageName") or state.get("package")
        return value if isinstance(value, str) and value else None

    async def _require_foreground_from_portal(self, package: str) -> dict[str, Any]:
        state = await asyncio.to_thread(self._query_portal, "phone_state")
        actual = self._phone_package(state)
        if actual != package:
            raise MobileInspectionError(
                f"Expected approved package in foreground; observed {actual or 'unknown'}"
            )
        return state

    async def _fresh_tree_nodes(self, package: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        await self._require_foreground_from_portal(package)
        tree = await asyncio.to_thread(self._query_portal, "a11y_tree_full")
        if not isinstance(tree, dict) or "className" not in tree:
            raise MobileInspectionError("Portal returned no valid accessibility root")
        actual_packages = {
            node.get("packageName")
            for node, _, _ in iter_accessibility_nodes(tree)
            if node.get("packageName")
        }
        if actual_packages != {package}:
            raise MobileInspectionError(
                "Fresh Portal tree does not belong exclusively to the approved package"
            )
        if tree_contains_sensitive_input(tree):
            raise MobileInspectionError(
                "An authentication or credential boundary is visible; autonomous inspection stopped."
            )
        nodes = normalize_accessibility_nodes(tree, package)
        if not nodes or not any(node.get("labels") for node in nodes):
            raise MobileInspectionError("Fresh Portal tree has no readable UI content")
        await self._require_foreground_from_portal(package)
        return tree, nodes

    @property
    def driver(self) -> Any:
        if self._driver is None:
            raise MobileInspectionError("MobileRun is not connected")
        return self._driver

    def _require_package(self, package: str) -> None:
        if package not in self.approved_packages:
            raise MobileInspectionError(f"Package is not in the explicit allow-list: {package}")

    async def launch(self, package: str) -> str:
        self._require_package(package)
        return str(await self.driver.start_app(package))

    async def capture_page(self, package: str, page: str) -> dict[str, Any]:
        self._require_package(package)
        tree, nodes = await self._fresh_tree_nodes(package)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        base = self.artifact_dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', page)}-{stamp}"
        tree_path = base.with_suffix(".json")
        screen_path = base.with_suffix(".png")
        tree_path.write_text(json.dumps(tree, indent=2, default=str), encoding="utf-8")
        screen_path.write_bytes(await self.driver.screenshot())
        return {
            "package": package, "page": page, "captured_at": stamp,
            "tree_path": str(tree_path), "screenshot_path": str(screen_path),
            "evidence_ref": tree_path.name,
            "source": f"content://{PORTAL_AUTHORITY}/a11y_tree_full",
            "node_count": len(nodes),
            "current_screen": detect_screen(nodes),
            "readable_labels": public_diagnostic_labels(nodes),
            "ui_text": nodes,
        }

    async def capture_screenshot(self, package: str, page: str) -> dict[str, Any]:
        """Capture local visual evidence only after a fresh safe-tree check."""
        self._require_package(package)
        _, nodes = await self._fresh_tree_nodes(package)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        safe_page = re.sub(r"[^A-Za-z0-9_.-]", "_", page)
        screen_path = self.artifact_dir / f"{safe_page}-{stamp}.png"
        screen_path.write_bytes(await self.driver.screenshot())
        await self._require_foreground_from_portal(package)
        return {
            "screenshot_ref": screen_path.name,
            "screen": detect_screen(nodes),
            "node_count": len(nodes),
            "ocr": local_ocr_capability(),
        }

    async def tap_element(
        self,
        package: str,
        capture: dict[str, Any],
        element_id: str,
    ) -> dict[str, Any]:
        """Tap one Python-enumerated safe navigation element using fresh bounds."""
        self._require_package(package)
        if package != GOODWE_PACKAGE or not re.fullmatch(r"nav-[a-f0-9]{12}", element_id):
            raise MobileInspectionError("Navigation element identifier is not approved")
        # Re-read the tree immediately before tapping so stale bounds are never reused.
        _, nodes = await self._fresh_tree_nodes(package)
        fresh_capture = {
            "package": package,
            "current_screen": detect_screen(nodes),
            "ui_text": nodes,
        }
        matches = [
            item for item in enumerate_navigation_candidates(fresh_capture)
            if item["element_id"] == element_id
        ]
        if len(matches) != 1:
            raise MobileInspectionError(
                "The approved navigation element is no longer uniquely visible; no tap was sent"
            )
        candidate = matches[0]
        bounds = _valid_bounds(candidate["bounds"])
        if bounds is None:
            raise MobileInspectionError("Approved navigation element has invalid fresh bounds")
        x, y = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
        await self.driver.tap(x, y)
        await asyncio.sleep(1.2)
        await self._require_foreground_from_portal(package)
        return {
            "element_id": element_id,
            "label": candidate["label"],
            "x": x,
            "y": y,
        }

    async def scroll_down(self, package: str) -> None:
        self._require_package(package)
        await self._require_foreground_from_portal(package)
        await self.driver.swipe(540, 1650, 540, 550, duration_ms=500)
        await asyncio.sleep(0.5)
        await self._require_foreground_from_portal(package)

    async def scroll_screen(self, package: str) -> dict[str, Any]:
        await self.scroll_down(package)
        return {"direction": "down", "gesture": [540, 1650, 540, 550, 500]}

    async def back(self, package: str) -> None:
        self._require_package(package)
        await self._require_foreground_from_portal(package)
        await self.driver.press_button("back")
        await asyncio.sleep(0.4)
        await self._require_foreground_from_portal(package)

    async def go_back(self, package: str) -> dict[str, Any]:
        await self.back(package)
        return {"keyevent": "back"}

    async def navigate_to_named_page(self, package: str, capture: dict[str, Any], label: str) -> None:
        """Tap one exact, approved read-only destination; ambiguous matches are refused."""
        self._require_package(package)
        if package != GOODWE_PACKAGE or label not in GOODWE_READ_ONLY_DESTINATIONS:
            raise MobileInspectionError(f"Navigation destination is not approved: {label}")
        await self._require_foreground_from_portal(package)
        matches = []
        for node in capture.get("ui_text", []):
            labels = [str(value) for value in node.get("labels", [])]
            if node.get("clickable") is True and label in labels:
                bounds = node.get("bounds")
                if isinstance(bounds, dict):
                    matches.append(bounds)
        if len(matches) != 1:
            raise MobileInspectionError(
                f"Read-only navigation to {label!r} is ambiguous ({len(matches)} exact matches)"
            )
        bounds = matches[0]
        try:
            left, top, right, bottom = (int(bounds[key]) for key in ("left", "top", "right", "bottom"))
        except (KeyError, TypeError, ValueError) as error:
            raise MobileInspectionError(f"Approved destination {label!r} has invalid bounds") from error
        if right <= left or bottom <= top:
            raise MobileInspectionError(f"Approved destination {label!r} has empty bounds")
        await self.driver.tap((left + right) // 2, (top + bottom) // 2)
        await asyncio.sleep(1.2)
        await self._require_foreground_from_portal(package)

    async def navigate_to_single_device_card(self, package: str, capture: dict[str, Any]) -> None:
        """Open the sole populated GoodWe device card; refuse zero or multiple cards."""
        self._require_package(package)
        if package != GOODWE_PACKAGE or capture.get("current_screen") != "GoodWe devices":
            raise MobileInspectionError("Populated-device navigation is allowed only from GoodWe devices")
        await self._require_foreground_from_portal(package)
        candidates: list[dict[str, Any]] = []
        for node in capture.get("ui_text", []):
            bounds = node.get("bounds")
            if not (
                node.get("clickable") is True
                and int(node.get("child_count") or 0) >= 4
                and isinstance(bounds, dict)
            ):
                continue
            try:
                top, bottom = int(bounds["top"]), int(bounds["bottom"])
            except (KeyError, TypeError, ValueError):
                continue
            if 250 <= top < bottom <= 1900:
                candidates.append(bounds)
        if len(candidates) != 1:
            raise MobileInspectionError(
                f"GoodWe populated device card is ambiguous ({len(candidates)} safe matches)"
            )
        bounds = candidates[0]
        left, top, right, bottom = (int(bounds[key]) for key in ("left", "top", "right", "bottom"))
        await self.driver.tap((left + right) // 2, (top + bottom) // 2)
        await asyncio.sleep(1.2)
        await self._require_foreground_from_portal(package)


def discover_candidate_packages(serial: str, adb_path: Path | None = None) -> list[str]:
    """Return only third-party package names matching known solar/inverter terms."""
    adb = (adb_path or default_adb_path()).resolve()
    result = subprocess.run([str(adb), "-s", serial, "shell", "pm", "list", "packages", "-3"],
                            capture_output=True, text=True, shell=False, timeout=30, check=False)
    if result.returncode != 0:
        raise MobileInspectionError("Third-party package discovery failed")
    pattern = re.compile(r"solar|inverter|isolar|fusion|sems|solis|fronius|enphase|growatt|shine|sungrow", re.I)
    packages = [line.removeprefix("package:").strip() for line in result.stdout.splitlines()]
    return sorted(package for package in packages if pattern.search(package))
