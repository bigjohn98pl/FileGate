"""JSON aggregation for FileGate run reporting."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from filegate.artifact_validation import (
    load_json_object,
    validate_case_result_payload,
    validate_run_summary_consistency,
    validate_run_summary_payload,
)


def build_report_payload(run_dir: Path) -> dict[str, Any]:
    """Load a FileGate run directory and build a report payload."""
    normalized_run_dir = run_dir.expanduser().resolve()
    summary_path = normalized_run_dir / "run-summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Run summary not found: {summary_path}")

    summary_payload = load_json_object(summary_path, artifact_kind="run summary artifact")
    validate_run_summary_payload(summary_payload, source=summary_path)

    cases: list[dict[str, Any]] = []
    loaded_case_results: list[tuple[Path, dict[str, Any]]] = []

    for case_index, case_summary in enumerate(summary_payload.get("cases", []), start=1):
        case_id = str(case_summary.get("case_id") or f"unknown_case_{case_index}")
        result_path_value = case_summary.get("result_path")
        result_path = _resolve_result_path(normalized_run_dir, case_id, result_path_value)

        case_payload = load_json_object(result_path, artifact_kind="case result artifact")
        validate_case_result_payload(
            case_payload,
            source=result_path,
            expected_run_id=str(summary_payload.get("run_id") or "") or None,
            expected_case_id=case_id,
        )
        loaded_case_results.append((result_path, case_payload))
        cases.append(case_payload)

    validate_run_summary_consistency(summary_payload, loaded_case_results, source=summary_path)

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
        "warnings": [],
        "cases": cases,
    }


def render_json_report(run_dir: Path) -> str:
    """Render an aggregated FileGate run report as JSON."""
    return json.dumps(build_report_payload(run_dir), indent=2, ensure_ascii=False) + "\n"


def _resolve_result_path(run_dir: Path, case_id: str, result_path_value: Any) -> Path:
    if not result_path_value:
        raise ValueError(f"Run summary entry for case '{case_id}' is missing result_path.")

    # Compatibility strategy:
    # Older summaries may store result_path relative to a project root instead of the run directory.
    # When the canonical in-run location exists, prefer it explicitly before falling back to the
    # serialized path value.
    local_case_result = (run_dir / case_id / "result.json").resolve()
    if local_case_result.exists():
        return local_case_result

    result_path = Path(str(result_path_value))
    if result_path.is_absolute():
        return result_path
    candidate = (run_dir / result_path).resolve()
    if candidate.exists():
        return candidate

    workspace_relative = (Path.cwd() / result_path).resolve()
    if workspace_relative.exists():
        return workspace_relative

    return candidate