from __future__ import annotations

import argparse
import json
import os
import platform as platform_module
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib, Gtk
except (ImportError, ValueError):  # pragma: no cover - environment-specific fallback
    gi = None
    Gio = None
    GLib = None
    Gtk = None

SCHEMA_VERSION = "0.1"
SAMPLE_APP_PATH = "samples/python-gtk"
TARGET_NAME = "python-gtk"
AUTOMATION_LEVELS = {"automatic", "semi_automatic", "manual"}
RESULT_STATUSES = {
    "pass",
    "fail",
    "warn",
    "skip",
    "manual_required",
    "unsupported",
    "timeout",
    "blocked",
    "inconclusive",
}

CASE_DEFAULTS: dict[str, dict[str, Any]] = {
    "open_file_single": {
        "name": "Open file single",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "open_file_multiple": {
        "name": "Open file multiple",
        "automation_level": "semi_automatic",
        "dialog_type": "open_files",
    },
    "open_folder": {
        "name": "Open folder",
        "automation_level": "semi_automatic",
        "dialog_type": "open_folder",
    },
    "save_file_new": {
        "name": "Save file new",
        "automation_level": "semi_automatic",
        "dialog_type": "save_file",
    },
    "save_file_overwrite": {
        "name": "Save file overwrite",
        "automation_level": "semi_automatic",
        "dialog_type": "save_file",
    },
    "cancel_open_dialog": {
        "name": "Cancel open dialog",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
        "cancel_expected": True,
    },
    "cancel_save_dialog": {
        "name": "Cancel save dialog",
        "automation_level": "semi_automatic",
        "dialog_type": "save_file",
        "cancel_expected": True,
    },
}


@dataclass(slots=True)
class SelectionResult:
    values: list[str]
    cancelled: bool
    returned_resource_type: str
    notes: list[dict[str, str]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the FileGate Python GTK sample target.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Absolute or relative path to a JSON scenario file.",
    )
    parser.add_argument(
        "--output",
        help="Optional result JSON path. Defaults to samples/python-gtk/out/<case-id>.result.json.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_case(case_payload: dict[str, Any]) -> dict[str, Any]:
    case_id = case_payload.get("id")
    if not case_id:
        raise ValueError("Scenario must define case.id.")

    defaults = CASE_DEFAULTS.get(case_id, {})
    merged = {
        "id": case_id,
        "name": case_payload.get("name") or defaults.get("name") or case_id,
        "automation_level": case_payload.get("automation_level")
        or defaults.get("automation_level")
        or "semi_automatic",
    }

    if merged["automation_level"] not in AUTOMATION_LEVELS:
        raise ValueError(
            f"Unsupported automation_level '{merged['automation_level']}'. "
            f"Expected one of: {sorted(AUTOMATION_LEVELS)}"
        )

    return merged


def infer_dialog_type(scenario: dict[str, Any]) -> str:
    dialog = scenario.get("dialog", {})
    if dialog.get("type"):
        return str(dialog["type"])

    case_id = scenario["case"]["id"]
    defaults = CASE_DEFAULTS.get(case_id, {})
    if defaults.get("dialog_type"):
        return str(defaults["dialog_type"])

    raise ValueError("Scenario must define dialog.type or use a known case.id.")


def resolve_output_path(base_dir: Path, case_id: str, cli_output: str | None) -> Path:
    if cli_output:
        return Path(cli_output).expanduser().resolve()
    return (base_dir / "out" / f"{case_id}.result.json").resolve()


def build_platform_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    incoming = scenario.get("platform", {})
    return {
        "os": incoming.get("os") or platform_system(),
        "distribution": incoming.get("distribution") or os.environ.get("XDG_CURRENT_DESKTOP") or "unknown",
        "version": incoming.get("version") or platform_module.release(),
        "desktop_environment": incoming.get("desktop_environment") or os.environ.get("XDG_CURRENT_DESKTOP") or "unknown",
        "session_type": incoming.get("session_type") or os.environ.get("XDG_SESSION_TYPE") or "unknown",
        "sandbox": incoming.get("sandbox") or detect_sandbox(),
    }


def platform_system() -> str:
    system = platform_module.system().lower()
    if system.startswith("darwin"):
        return "macos"
    return system or "unknown"


def detect_sandbox() -> str:
    if os.environ.get("FLATPAK_ID"):
        return "flatpak"
    if os.environ.get("SNAP"):
        return "snap"
    if os.environ.get("APPIMAGE"):
        return "appimage"
    return "none"


def build_target_payload() -> dict[str, Any]:
    version = "unknown"
    if Gtk is not None:
        version = ".".join(
            str(value)
            for value in (
                Gtk.get_major_version(),
                Gtk.get_minor_version(),
                Gtk.get_micro_version(),
            )
        )

    return {
        "name": TARGET_NAME,
        "version": version,
        "sample_app": SAMPLE_APP_PATH,
    }


def normalize_filetypes(raw_filetypes: Any) -> list[tuple[str, str]]:
    if not raw_filetypes:
        return []

    normalized = []
    for item in raw_filetypes:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            normalized.append((str(item[0]), str(item[1])))
        else:
            raise ValueError(
                "dialog.filetypes entries must be [label, pattern] pairs."
            )
    return normalized


def execute_selection(scenario: dict[str, Any], dialog_type: str) -> SelectionResult:
    simulation = scenario.get("simulation", {})
    if simulation.get("enabled"):
        return execute_simulation(simulation, dialog_type)

    if Gtk is None or Gio is None or GLib is None:
        raise RuntimeError("GTK 4 / PyGObject is unavailable in this Python environment.")
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError("GTK dialogs require a graphical display session.")

    return execute_interactive_dialog(scenario, dialog_type)


def execute_simulation(simulation: dict[str, Any], dialog_type: str) -> SelectionResult:
    if simulation.get("cancel"):
        return SelectionResult(values=[], cancelled=True, returned_resource_type="unknown")

    if dialog_type == "open_files":
        selected_values = simulation.get("selected_paths") or []
    else:
        selected_value = simulation.get("selected_path")
        selected_values = [selected_value] if selected_value else []

    values = [str(value) for value in selected_values if value]
    return SelectionResult(
        values=values,
        cancelled=len(values) == 0,
        returned_resource_type="path" if values else "unknown",
    )


def execute_interactive_dialog(scenario: dict[str, Any], dialog_type: str) -> SelectionResult:
    app = Gtk.Application(application_id="dev.filegate.python_gtk", flags=0)
    state: dict[str, Any] = {
        "selection": SelectionResult(values=[], cancelled=True, returned_resource_type="unknown"),
        "error": None,
        "done": False,
    }
    loop = GLib.MainLoop()

    def on_activate(application: Gtk.Application) -> None:
        window = Gtk.ApplicationWindow(application=application)
        window.set_title("FileGate GTK sample")
        window.set_default_size(1, 1)
        window.set_visible(False)

        dialog = build_file_dialog(scenario)
        if dialog_type == "open_file":
            dialog.open(window, None, lambda obj, result: _finish_open(obj, result, state, loop))
        elif dialog_type == "open_files":
            dialog.open_multiple(window, None, lambda obj, result: _finish_open_multiple(obj, result, state, loop))
        elif dialog_type == "open_folder":
            dialog.select_folder(window, None, lambda obj, result: _finish_open(obj, result, state, loop, folder=True))
        elif dialog_type == "save_file":
            dialog.save(window, None, lambda obj, result: _finish_save(obj, result, state, loop))
        else:
            state["error"] = ValueError(f"Unsupported dialog.type '{dialog_type}'.")
            state["done"] = True
            loop.quit()

    app.connect("activate", on_activate)
    app.register(None)
    app.activate()
    loop.run()

    app.quit()
    if state["error"] is not None:
        raise state["error"]
    return state["selection"]


def build_file_dialog(scenario: dict[str, Any]) -> Gtk.FileDialog:
    dialog_payload = scenario.get("dialog", {})
    dialog = Gtk.FileDialog()
    if dialog_payload.get("title"):
        dialog.set_title(str(dialog_payload["title"]))

    initialdir = dialog_payload.get("initialdir")
    initialfile = dialog_payload.get("initialfile")
    if initialdir:
        dialog.set_initial_folder(Gio.File.new_for_path(str(initialdir)))
    if initialfile and initialdir:
        dialog.set_initial_file(Gio.File.new_for_path(str(Path(str(initialdir)) / str(initialfile))))
    elif initialfile:
        dialog.set_initial_name(str(initialfile))

    filters = build_filters(dialog_payload.get("filetypes"))
    if filters:
        store = Gio.ListStore.new(Gtk.FileFilter)
        for file_filter in filters:
            store.append(file_filter)
        dialog.set_filters(store)
        dialog.set_default_filter(filters[0])

    return dialog


def build_filters(raw_filetypes: Any) -> list[Gtk.FileFilter]:
    filters: list[Gtk.FileFilter] = []
    for label, pattern_blob in normalize_filetypes(raw_filetypes):
        file_filter = Gtk.FileFilter()
        file_filter.set_name(label)
        for pattern in str(pattern_blob).split(";"):
            normalized = pattern.strip()
            if normalized:
                file_filter.add_pattern(normalized)
        filters.append(file_filter)
    return filters


def _is_cancelled_error(error: GLib.Error) -> bool:
    message = error.message.lower()
    return "dismissed" in message or "cancel" in message


def _finish_open(
    dialog: Gtk.FileDialog,
    result: Gio.AsyncResult,
    state: dict[str, Any],
    loop: GLib.MainLoop,
    *,
    folder: bool = False,
) -> None:
    try:
        selected_file = dialog.select_folder_finish(result) if folder else dialog.open_finish(result)
        path = selected_file.get_path() if selected_file is not None else None
        values = [path] if path else []
        state["selection"] = SelectionResult(
            values=values,
            cancelled=len(values) == 0,
            returned_resource_type="path" if values else "unknown",
            notes=[
                {
                    "code": "GTK_NATIVE_DIALOG",
                    "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                }
            ],
        )
    except GLib.Error as error:
        if _is_cancelled_error(error):
            state["selection"] = SelectionResult(
                values=[],
                cancelled=True,
                returned_resource_type="unknown",
                notes=[
                    {
                        "code": "GTK_NATIVE_DIALOG",
                        "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                    }
                ],
            )
        else:
            state["error"] = error
    finally:
        state["done"] = True
        loop.quit()


def _finish_open_multiple(
    dialog: Gtk.FileDialog,
    result: Gio.AsyncResult,
    state: dict[str, Any],
    loop: GLib.MainLoop,
) -> None:
    try:
        model = dialog.open_multiple_finish(result)
        values: list[str] = []
        for index in range(model.get_n_items()):
            selected_file = model.get_item(index)
            path = selected_file.get_path() if selected_file is not None else None
            if path:
                values.append(path)
        state["selection"] = SelectionResult(
            values=values,
            cancelled=len(values) == 0,
            returned_resource_type="path" if values else "unknown",
            notes=[
                {
                    "code": "GTK_NATIVE_DIALOG",
                    "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                }
            ],
        )
    except GLib.Error as error:
        if _is_cancelled_error(error):
            state["selection"] = SelectionResult(
                values=[],
                cancelled=True,
                returned_resource_type="unknown",
                notes=[
                    {
                        "code": "GTK_NATIVE_DIALOG",
                        "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                    }
                ],
            )
        else:
            state["error"] = error
    finally:
        state["done"] = True
        loop.quit()


def _finish_save(
    dialog: Gtk.FileDialog,
    result: Gio.AsyncResult,
    state: dict[str, Any],
    loop: GLib.MainLoop,
) -> None:
    try:
        selected_file = dialog.save_finish(result)
        path = selected_file.get_path() if selected_file is not None else None
        values = [path] if path else []
        state["selection"] = SelectionResult(
            values=values,
            cancelled=len(values) == 0,
            returned_resource_type="path" if values else "unknown",
            notes=[
                {
                    "code": "GTK_NATIVE_DIALOG",
                    "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                }
            ],
        )
    except GLib.Error as error:
        if _is_cancelled_error(error):
            state["selection"] = SelectionResult(
                values=[],
                cancelled=True,
                returned_resource_type="unknown",
                notes=[
                    {
                        "code": "GTK_NATIVE_DIALOG",
                        "message": "Interactive result used GTK 4 native FileDialog APIs, which may route through portal/native backends depending on the desktop session.",
                    }
                ],
            )
        else:
            state["error"] = error
    finally:
        state["done"] = True
        loop.quit()


def compute_access_flags(dialog_type: str, values: list[str]) -> tuple[bool, bool]:
    if not values:
        return False, False

    if dialog_type == "open_files":
        can_read = all(os.access(value, os.R_OK) for value in values)
        return can_read, False

    value = values[0]
    if dialog_type in {"open_file", "open_folder"}:
        return os.access(value, os.R_OK), os.access(value, os.W_OK)

    if dialog_type == "save_file":
        target = Path(value)
        if target.exists():
            return os.access(value, os.R_OK), os.access(value, os.W_OK)
        parent = target.parent if str(target.parent) else Path.cwd()
        return False, os.access(parent, os.W_OK)

    return False, False


def validate_selection_count(
    scenario: dict[str, Any],
    case_payload: dict[str, Any],
    selection: SelectionResult,
) -> list[dict[str, str]]:
    expectation = scenario.get("expectation", {})
    case_id = case_payload["id"]

    exact_count = expectation.get("expected_selection_count")
    min_count = expectation.get("min_selection_count")
    max_count = expectation.get("max_selection_count")

    if exact_count is None:
        if case_id == "open_file_single":
            exact_count = 1
        elif case_id == "open_file_multiple":
            min_count = 2 if min_count is None else min_count

    actual_count = len(selection.values)
    issues: list[dict[str, str]] = []

    if exact_count is not None and actual_count != int(exact_count):
        issues.append(
            {
                "code": "SELECTION_COUNT_MISMATCH",
                "message": (
                    f"Scenario expected exactly {int(exact_count)} selected path(s), "
                    f"but received {actual_count}."
                ),
            }
        )

    if min_count is not None and actual_count < int(min_count):
        issues.append(
            {
                "code": "SELECTION_COUNT_TOO_LOW",
                "message": (
                    f"Scenario expected at least {int(min_count)} selected path(s), "
                    f"but received {actual_count}."
                ),
            }
        )
    if max_count is not None and actual_count > int(max_count):
        issues.append(
            {
                "code": "SELECTION_COUNT_TOO_HIGH",
                "message": (
                    f"Scenario expected at most {int(max_count)} selected path(s), "
                    f"but received {actual_count}."
                ),
            }
        )

    return issues


def build_result_payload(
    scenario: dict[str, Any],
    case_payload: dict[str, Any],
    dialog_type: str,
    selection: SelectionResult,
    duration_ms: int,
    error: Exception | None = None,
) -> dict[str, Any]:
    expectation = scenario.get("expectation", {})
    case_defaults = CASE_DEFAULTS.get(case_payload["id"], {})
    cancel_expected = bool(
        expectation.get("cancel_is_expected", case_defaults.get("cancel_expected", False))
    )

    notes: list[dict[str, str]] = list(selection.notes)
    if scenario.get("simulation", {}).get("enabled"):
        notes.append(
            {
                "code": "SIMULATED",
                "message": "Result was produced using the documented simulation mode rather than an interactive GTK dialog.",
            }
        )

    if error is not None:
        notes.append({"code": "EXECUTION_ERROR", "message": str(error)})
        return {
            "status": "unsupported" if is_backend_error(error) else "fail",
            "duration_ms": duration_ms,
            "returned_resource_type": "unknown",
            "returned_value_example": None,
            "can_read": False,
            "can_write": False,
            "error_code": classify_error_code(error),
            "notes": notes,
        }

    can_read, can_write = compute_access_flags(dialog_type, selection.values)

    if selection.cancelled:
        notes.append(
            {
                "code": "USER_CANCELLED",
                "message": "The dialog was cancelled and no resource was returned.",
            }
        )
        status = "pass" if cancel_expected else "fail"
        return {
            "status": status,
            "duration_ms": duration_ms,
            "returned_resource_type": selection.returned_resource_type,
            "returned_value_example": None,
            "can_read": False,
            "can_write": False,
            "error_code": "USER_CANCELLED",
            "notes": notes,
        }

    selection_count_issues = validate_selection_count(scenario, case_payload, selection)
    notes.extend(selection_count_issues)

    if cancel_expected:
        notes.append(
            {
                "code": "UNEXPECTED_SELECTION",
                "message": "A resource was selected even though the scenario expected a cancel action.",
            }
        )
        status = "fail"
    elif selection_count_issues:
        status = "fail"
    else:
        status = "pass"

    return {
        "status": status,
        "duration_ms": duration_ms,
        "returned_resource_type": selection.returned_resource_type,
        "returned_value_example": selection.values if dialog_type == "open_files" else selection.values[0],
        "can_read": can_read,
        "can_write": can_write,
        "error_code": None,
        "notes": notes,
    }


def is_backend_error(error: Exception) -> bool:
    if isinstance(error, RuntimeError):
        return True
    if GLib is not None and isinstance(error, GLib.Error):
        message = error.message.lower()
        return "portal" in message or "display" in message or "gtk" in message
    return False


def classify_error_code(error: Exception) -> str:
    message = str(error).lower()
    if "unavailable" in message or "pygobject" in message:
        return "BACKEND_UNSUPPORTED"
    if "display" in message:
        return "RESOURCE_UNAVAILABLE"
    if "portal" in message:
        return "PORTAL_UNAVAILABLE"
    if "dismissed" in message or "cancel" in message:
        return "USER_CANCELLED"
    return "UNKNOWN_ERROR"


def generate_run_id(target_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    host_os = platform_system()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown").lower().replace(" ", "-")
    return f"{timestamp}-{host_os}-{desktop}-{target_name}"


def validate_result_payload(payload: dict[str, Any]) -> None:
    required_top_level = {"schema_version", "run_id", "platform", "target", "case", "result"}
    missing_top_level = required_top_level.difference(payload)
    if missing_top_level:
        raise ValueError(f"Result payload missing top-level fields: {sorted(missing_top_level)}")

    case_required = {"id", "automation_level"}
    missing_case = case_required.difference(payload["case"])
    if missing_case:
        raise ValueError(f"Result payload missing case fields: {sorted(missing_case)}")

    result_required = {"status", "duration_ms", "returned_resource_type"}
    missing_result = result_required.difference(payload["result"])
    if missing_result:
        raise ValueError(f"Result payload missing result fields: {sorted(missing_result)}")

    if payload["result"]["status"] not in RESULT_STATUSES:
        raise ValueError(f"Unsupported result.status '{payload['result']['status']}'.")

    if not isinstance(payload["result"]["duration_ms"], int) or payload["result"]["duration_ms"] < 0:
        raise ValueError("result.duration_ms must be a non-negative integer.")


def main() -> int:
    args = parse_args()
    scenario_path = Path(args.scenario).expanduser().resolve()
    base_dir = Path(__file__).resolve().parent
    scenario = load_json(scenario_path)
    case_payload = ensure_case(scenario.get("case", {}))
    dialog_type = infer_dialog_type({**scenario, "case": case_payload})
    output_path = resolve_output_path(base_dir, case_payload["id"], args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    selection: SelectionResult | None = None
    execution_error: Exception | None = None

    try:
        selection = execute_selection(scenario, dialog_type)
    except Exception as error:  # pragma: no cover - exercised in environment-specific runs
        execution_error = error

    duration_ms = int((time.perf_counter() - started) * 1000)
    result_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": scenario.get("run_id") or generate_run_id(TARGET_NAME),
        "platform": build_platform_payload(scenario),
        "target": build_target_payload(),
        "case": case_payload,
        "result": build_result_payload(
            scenario=scenario,
            case_payload=case_payload,
            dialog_type=dialog_type,
            selection=selection or SelectionResult([], True, "unknown"),
            duration_ms=duration_ms,
            error=execution_error,
        ),
    }

    validate_result_payload(result_payload)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(output_path)
    return 0 if result_payload["result"]["status"] in {"pass", "warn", "manual_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())