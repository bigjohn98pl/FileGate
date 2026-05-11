from __future__ import annotations

import argparse
import json
import os
import platform as platform_module
from pathlib import Path
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from filegate.linux_portal import (
    detect_sandbox_metadata,
    file_uri_to_path,
    probe_portal_metadata,
)


SCHEMA_VERSION = "0.1"
SAMPLE_APP_PATH = "samples/linux-portal"
TARGET_NAME = "linux-portal"
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
    "flatpak_open_file_portal": {
        "name": "Flatpak open file portal",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "flatpak_save_file_portal": {
        "name": "Flatpak save file portal",
        "automation_level": "semi_automatic",
        "dialog_type": "save_file",
    },
    "portal_cancel_behavior": {
        "name": "Portal cancel behavior",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
        "cancel_expected": True,
    },
    "portal_returns_uri_or_path": {
        "name": "Portal returns URI or path",
        "automation_level": "semi_automatic",
        "dialog_type": "open_file",
    },
    "sandbox_no_home_access_without_grant": {
        "name": "Sandbox no home access without grant",
        "automation_level": "automatic",
        "dialog_type": "open_file",
    },
}


@dataclass
class PortalSelectionResult:
    values: list[str]
    cancelled: bool
    returned_resource_type: str
    observed_resource_type: str
    notes: list[dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FileGate Linux portal sample target.")
    parser.add_argument("--scenario", required=True, help="Absolute or relative path to a JSON scenario file.")
    parser.add_argument("--output", help="Optional result JSON path.")
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
        "automation_level": case_payload.get("automation_level") or defaults.get("automation_level") or "semi_automatic",
        "target_hint": case_payload.get("target_hint") or "portal",
    }

    if merged["automation_level"] not in AUTOMATION_LEVELS:
        raise ValueError(f"Unsupported automation_level '{merged['automation_level']}'.")

    return merged


def infer_dialog_type(scenario: dict[str, Any]) -> str:
    dialog = scenario.get("dialog", {})
    if dialog.get("type"):
        return str(dialog["type"])
    defaults = CASE_DEFAULTS.get(scenario["case"]["id"], {})
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
        "sandbox": incoming.get("sandbox") or detect_sandbox_metadata().sandbox,
    }


def platform_system() -> str:
    system = platform_module.system().lower()
    if system.startswith("darwin"):
        return "macos"
    return system or "unknown"


def build_target_payload() -> dict[str, Any]:
    return {
        "name": TARGET_NAME,
        "version": "0.1",
        "sample_app": SAMPLE_APP_PATH,
    }


def execute_case(scenario: dict[str, Any], case_payload: dict[str, Any], dialog_type: str) -> PortalSelectionResult:
    simulation = scenario.get("simulation", {})
    execution_context = scenario.get("execution_context", {})
    portal_metadata = execution_context.get("portal") or probe_portal_metadata().to_dict()
    sandbox_metadata = execution_context.get("sandbox") or detect_sandbox_metadata().to_dict()
    notes: list[dict[str, str]] = []

    notes.extend(_metadata_notes(portal_metadata=portal_metadata, sandbox_metadata=sandbox_metadata))

    if case_payload["id"] == "sandbox_no_home_access_without_grant" or simulation.get("metadata_only"):
        return PortalSelectionResult(
            values=[],
            cancelled=False,
            returned_resource_type="unknown",
            observed_resource_type="metadata_only",
            notes=notes,
        )

    if simulation.get("enabled"):
        return execute_simulation(simulation, notes)

    # Phase 3 initial landing: direct portal interactive execution path is intentionally explicit
    # about current limitations in this repo. The target captures portal capability metadata and
    # degrades cleanly rather than pretending it executed a selection that it did not observe.
    limitation_message = (
        "Interactive direct portal execution is not fully automated in this repository revision. "
        "Use simulation mode for deterministic coverage, or extend this target with a Request/Response "
        "D-Bus flow for live portal interactions."
    )
    notes.append({"code": "PORTAL_INTERACTIVE_LIMITATION", "message": limitation_message})

    if not portal_metadata.get("available"):
        notes.append(
            {
                "code": "PORTAL_UNAVAILABLE",
                "message": "The XDG Desktop Portal FileChooser interface was not available for this session.",
            }
        )
    return PortalSelectionResult(
        values=[],
        cancelled=False,
        returned_resource_type="unknown",
        observed_resource_type="unobserved",
        notes=notes,
    )


