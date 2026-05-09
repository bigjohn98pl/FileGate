"""JSON aggregation for FileGate run reporting."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


def build_report_payload(run_dir: Path) -> dict[str, Any]:
    """Load a FileGate run directory and build a report payload."""
    normalized_run_dir = run_dir.expanduser().resolve()
    summary_path = normalized_run_dir / "run-summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Run summary not found: {summary_path}")

    summary_payload = _load_json(summary_path)
    warnings: list[dict[str, str]] = []
    cases: list[dict[str, Any]] = []

    for case_index, case_summary in enumerate(summary_payload.get("cases", []), start=1):
        case_id = str(case_summary.get("case_id") or f"unknown_case_{case_index}")
        result_path_value = case_summary.get("result_path")
        if not result_path_value:
            warnings.append(
                _warning(
                    code="missing_result_path",
                    message=f"Case '{case_id}' is missing result_path in run-summary.json.",
                )
            )
            cases.append(_build_placeholder_case(case_id, case_summary, "Missing result_path in run summary."))
            continue

        result_path = _resolve_result_path(normalized_run_dir, case_id, result_path_value)

        if not result_path.exists():
            warnings.append(
                _warning(
                    code="missing_result_file",
                    message=f"Case '{case_id}' result file is missing: {result_path}",
                )
            )
            cases.append(
                _build_placeholder_case(
                    case_id,
                    case_summary,
                    f"Result file not found: {result_path}",
                )
            )
            continue

        try:
            case_payload = _load_json(result_path)
        except json.JSONDecodeError as exc:
            warnings.append(
                _warning(
                    code="invalid_result_json",
                    message=f"Case '{case_id}' result file is not valid JSON: {result_path} ({exc})",
                )
            )
            cases.append(
                _build_placeholder_case(
                    case_id,
                    case_summary,
                    f"Result file is invalid JSON: {result_path}",
                )
            )
            continue

        case_warnings = _validate_case_payload(case_payload, case_summary, result_path)
        warnings.extend(case_warnings)
        notes = list(case_payload.get("result", {}).get("notes", []))
        notes.extend(
            {
                "code": warning["code"],
                "message": warning["message"],
            }
            for warning in case_warnings
        )
        case_payload.setdefault("result", {})
        case_payload["result"]["notes"] = notes
        cases.append(case_payload)

    counts_by_status = dict(
        sorted(Counter(str(case.get("result", {}).get("status", "inconclusive")) for case in cases).items())
    )

    return {
        "schema_version": str(summary_payload.get("schema_version", "0.1")),
        "report_format": "json",
        "run_id": summary_payload.get("run_id"),
        "generated_at": summary_payload.get("generated_at"),
        "source_run_directory": str(normalized_run_dir),
        "platform": summary_payload.get("platform"),
        "target": summary_payload.get("target"),
        "total_cases": len(cases),
        "counts_by_status": counts_by_status,
        "warnings": warnings,
        "cases": cases,
    }


def render_json_report(run_dir: Path) -> str:
    """Render an aggregated FileGate run report as JSON."""
    return json.dumps(build_report_payload(run_dir), indent=2, ensure_ascii=False) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}, got {type(payload).__name__}")
    return payload


def _warning(*, code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _resolve_result_path(run_dir: Path, case_id: str, result_path_value: Any) -> Path:
    local_case_result = (run_dir / case_id / "result.json").resolve()
    if local_case_result.parent.exists():
        return local_case_result

    result_path = Path(str(result_path_value))
    if result_path.is_absolute():
        return result_path
    return (run_dir / result_path).resolve()


def _build_placeholder_case(
    case_id: str,
    case_summary: dict[str, Any],
    note_message: str,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": None,
        "platform": None,
        "target": None,
        "case": {
            "id": case_id,
            "name": case_id.replace("_", " ").title(),
            "automation_level": "unknown",
        },
        "result": {
            "status": str(case_summary.get("status") or "inconclusive"),
            "duration_ms": int(case_summary.get("duration_ms") or 0),
            "returned_resource_type": "unknown",
            "returned_value_example": None,
            "can_read": None,
            "can_write": None,
            "error_code": None,
            "notes": [_warning(code="incomplete_source_result", message=note_message)],
        },
    }


def _validate_case_payload(
    case_payload: dict[str, Any],
    case_summary: dict[str, Any],
    result_path: Path,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for field in ("schema_version", "run_id", "platform", "target", "case", "result"):
        if field not in case_payload:
            warnings.append(
                _warning(
                    code="missing_case_field",
                    message=f"Result file {result_path} is missing top-level field '{field}'.",
                )
            )

    case_block = case_payload.get("case")
    if not isinstance(case_block, dict):
        warnings.append(
            _warning(code="invalid_case_block", message=f"Result file {result_path} has invalid 'case' object.")
        )
    else:
        case_id = str(case_summary.get("case_id") or "")
        payload_case_id = str(case_block.get("id") or "")
        if case_id and payload_case_id and case_id != payload_case_id:
            warnings.append(
                _warning(
                    code="case_id_mismatch",
                    message=(
                        f"Run summary case_id '{case_id}' does not match result payload "
                        f"case.id '{payload_case_id}' in {result_path}."
                    ),
                )
            )
        for field in ("id", "automation_level"):
            if field not in case_block:
                warnings.append(
                    _warning(
                        code="missing_case_subfield",
                        message=f"Result file {result_path} is missing case.{field}.",
                    )
                )

    result_block = case_payload.get("result")
    if not isinstance(result_block, dict):
        warnings.append(
            _warning(code="invalid_result_block", message=f"Result file {result_path} has invalid 'result' object.")
        )
        return warnings

    for field in ("status", "duration_ms", "returned_resource_type"):
        if field not in result_block:
            warnings.append(
                _warning(
                    code="missing_result_subfield",
                    message=f"Result file {result_path} is missing result.{field}.",
                )
            )

    summary_status = case_summary.get("status")
    result_status = result_block.get("status")
    if summary_status and result_status and str(summary_status) != str(result_status):
        warnings.append(
            _warning(
                code="status_mismatch",
                message=(
                    f"Run summary status '{summary_status}' does not match result "
                    f"status '{result_status}' for {result_path}."
                ),
            )
        )

    return warnings