"""Explicit validation helpers for FileGate result artifacts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "0.1"
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
RETURNED_RESOURCE_TYPES = {"path", "uri", "handle", "unknown"}
ERROR_CODES = {
    "USER_CANCELLED",
    "PERMISSION_DENIED",
    "RESOURCE_NOT_FOUND",
    "RESOURCE_UNAVAILABLE",
    "BACKEND_UNSUPPORTED",
    "PORTAL_UNAVAILABLE",
    "SANDBOX_DENIED",
    "PERSISTENCE_DENIED",
    "ACCESS_REVOKED",
    "UNKNOWN_ERROR",
}

_PLATFORM_FIELDS = (
    "os",
    "distribution",
    "version",
    "desktop_environment",
    "session_type",
    "sandbox",
)
_TARGET_FIELDS = ("name", "version", "sample_app")


class ArtifactValidationError(ValueError):
    """Raised when a FileGate artifact violates documented schema rules."""

    def __init__(self, artifact_kind: str, source: Path | str | None, errors: Iterable[str]) -> None:
        self.artifact_kind = artifact_kind
        self.source = Path(source) if isinstance(source, Path) else source
        self.errors = tuple(str(error) for error in errors)
        subject = artifact_kind
        if source is not None:
            subject = f"{artifact_kind} at {source}"
        message = subject + " is invalid:\n" + "\n".join(f"- {error}" for error in self.errors)
        super().__init__(message)


def load_json_object(path: Path, *, artifact_kind: str) -> dict[str, Any]:
    """Load a JSON object from disk and convert parser failures to validation failures."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactValidationError(artifact_kind, path, ["Artifact file does not exist."]) from exc
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(
            artifact_kind,
            path,
            [
                (
                    "Artifact is not valid JSON "
                    f"(line {exc.lineno}, column {exc.colno}): {exc.msg}"
                )
            ],
        ) from exc

    if not isinstance(payload, dict):
        raise ArtifactValidationError(
            artifact_kind,
            path,
            [f"Artifact root must be a JSON object, got {type(payload).__name__}."],
        )
    return payload


def validate_case_result_payload(
    payload: dict[str, Any],
    *,
    source: Path | str | None = None,
    expected_run_id: str | None = None,
    expected_case_id: str | None = None,
    expected_automation_level: str | None = None,
) -> dict[str, Any]:
    """Validate one canonical FileGate case-result payload."""
    errors: list[str] = []
    _validate_schema_version(payload, errors, field_name="schema_version")
    _validate_non_empty_string(payload.get("run_id"), errors, field_name="run_id")
    _validate_platform_block(payload.get("platform"), errors, field_name="platform")
    _validate_target_block(payload.get("target"), errors, field_name="target")
    case_block = _validate_case_block(payload.get("case"), errors, field_name="case")
    result_block = _validate_result_block(payload.get("result"), errors, field_name="result")

    if expected_run_id is not None and payload.get("run_id") != expected_run_id:
        errors.append(
            f"run_id must match the active run ('{expected_run_id}'), got '{payload.get('run_id')}'."
        )

    if case_block is not None and expected_case_id is not None and case_block.get("id") != expected_case_id:
        errors.append(
            f"case.id must match the executed case ('{expected_case_id}'), got '{case_block.get('id')}'."
        )

    if (
        case_block is not None
        and expected_automation_level is not None
        and case_block.get("automation_level") != expected_automation_level
    ):
        errors.append(
            "case.automation_level must match the executed case definition "
            f"('{expected_automation_level}'), got '{case_block.get('automation_level')}'."
        )

    if result_block is not None:
        error_code = result_block.get("error_code")
        if result_block.get("status") == "pass" and error_code not in {None, "USER_CANCELLED"}:
            errors.append(
                "result.status='pass' may not use a fatal result.error_code; "
                f"got '{error_code}'."
            )

    _raise_if_errors("case result artifact", source, errors)
    return payload


