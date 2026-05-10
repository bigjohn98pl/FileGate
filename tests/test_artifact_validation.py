from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from filegate.artifact_validation import (
    ArtifactValidationError,
    validate_case_result_payload,
    validate_run_summary_consistency,
    validate_run_summary_payload,
)
from filegate.reporting.json import build_report_payload


def make_valid_case_result(
    *,
    run_id: str = "2026-05-10T01-55-36Z-electron",
    case_id: str = "open_file_single",
    status: str = "pass",
    duration_ms: int = 42,
    error_code: str | None = None,
) -> dict:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "platform": {
            "os": "linux",
            "distribution": "Fedora Linux",
            "version": "43",
            "desktop_environment": "KDE",
            "session_type": "wayland",
            "sandbox": "none",
        },
        "target": {
            "name": "electron",
            "version": "35.7.5",
            "sample_app": "samples/electron",
        },
        "case": {
            "id": case_id,
            "name": "Open file single",
            "automation_level": "semi_automatic",
        },
        "result": {
            "status": status,
            "duration_ms": duration_ms,
            "returned_resource_type": "path",
            "returned_value_example": "/tmp/example.txt",
            "can_read": True,
            "can_write": False,
            "error_code": error_code,
            "notes": [{"code": "INFO", "message": "Validation fixture."}],
        },
    }


def make_valid_run_summary(*, run_id: str, result_path: str, status: str = "pass", duration_ms: int = 42) -> dict:
    return {
        "schema_version": "0.1",
        "run_id": run_id,
        "generated_at": "2026-05-10T01:55:36.572286+00:00",
        "platform": {
            "os": "linux",
            "distribution": "Fedora Linux",
            "version": "43",
            "desktop_environment": "KDE",
            "session_type": "wayland",
            "sandbox": "none",
        },
        "target": {
            "name": "electron",
            "version": "35.7.5",
            "sample_app": "samples/electron",
        },
        "cases": [
            {
                "case_id": "open_file_single",
                "status": status,
                "duration_ms": duration_ms,
                "result_path": result_path,
            }
        ],
    }


class ArtifactValidationTests(unittest.TestCase):
    def test_valid_case_result_payload_passes(self) -> None:
        payload = make_valid_case_result()
        validated = validate_case_result_payload(
            payload,
            expected_run_id=payload["run_id"],
            expected_case_id=payload["case"]["id"],
            expected_automation_level=payload["case"]["automation_level"],
        )
        self.assertIs(validated, payload)

    def test_invalid_status_is_rejected(self) -> None:
        payload = make_valid_case_result()
        payload["result"]["status"] = "maybe"

        with self.assertRaises(ArtifactValidationError) as exc:
            validate_case_result_payload(payload)

        self.assertIn("result.status must be one of", str(exc.exception))

    def test_invalid_error_code_is_rejected(self) -> None:
        payload = make_valid_case_result(status="fail", error_code="BAD_NEWS")

        with self.assertRaises(ArtifactValidationError) as exc:
            validate_case_result_payload(payload)

        self.assertIn("result.error_code", str(exc.exception))

    def test_pass_with_fatal_error_code_is_rejected(self) -> None:
        payload = make_valid_case_result(status="pass", error_code="UNKNOWN_ERROR")

        with self.assertRaises(ArtifactValidationError) as exc:
            validate_case_result_payload(payload)

        self.assertIn("status='pass'", str(exc.exception))

    def test_invalid_summary_structure_is_rejected(self) -> None:
        summary = make_valid_run_summary(run_id="run-1", result_path="open_file_single/result.json")
        summary["cases"][0]["duration_ms"] = -1

        with self.assertRaises(ArtifactValidationError) as exc:
            validate_run_summary_payload(summary)

        self.assertIn("cases[1].duration_ms", str(exc.exception))

    def test_summary_consistency_detects_status_mismatch(self) -> None:
        case_payload = make_valid_case_result(status="pass")
        summary = make_valid_run_summary(
            run_id=case_payload["run_id"],
            result_path="open_file_single/result.json",
            status="fail",
            duration_ms=case_payload["result"]["duration_ms"],
        )

        with self.assertRaises(ArtifactValidationError) as exc:
            validate_run_summary_consistency(summary, [(Path("/tmp/result.json"), case_payload)])

        self.assertIn("Run summary status", str(exc.exception))

    def test_report_loader_accepts_valid_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir) / "run-1"
            case_dir = run_dir / "open_file_single"
            case_dir.mkdir(parents=True)

            case_payload = make_valid_case_result(run_id="run-1")
            result_path = case_dir / "result.json"
            result_path.write_text(json.dumps(case_payload, indent=2) + "\n", encoding="utf-8")

            summary = make_valid_run_summary(
                run_id="run-1",
                result_path="open_file_single/result.json",
                status=case_payload["result"]["status"],
                duration_ms=case_payload["result"]["duration_ms"],
            )
            (run_dir / "run-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

            report = build_report_payload(run_dir)
            self.assertEqual(report["total_cases"], 1)
            self.assertEqual(report["counts_by_status"], {"pass": 1})

    def test_report_loader_rejects_missing_required_case_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir) / "run-1"
            case_dir = run_dir / "open_file_single"
            case_dir.mkdir(parents=True)

            case_payload = make_valid_case_result(run_id="run-1")
            del case_payload["case"]["automation_level"]
            result_path = case_dir / "result.json"
            result_path.write_text(json.dumps(case_payload, indent=2) + "\n", encoding="utf-8")

            summary = make_valid_run_summary(run_id="run-1", result_path="open_file_single/result.json")
            (run_dir / "run-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

            with self.assertRaises(ArtifactValidationError) as exc:
                build_report_payload(run_dir)

            self.assertIn("case.automation_level", str(exc.exception))


if __name__ == "__main__":
    unittest.main()