def execute_simulation(simulation: dict[str, Any], notes: list[dict[str, str]]) -> PortalSelectionResult:
    notes.append(
        {
            "code": "SIMULATED",
            "message": "Result was produced using the documented simulation mode rather than a live portal Request/Response flow.",
        }
    )

    if simulation.get("cancel"):
        notes.append(
            {
                "code": "PORTAL_RESPONSE",
                "message": "Simulated portal response code 1 (user cancelled).",
            }
        )
        return PortalSelectionResult(
            values=[],
            cancelled=True,
            returned_resource_type="unknown",
            observed_resource_type="none",
            notes=notes,
        )

    selected_uri = simulation.get("selected_uri")
    selected_path = simulation.get("selected_path")
    selected_paths = simulation.get("selected_paths") or []

    if selected_uri:
        converted = file_uri_to_path(str(selected_uri))
        notes.append(
            {
                "code": "PORTAL_URI_OBSERVED",
                "message": f"Observed portal-style URI result: {selected_uri}",
            }
        )
        if converted:
            notes.append(
                {
                    "code": "PORTAL_URI_CONVERTED_TO_PATH",
                    "message": f"Converted file URI to local path: {converted}",
                }
            )
        if selected_path:
            notes.append(
                {
                    "code": "PORTAL_PATH_COMPARISON",
                    "message": f"Scenario also supplied a path-form comparison value: {selected_path}",
                }
            )
        value = str(selected_uri)
        return PortalSelectionResult(
            values=[value],
            cancelled=False,
            returned_resource_type="uri",
            observed_resource_type="uri",
            notes=notes,
        )

    if selected_paths:
        notes.append(
            {
                "code": "PORTAL_PATHS_OBSERVED",
                "message": f"Scenario supplied {len(selected_paths)} path value(s) instead of URIs.",
            }
        )
        return PortalSelectionResult(
            values=[str(value) for value in selected_paths],
            cancelled=False,
            returned_resource_type="path",
            observed_resource_type="path",
            notes=notes,
        )

    if selected_path:
        notes.append(
            {
                "code": "PORTAL_PATH_OBSERVED",
                "message": f"Scenario supplied a direct path value instead of a URI: {selected_path}",
            }
        )
        return PortalSelectionResult(
            values=[str(selected_path)],
            cancelled=False,
            returned_resource_type="path",
            observed_resource_type="path",
            notes=notes,
        )

    return PortalSelectionResult(
        values=[],
        cancelled=True,
        returned_resource_type="unknown",
        observed_resource_type="none",
        notes=notes,
    )


def compute_access_flags(selection: PortalSelectionResult, dialog_type: str) -> tuple[bool, bool]:
    if not selection.values:
        return False, False

    if selection.returned_resource_type == "uri":
        local_path = file_uri_to_path(selection.values[0])
        if local_path is None:
            return False, False
        values = [local_path]
    else:
        values = selection.values

    if dialog_type == "save_file":
        target = Path(values[0])
        if target.exists():
            return os.access(values[0], os.R_OK), os.access(values[0], os.W_OK)
        parent = target.parent if str(target.parent) else Path.cwd()
        return False, os.access(parent, os.W_OK)

    return os.access(values[0], os.R_OK), os.access(values[0], os.W_OK)


