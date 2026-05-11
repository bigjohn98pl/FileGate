from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from filegate.cases import DEFAULT_CASE_REGISTRY
from filegate.environment import PlatformMetadata
from filegate.runner import RunRequest, Runner, TargetConfig
from filegate.targets import build_python_tkinter_target


def _platform() -> PlatformMetadata:
    return PlatformMetadata(
        os="linux",
        distribution="Fedora Linux",
        version="43",
        desktop_environment="KDE",
        session_type="wayland",
        sandbox="none",
    )


class RunnerStabilityPersistenceTests(unittest.TestCase):
    def _python_target(self) -> TargetConfig:
        return build_python_tkinter_target(Path(__file__).resolve().parents[1])

    def test_registry_includes_new_stability_and_persistence_cases(self) -> None:
        cases = {case.case_id: case for case in DEFAULT_CASE_REGISTRY.all()}

        self.assertEqual(cases["open_dialog_multiple_times"].automation_level, "semi_automatic")
        self.assertEqual(cases["open_dialog_multiple_times"].orchestration, "repeat_dialog")
        self.assertEqual(cases["open_after_app_restart"].orchestration, "restart_dialog")
        self.assertEqual(cases["persistent_access_after_restart"].orchestration, "restart_probe")
        self.assertEqual(cases["revoked_access_behavior"].automation_level, "manual")
        self.assertEqual(cases["revoked_access_behavior"].orchestration, "revocation_probe")
        self.assertEqual(cases["timeout_when_dialog_not_closed"].orchestration, "timeout_observation")

    def test_timeout_case_maps_to_timeout_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            target = self._python_target()
            summary = Runner().run(
                RunRequest(
                    target=target,
                    output_dir=output_dir,
                    case_ids=["timeout_when_dialog_not_closed"],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                    timeout_seconds=0.2,
                )
            )

            result_path = summary.output_dir / "timeout_when_dialog_not_closed" / "result.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["result"]["status"], "timeout")
            note_codes = {note["code"] for note in payload["result"]["notes"]}
            self.assertIn("timeout_semantics", note_codes)
            self.assertIn("step_1_runner_timeout", note_codes)

    def test_persistence_case_records_explicit_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            target = self._python_target()
            summary = Runner().run(
                RunRequest(
                    target=target,
                    output_dir=output_dir,
                    case_ids=["persistent_access_after_restart"],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                )
            )

            result_path = summary.output_dir / "persistent_access_after_restart" / "result.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["result"]["status"], "pass")
            self.assertIsNone(payload["result"]["error_code"])
            note_codes = {note["code"] for note in payload["result"]["notes"]}
            self.assertIn("persistence_expectation", note_codes)
            self.assertIn("persistence_observation", note_codes)
            self.assertIsInstance(payload["result"]["returned_value_example"], dict)
            self.assertIn("initial", payload["result"]["returned_value_example"])
            self.assertIn("post_restart_probe", payload["result"]["returned_value_example"])

    def test_revocation_case_remains_honest_manual_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            target = self._python_target()
            summary = Runner().run(
                RunRequest(
                    target=target,
                    output_dir=output_dir,
                    case_ids=["revoked_access_behavior"],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                )
            )

            result_path = summary.output_dir / "revoked_access_behavior" / "result.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["case"]["automation_level"], "manual")
            self.assertEqual(payload["result"]["status"], "manual_required")
            self.assertEqual(payload["result"]["error_code"], "ACCESS_REVOKED")
            note_codes = {note["code"] for note in payload["result"]["notes"]}
            self.assertIn("manual_revocation_case", note_codes)
            self.assertIn("revocation_observation", note_codes)

    def test_restart_case_writes_step_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            target = self._python_target()
            summary = Runner().run(
                RunRequest(
                    target=target,
                    output_dir=output_dir,
                    case_ids=["open_after_app_restart"],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                )
            )

            case_dir = summary.output_dir / "open_after_app_restart"
            self.assertTrue((case_dir / "scenario.step-1.json").exists())
            self.assertTrue((case_dir / "scenario.step-2.json").exists())
            self.assertTrue((case_dir / "result.step-1.json").exists())
            self.assertTrue((case_dir / "result.step-2.json").exists())


if __name__ == "__main__":
    unittest.main()