def validate_run_summary_payload(
    payload: dict[str, Any],
    *,
    source: Path | str | None = None,
) -> dict[str, Any]:
    """Validate the FileGate run-summary artifact shape."""
    errors: list[str] = []
    _validate_schema_version(payload, errors, field_name="schema_version")
    _validate_non_empty_string(payload.get("run_id"), errors, field_name="run_id")
    _validate_non_empty_string(payload.get("generated_at"), errors, field_name="generated_at")
    if isinstance(payload.get("generated_at"), str):
        try:
            datetime.fromisoformat(str(payload["generated_at"]))
        except ValueError:
            errors.append("generated_at must be a valid ISO-8601 timestamp.")

    _validate_platform_block(payload.get("platform"), errors, field_name="platform")
    _validate_target_block(payload.get("target"), errors, field_name="target")

    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append(f"cases must be an array, got {type(cases).__name__}.")
        _raise_if_errors("run summary artifact", source, errors)
        return payload

    seen_case_ids: set[str] = set()
    for index, case_summary in enumerate(cases, start=1):
        field_name = f"cases[{index}]"
        if not isinstance(case_summary, dict):
            errors.append(f"{field_name} must be an object, got {type(case_summary).__name__}.")
            continue

        case_id = case_summary.get("case_id")
        _validate_non_empty_string(case_id, errors, field_name=f"{field_name}.case_id")
        if isinstance(case_id, str) and case_id in seen_case_ids:
            errors.append(f"{field_name}.case_id '{case_id}' is duplicated in the run summary.")
        elif isinstance(case_id, str):
            seen_case_ids.add(case_id)

        _validate_enum(
            case_summary.get("status"),
            RESULT_STATUSES,
            errors,
            field_name=f"{field_name}.status",
        )
        _validate_non_negative_integer(
            case_summary.get("duration_ms"),
            errors,
            field_name=f"{field_name}.duration_ms",
        )
        _validate_non_empty_string(
            case_summary.get("result_path"),
            errors,
            field_name=f"{field_name}.result_path",
        )

    _raise_if_errors("run summary artifact", source, errors)
    return payload


def validate_run_summary_consistency(
    summary_payload: dict[str, Any],
    case_results: Iterable[tuple[Path, dict[str, Any]]],
    *,
    source: Path | str | None = None,
) -> None:
    """Validate that a run summary agrees with the loaded per-case result artifacts."""
    errors: list[str] = []
    loaded_by_case_id: dict[str, tuple[Path, dict[str, Any]]] = {}

    for result_path, case_payload in case_results:
        case_id = str(((case_payload.get("case") or {}).get("id") or "")).strip()
        if not case_id:
            errors.append(f"Loaded case result {result_path} is missing case.id.")
            continue
        if case_id in loaded_by_case_id:
            errors.append(f"Multiple case result artifacts were loaded for case_id '{case_id}'.")
            continue
        loaded_by_case_id[case_id] = (result_path, case_payload)

    for index, case_summary in enumerate(summary_payload.get("cases", []), start=1):
        if not isinstance(case_summary, dict):
            continue

        case_id = str(case_summary.get("case_id") or "").strip()
        if not case_id:
            continue

        loaded = loaded_by_case_id.get(case_id)
        if loaded is None:
            errors.append(
                f"Run summary case '{case_id}' does not have a matching loaded result artifact."
            )
            continue

        result_path, case_payload = loaded
        validate_case_result_payload(
            case_payload,
            source=result_path,
            expected_run_id=str(summary_payload.get("run_id") or "") or None,
            expected_case_id=case_id,
        )
        result_block = case_payload["result"]

        if case_summary.get("status") != result_block.get("status"):
            errors.append(
                "Run summary status for case "
                f"'{case_id}' is '{case_summary.get('status')}', but the result artifact stores "
                f"'{result_block.get('status')}'."
            )
        if case_summary.get("duration_ms") != result_block.get("duration_ms"):
            errors.append(
                "Run summary duration_ms for case "
                f"'{case_id}' is '{case_summary.get('duration_ms')}', but the result artifact stores "
                f"'{result_block.get('duration_ms')}'."
            )

    _raise_if_errors("run artifact set", source, errors)