def build_result_payload(
    scenario: dict[str, Any],
    case_payload: dict[str, Any],
    dialog_type: str,
    selection: PortalSelectionResult,
    duration_ms: int,
    error: Exception | None = None,
) -> dict[str, Any]:
    expectation = scenario.get("expectation", {})
    case_defaults = CASE_DEFAULTS.get(case_payload["id"], {})
    cancel_expected = bool(expectation.get("cancel_is_expected", case_defaults.get("cancel_expected", False)))
    portal_expected = bool((scenario.get("execution_context", {}) or {}).get("portal_expected", False))
    notes = list(selection.notes)

    if error is not None:
        notes.append({"code": "EXECUTION_ERROR", "message": str(error)})
        return {
            "status": "fail",
            "duration_ms": duration_ms,
            "returned_resource_type": "unknown",
            "returned_value_example": None,
            "can_read": False,
            "can_write": False,
            "error_code": "UNKNOWN_ERROR",
            "notes": notes,
        }

    if case_payload["id"] == "sandbox_no_home_access_without_grant":
        sandbox_metadata = (scenario.get("execution_context", {}) or {}).get("sandbox") or detect_sandbox_metadata().to_dict()
        home_access = str(sandbox_metadata.get("host_home_access") or "unknown")
        status = "pass" if home_access in {"none", "not_applicable"} else "warn"
        if home_access == "unknown":
            status = "inconclusive"
        notes.append(
            {
                "code": "SANDBOX_HOME_ACCESS_OBSERVED",
                "message": f"Observed host home access classification: {home_access}.",
            }
        )
        return {
            "status": status,
            "duration_ms": duration_ms,
            "returned_resource_type": "unknown",
            "returned_value_example": None,
            "can_read": False,
            "can_write": False,
            "error_code": None if status in {"pass", "warn"} else "SANDBOX_DENIED",
            "notes": notes,
        }

    if selection.cancelled:
        notes.append({"code": "USER_CANCELLED", "message": "The portal interaction returned no resource."})
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

    can_read, can_write = compute_access_flags(selection, dialog_type)

    if portal_expected and selection.observed_resource_type == "unobserved":
        return {
            "status": "unsupported",
            "duration_ms": duration_ms,
            "returned_resource_type": "unknown",
            "returned_value_example": None,
            "can_read": False,
            "can_write": False,
            "error_code": "BACKEND_UNSUPPORTED",
            "notes": notes,
        }

    status = "pass"
    if cancel_expected:
        status = "fail"
        notes.append(
            {
                "code": "UNEXPECTED_SELECTION",
                "message": "A resource was selected even though the scenario expected cancellation.",
            }
        )

    notes.append(
        {
            "code": "RESOURCE_TYPE_OBSERVED",
            "message": f"Observed resource behavior category: {selection.observed_resource_type}.",
        }
    )
    return {
        "status": status,
        "duration_ms": duration_ms,
        "returned_resource_type": selection.returned_resource_type,
        "returned_value_example": selection.values if len(selection.values) > 1 else selection.values[0],
        "can_read": can_read,
        "can_write": can_write,
        "error_code": None,
        "notes": notes,
    }


def _metadata_notes(*, portal_metadata: dict[str, Any], sandbox_metadata: dict[str, Any]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = [
        {
            "code": "PORTAL_CAPABILITIES",
            "message": (
                "Portal availability="
                f"{portal_metadata.get('available')}"
                ", filechooser_version="
                f"{portal_metadata.get('filechooser_version')}"
                ", supports_open_file="
                f"{portal_metadata.get('supports_open_file')}"
                ", supports_save_file="
                f"{portal_metadata.get('supports_save_file')}"
            ),
        },
        {
            "code": "SANDBOX_CONTEXT",
            "message": (
                f"sandbox={sandbox_metadata.get('sandbox')}, "
                f"host_home_access={sandbox_metadata.get('host_home_access')}, "
                f"filesystem_permissions={sandbox_metadata.get('filesystem_permissions') or []}, "
                f"documents_portal_mount={sandbox_metadata.get('documents_portal_mount')}"
            ),
        },
    ]
    for message in portal_metadata.get("notes") or []:
        notes.append({"code": "PORTAL_NOTE", "message": str(message)})
    for message in sandbox_metadata.get("notes") or []:
        notes.append({"code": "SANDBOX_NOTE", "message": str(message)})
    return notes


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
    if payload["result"]["status"] not in RESULT_STATUSES:
        raise ValueError(f"Unsupported result.status '{payload['result']['status']}'.")


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
    selection: PortalSelectionResult | None = None
    execution_error: Exception | None = None
    try:
        selection = execute_case(scenario, case_payload, dialog_type)
    except Exception as error:
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
            selection=selection or PortalSelectionResult([], True, "unknown", "none", []),
            duration_ms=duration_ms,
            error=execution_error,
        ),
    }
    validate_result_payload(result_payload)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(output_path)
    return 0 if result_payload["result"]["status"] in {"pass", "warn", "manual_required", "unsupported", "inconclusive"} else 1


if __name__ == "__main__":
    sys.exit(main())