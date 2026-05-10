from __future__ import annotations

import argparse
import json
import os
import platform as platform_module
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import TclError, filedialog
except ImportError:  # pragma: no cover - environment-specific fallback
    tk = None
    TclError = RuntimeError
    filedialog = None

SCHEMA_VERSION = "0.1"
SAMPLE_APP_PATH = "samples/python-tkinter"
TARGET_NAME = "python-tkinter"
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
    "filter_pdf_only": {
        "name": "Filter PDF only",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "filter_images_only": {
        "name": "Filter images only",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "filter_multiple_mime_types": {
        "name": "Filter multiple MIME types",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "extension_auto_append_on_save": {
        "name": "Extension auto append on save",
        "automation_level": "semi_automatic",
        "dialog_type": "save_file",
    },
    "wrong_extension_selected": {
        "name": "Wrong extension selected",
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


@dataclass
class SelectionResult:
    values: list[str]
    cancelled: bool
    returned_resource_type: str
    notes: list[dict[str, str]] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the FileGate Python Tkinter sample target.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Absolute or relative path to a JSON scenario file.",
    )
    parser.add_argument(
        "--output",
        help="Optional result JSON path. Defaults to samples/python-tkinter/out/<case-id>.result.json.",
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


def build_target_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    incoming = scenario.get("target") or {}
    if incoming.get("name") and incoming.get("version") and incoming.get("sample_app"):
        return {
            "name": str(incoming["name"]),
            "version": str(incoming["version"]),
            "sample_app": str(incoming["sample_app"]),
        }

    version = "unknown"
    if tk is not None:
        version = str(getattr(tk, "TkVersion", "unknown"))

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

    if tk is None or filedialog is None:
        raise RuntimeError("Tkinter is unavailable in this Python environment.")

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    dialog = scenario.get("dialog", {})
    options: dict[str, Any] = {}
    for key in ("title", "initialdir", "initialfile", "defaultextension"):
        if dialog.get(key):
            options[key] = dialog[key]

    if "mustexist" in dialog:
        options["mustexist"] = bool(dialog["mustexist"])

    filetypes = normalize_filetypes(dialog.get("filetypes"))
    if filetypes:
        options["filetypes"] = filetypes

    try:
        if dialog_type == "open_file":
            selected = filedialog.askopenfilename(**options)
            values = [selected] if selected else []
        elif dialog_type == "open_files":
            selected = filedialog.askopenfilenames(**options)
            values = [str(value) for value in selected] if selected else []
        elif dialog_type == "open_folder":
            selected = filedialog.askdirectory(**options)
            values = [selected] if selected else []
        elif dialog_type == "save_file":
            selected = filedialog.asksaveasfilename(**options)
            values = [selected] if selected else []
        else:
            raise ValueError(f"Unsupported dialog.type '{dialog_type}'.")
    finally:
        root.destroy()

    return SelectionResult(
        values=values,
        cancelled=len(values) == 0,
        returned_resource_type="path" if values else "unknown",
        notes=[],
    )


def execute_simulation(simulation: dict[str, Any], dialog_type: str) -> SelectionResult:
    if simulation.get("cancel"):
        return SelectionResult(values=[], cancelled=True, returned_resource_type="unknown", notes=[])

    if dialog_type == "open_files":
        selected_values = simulation.get("selected_paths") or []
    else:
        selected_value = simulation.get("selected_path")
        selected_values = [selected_value] if selected_value else []

    values = [str(value) for value in selected_values if value]
    notes: list[dict[str, str]] = []
    if simulation.get("selected_filter_label"):
        notes.append(
            {
                "code": "SELECTED_FILTER_LABEL",
                "message": f"Simulation recorded selected filter label '{simulation['selected_filter_label']}'.",
            }
        )
    return SelectionResult(
        values=values,
        cancelled=len(values) == 0,
        returned_resource_type="path" if values else "unknown",
        notes=notes,
    )


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


def evaluate_filter_expectations(
    scenario: dict[str, Any],
    dialog_type: str,
    selection: SelectionResult,
) -> tuple[list[dict[str, str]], str | None]:
    dialog = scenario.get("dialog", {})
    expectation = scenario.get("expectation", {})
    notes: list[dict[str, str]] = []

    filetypes = normalize_filetypes(dialog.get("filetypes"))
    if filetypes:
        configured = ", ".join(f"{label} ({pattern})" for label, pattern in filetypes)
        notes.append(
            {
                "code": "CONFIGURED_FILTERS",
                "message": f"Configured dialog filters: {configured}.",
            }
        )

    selected_filter_label = expectation.get("selected_filter_label")
    if selected_filter_label:
        notes.append(
            {
                "code": "FILTER_INTENT",
                "message": f"Scenario exercised filter intent '{selected_filter_label}'.",
            }
        )

    if dialog_type != "open_file" or selection.cancelled or not selection.values:
        return notes, None

    allowed_extensions = expectation.get("allowed_extensions") or []
    if not allowed_extensions:
        return notes, None

    selected_path = Path(selection.values[0])
    selected_extension = selected_path.suffix.lower()
    normalized_allowed = {str(value).lower() for value in allowed_extensions}
    if selected_extension in normalized_allowed:
        notes.append(
            {
                "code": "FILTER_MATCHED_SELECTION",
                "message": (
                    f"Selected file extension '{selected_extension}' matched the allowed filter set "
                    f"{sorted(normalized_allowed)}."
                ),
            }
        )
        return notes, None

    notes.append(
        {
            "code": "FILTER_MISMATCH",
            "message": (
                f"Selected file extension '{selected_extension or '(none)'}' did not match the allowed filter set "
                f"{sorted(normalized_allowed)}. Native dialogs may allow manual override or expose filters as advisory only."
            ),
        }
    )
    return notes, "warn"


def evaluate_save_expectations(
    scenario: dict[str, Any],
    dialog_type: str,
    selection: SelectionResult,
) -> tuple[list[dict[str, str]], str | None]:
    expectation = scenario.get("expectation", {})
    notes: list[dict[str, str]] = []

    if dialog_type != "save_file" or selection.cancelled or not selection.values:
        return notes, None

    selected_path = Path(selection.values[0])
    selected_extension = selected_path.suffix.lower()
    expected_extension = str(expectation.get("expected_extension") or "").lower()

    if expectation.get("expect_auto_append") and expected_extension:
        if selected_extension == expected_extension:
            notes.append(
                {
                    "code": "AUTO_APPEND_OBSERVED",
                    "message": (
                        f"Returned save path used extension '{selected_extension}', matching the configured default extension."
                    ),
                }
            )
            return notes, None

        notes.append(
            {
                "code": "AUTO_APPEND_NOT_OBSERVED",
                "message": (
                    f"Returned save path used extension '{selected_extension or '(none)'}' instead of the configured default extension '{expected_extension}'. "
                    "Some dialog backends treat default extensions as advisory only."
                ),
            }
        )
        return notes, "warn"

    mismatched_extension = str(expectation.get("mismatched_extension") or "").lower()
    if mismatched_extension and expected_extension:
        if selected_extension == mismatched_extension:
            notes.append(
                {
                    "code": "WRONG_EXTENSION_PRESERVED",
                    "message": (
                        f"Returned save path preserved the mismatched extension '{mismatched_extension}' instead of coercing to '{expected_extension}'."
                    ),
                }
            )
            return notes, "warn"
        if selected_extension == expected_extension:
            notes.append(
                {
                    "code": "WRONG_EXTENSION_CORRECTED",
                    "message": (
                        f"Returned save path used the configured extension '{expected_extension}' rather than the mismatched extension '{mismatched_extension}'."
                    ),
                }
            )
            return notes, None

        notes.append(
            {
                "code": "WRONG_EXTENSION_ALTERNATE_RESULT",
                "message": (
                    f"Returned save path used extension '{selected_extension or '(none)'}', which differs from both the configured '{expected_extension}' and mismatched '{mismatched_extension}' extensions."
                ),
            }
        )
        return notes, "warn"

    return notes, None


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

    notes: list[dict[str, str]] = list(selection.notes or [])
    if scenario.get("simulation", {}).get("enabled"):
        notes.append(
            {
                "code": "SIMULATED",
                "message": "Result was produced using the documented simulation mode rather than an interactive Tk dialog.",
            }
        )

    if error is not None:
        notes.append({"code": "EXECUTION_ERROR", "message": str(error)})
        return {
            "status": "unsupported" if isinstance(error, (RuntimeError, TclError)) else "fail",
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

    filter_notes, filter_status = evaluate_filter_expectations(scenario, dialog_type, selection)
    notes.extend(filter_notes)
    save_notes, save_status = evaluate_save_expectations(scenario, dialog_type, selection)
    notes.extend(save_notes)

    if not scenario.get("simulation", {}).get("enabled") and (
        case_payload["id"].startswith("filter_") or case_payload["id"] in {"extension_auto_append_on_save", "wrong_extension_selected"}
    ):
        notes.append(
            {
                "code": "NATIVE_DIALOG_LIMITATION",
                "message": (
                    "Tk native dialogs do not expose deterministic APIs for reading the actively chosen filter or proving whether the backend auto-appended an extension; "
                    "results should be interpreted as best-effort observations from the returned path."
                ),
            }
        )

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
    elif filter_status == "warn" or save_status == "warn":
        status = "warn"
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


def classify_error_code(error: Exception) -> str:
    message = str(error).lower()
    if "tkinter is unavailable" in message:
        return "BACKEND_UNSUPPORTED"
    if "no display name" in message or "couldn't connect to display" in message:
        return "RESOURCE_UNAVAILABLE"
    if isinstance(error, TclError):
        return "RESOURCE_UNAVAILABLE"
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
        "target": build_target_payload(scenario),
        "case": case_payload,
        "result": build_result_payload(
            scenario=scenario,
            case_payload=case_payload,
            dialog_type=dialog_type,
            selection=selection or SelectionResult([], True, "unknown", []),
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
    sys.exit(main())