def _validate_schema_version(payload: dict[str, Any], errors: list[str], *, field_name: str) -> None:
    if field_name not in payload:
        errors.append(f"Missing required field '{field_name}'.")
        return
    value = payload.get(field_name)
    if value != SCHEMA_VERSION:
        errors.append(f"{field_name} must be '{SCHEMA_VERSION}', got '{value}'.")


def _validate_platform_block(value: Any, errors: list[str], *, field_name: str) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object, got {type(value).__name__}.")
        return
    for subfield in _PLATFORM_FIELDS:
        if subfield not in value:
            errors.append(f"{field_name}.{subfield} is required.")
            continue
        subvalue = value.get(subfield)
        if subvalue is not None and not isinstance(subvalue, str):
            errors.append(
                f"{field_name}.{subfield} must be a string or null, got {type(subvalue).__name__}."
            )


def _validate_target_block(value: Any, errors: list[str], *, field_name: str) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object, got {type(value).__name__}.")
        return
    for subfield in _TARGET_FIELDS:
        _validate_non_empty_string(value.get(subfield), errors, field_name=f"{field_name}.{subfield}")


def _validate_case_block(value: Any, errors: list[str], *, field_name: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object, got {type(value).__name__}.")
        return None

    _validate_non_empty_string(value.get("id"), errors, field_name=f"{field_name}.id")
    _validate_enum(
        value.get("automation_level"),
        AUTOMATION_LEVELS,
        errors,
        field_name=f"{field_name}.automation_level",
    )
    if "name" in value and value.get("name") is not None and not isinstance(value.get("name"), str):
        errors.append(f"{field_name}.name must be a string when present.")
    return value


def _validate_result_block(value: Any, errors: list[str], *, field_name: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object, got {type(value).__name__}.")
        return None

    _validate_enum(value.get("status"), RESULT_STATUSES, errors, field_name=f"{field_name}.status")
    _validate_non_negative_integer(
        value.get("duration_ms"),
        errors,
        field_name=f"{field_name}.duration_ms",
    )
    _validate_enum(
        value.get("returned_resource_type"),
        RETURNED_RESOURCE_TYPES,
        errors,
        field_name=f"{field_name}.returned_resource_type",
    )

    can_read = value.get("can_read")
    if can_read is not None and not isinstance(can_read, bool):
        errors.append(f"{field_name}.can_read must be a boolean or null, got {type(can_read).__name__}.")

    can_write = value.get("can_write")
    if can_write is not None and not isinstance(can_write, bool):
        errors.append(f"{field_name}.can_write must be a boolean or null, got {type(can_write).__name__}.")

    error_code = value.get("error_code")
    if error_code is not None:
        _validate_enum(error_code, ERROR_CODES, errors, field_name=f"{field_name}.error_code")

    notes = value.get("notes")
    if notes is not None:
        if not isinstance(notes, list):
            errors.append(f"{field_name}.notes must be an array when present, got {type(notes).__name__}.")
        else:
            for index, note in enumerate(notes, start=1):
                note_field = f"{field_name}.notes[{index}]"
                if not isinstance(note, dict):
                    errors.append(f"{note_field} must be an object, got {type(note).__name__}.")
                    continue
                _validate_non_empty_string(note.get("code"), errors, field_name=f"{note_field}.code")
                _validate_non_empty_string(note.get("message"), errors, field_name=f"{note_field}.message")

    return value


def _validate_non_empty_string(value: Any, errors: list[str], *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field_name} must be a non-empty string.")


def _validate_enum(value: Any, allowed: set[str], errors: list[str], *, field_name: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        errors.append(f"{field_name} must be one of [{allowed_values}], got {value!r}.")


def _validate_non_negative_integer(value: Any, errors: list[str], *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{field_name} must be a non-negative integer.")


def _raise_if_errors(artifact_kind: str, source: Path | str | None, errors: list[str]) -> None:
    if errors:
        raise ArtifactValidationError(artifact_kind, source, errors)