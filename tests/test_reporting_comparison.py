from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from filegate.reporting.comparison import build_comparison_payload


def _case_payload(*, run_id: str, target_name: str, result_path: str, note_message: str) -> dict:
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
            "name": target_name,
            "version": "1.0",
            "sample_app": f"samples/{target_name}",
        },
        "case": {
            "id": "wrong_extension_selected",
            "name": "Wrong extension selected",
            "automation_level": "semi_automatic",
        },
        "result": {
            "status": "warn",
            "duration_ms": 15,
            "returned_resource_type": "path",
            "returned_value_example": result_path,
            "can_read": False,
            "can_write": True,
            "error_code": None,
            "notes": [{"code": "WRONG_EXTENSION_PRESERVED", "message": note_message}],
        },
    }


def _summary(*, run_id: str, target_name: str, result_path: str) -> dict:
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
            "name": target_name,
            "version": "1.0",
            "sample_app": f"samples/{target_name}",
        },
        "cases": [
            {
                "case_id": "wrong_extension_selected",
                "status": "warn",
                "duration_ms": 15,
                "result_path": result_path,
            }
        ],
    }


class ComparisonReportingTests(unittest.TestCase):
    def test_comparison_surfaces_value_and_note_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            left = root / "left"
            right = root / "right"
            left_case_dir = left / "wrong_extension_selected"
            right_case_dir = right / "wrong_extension_selected"
            left_case_dir.mkdir(parents=True)
            right_case_dir.mkdir(parents=True)

            left_result = _case_payload(
                run_id="run-left",
                target_name="electron",
                result_path="/tmp/example.pdf",
                note_message="Electron preserved .pdf.",
            )
            right_result = _case_payload(
                run_id="run-right",
                target_name="python-tkinter",
                result_path="/tmp/example.txt",
                note_message="Tkinter corrected to .txt.",
            )

            (left_case_dir / "result.json").write_text(
                json.dumps(left_result, indent=2) + "\n", encoding="utf-8"
            )
            (right_case_dir / "result.json").write_text(
                json.dumps(right_result, indent=2) + "\n", encoding="utf-8"
            )
            (left / "run-summary.json").write_text(
                json.dumps(
                    _summary(
                        run_id="run-left",
                        target_name="electron",
                        result_path="wrong_extension_selected/result.json",
                    ),
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (right / "run-summary.json").write_text(
                json.dumps(
                    _summary(
                        run_id="run-right",
                        target_name="python-tkinter",
                        result_path="wrong_extension_selected/result.json",
                    ),
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            payload = build_comparison_payload(left, right)
            case = payload["cases"][0]
            note_codes = {note["code"] for note in case["notes"]}

            self.assertIn("returned_value_difference", note_codes)
            self.assertIn("note_difference", note_codes)


if __name__ == "__main__":
    unittest.main()
