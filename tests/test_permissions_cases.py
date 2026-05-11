"""Tests for FG-05 permissions-oriented FileGate cases.

Validates:
- Case registry entries for all 5 permission cases
- Scenario builder output (fixture paths, permissions extension fields)
- End-to-end simulation runs against the python-tkinter target
- End-to-end simulation runs against the python-gtk target
- Explicit can_read / can_write / error_code semantics in result artifacts
- That permission failures are not collapsed into generic unknown outcomes
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from filegate.cases import DEFAULT_CASE_REGISTRY
from filegate.environment import PlatformMetadata
from filegate.runner import RunRequest, Runner, TargetConfig
from filegate.targets import build_python_tkinter_target
from filegate.targets.python_gtk import build_python_gtk_target

PERMISSIONS_CASE_IDS = (
    "read_only_file",
    "write_to_read_only_file",
    "permission_denied_file",
    "permission_denied_directory",
    "execute_permission_irrelevant",
)


def _platform() -> PlatformMetadata:
    return PlatformMetadata(
        os="linux",
        distribution="Test Linux",
        version="1",
        desktop_environment="test",
        session_type="wayland",
        sandbox="none",
    )


def _is_root() -> bool:
    return os.getuid() == 0


class PermissionsRegistryTests(unittest.TestCase):
    def test_all_permissions_cases_in_registry(self) -> None:
        available = {case.case_id for case in DEFAULT_CASE_REGISTRY.all()}
        for case_id in PERMISSIONS_CASE_IDS:
            self.assertIn(case_id, available, f"Case '{case_id}' missing from registry")

    def test_all_permissions_cases_use_permissions_family(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.family, "permissions", f"Case '{case_id}' wrong family")

    def test_all_permissions_cases_are_automatic(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.automation_level, "automatic")

    def test_all_permissions_cases_use_dialog_selection_builder(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.scenario_builder_id, "dialog_selection")

    def test_read_only_file_uses_open_file_dialog(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("read_only_file").dialog.dialog_type, "open_file")

    def test_write_to_read_only_file_uses_save_file_dialog(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("write_to_read_only_file").dialog.dialog_type, "save_file")

    def test_permission_denied_directory_uses_open_folder_dialog(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("permission_denied_directory").dialog.dialog_type, "open_folder")

    def test_all_permissions_cases_have_permission_case_flag(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            perm_ext = case.extensions.get("permissions", {})
            self.assertTrue(perm_ext.get("permission_case"), f"Case '{case_id}' missing permission_case=True")

    def test_all_permissions_cases_have_semantics_field(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            perm_ext = case.extensions.get("permissions", {})
            self.assertIn("permission_case_semantics", perm_ext)

    def test_read_only_file_fixture_permissions(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("read_only_file")
        self.assertEqual(case.simulation.fixtures[0].permissions, 0o444)
        self.assertEqual(case.simulation.fixtures[0].role, "selection")

    def test_write_to_read_only_file_fixture_permissions(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("write_to_read_only_file").simulation.fixtures[0].permissions, 0o444)

    def test_permission_denied_file_fixture_permissions(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("permission_denied_file").simulation.fixtures[0].permissions, 0o000)

    def test_permission_denied_directory_fixture_kind(self) -> None:
        f = DEFAULT_CASE_REGISTRY.get("permission_denied_directory").simulation.fixtures[0]
        self.assertEqual(f.kind, "directory")
        self.assertEqual(f.permissions, 0o000)

    def test_execute_permission_irrelevant_fixture_permissions(self) -> None:
        self.assertEqual(DEFAULT_CASE_REGISTRY.get("execute_permission_irrelevant").simulation.fixtures[0].permissions, 0o111)

    def test_extension_contract_expected_fields(self) -> None:
        expected = {
            "read_only_file": ("read_only_accessible", True, False),
            "write_to_read_only_file": ("write_denied_read_only", True, False),
            "permission_denied_file": ("access_denied", False, False),
            "permission_denied_directory": ("access_denied", False, False),
            "execute_permission_irrelevant": ("execute_only_no_read", False, False),
        }
        for case_id, (semantics, exp_read, exp_write) in expected.items():
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            perm = case.extensions.get("permissions", {})
            self.assertEqual(perm.get("permission_case_semantics"), semantics, case_id)
            self.assertEqual(perm.get("expected_can_read"), exp_read, case_id)
            self.assertEqual(perm.get("expected_can_write"), exp_write, case_id)




class PermissionsScenarioBuilderTests(unittest.TestCase):
    def _build(self, case_id: str) -> dict:
        case = DEFAULT_CASE_REGISTRY.get(case_id)
        return Runner()._build_scenario_payload(
            case=case,
            run_id="run-permissions-test",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )

    def test_read_only_file_selected_path_in_permissions_subdir(self) -> None:
        scenario = self._build("read_only_file")
        self.assertIn("permissions", scenario["simulation"]["selected_path"])
        self.assertIn("read-only-file.txt", scenario["simulation"]["selected_path"])

    def test_write_to_read_only_file_dialog_type_is_save(self) -> None:
        scenario = self._build("write_to_read_only_file")
        self.assertEqual(scenario["dialog"]["type"], "save_file")
        self.assertIn("read-only-save-target.txt", scenario["simulation"]["selected_path"])

    def test_permission_denied_directory_dialog_type_is_open_folder(self) -> None:
        scenario = self._build("permission_denied_directory")
        self.assertEqual(scenario["dialog"]["type"], "open_folder")
        self.assertIn("denied-directory", scenario["simulation"]["selected_path"])

    def test_execute_permission_irrelevant_selected_path(self) -> None:
        scenario = self._build("execute_permission_irrelevant")
        self.assertIn("execute-only-file.txt", scenario["simulation"]["selected_path"])

    def test_permissions_extension_in_scenario(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            with self.subTest(case_id=case_id):
                scenario = self._build(case_id)
                perm_ext = scenario["extensions"]["permissions"]
                self.assertTrue(perm_ext.get("permission_case"))
                self.assertIn("permission_case_semantics", perm_ext)

    def test_fixture_permissions_applied_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sim_root = Path(tmp_dir) / "simulation"
            case = DEFAULT_CASE_REGISTRY.get("read_only_file")
            Runner()._build_scenario_payload(
                case=case,
                run_id="perm-test",
                platform_metadata=_platform(),
                simulation_root=sim_root,
                simulation_enabled=True,
            )
            fixture_path = sim_root / "permissions" / "read-only-file.txt"
            self.assertTrue(fixture_path.exists())
            mode = stat.S_IMODE(fixture_path.stat().st_mode)
            self.assertEqual(mode, 0o444, f"Expected 0o444, got {oct(mode)}")




class PermissionsEndToEndTkinterTests(unittest.TestCase):
    """Run permission cases against the python-tkinter target in simulation mode."""

    def _python_target(self) -> TargetConfig:
        return build_python_tkinter_target(Path(__file__).resolve().parents[1])

    def _run_case(self, case_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            summary = Runner().run(
                RunRequest(
                    target=self._python_target(),
                    output_dir=output_dir,
                    case_ids=[case_id],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                )
            )
            result_path = summary.output_dir / case_id / "result.json"
            return json.loads(result_path.read_text(encoding="utf-8"))

    def _assert_schema(self, payload: dict) -> None:
        for f in ("schema_version", "run_id", "platform", "target", "case", "result"):
            self.assertIn(f, payload)
        self.assertEqual(payload["schema_version"], "0.1")

    def test_all_permissions_cases_schema_compliant(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            with self.subTest(case_id=case_id):
                self._assert_schema(self._run_case(case_id))

    def test_read_only_file_has_permission_notes(self) -> None:
        payload = self._run_case("read_only_file")
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertIn("PERMISSION_FIXTURE_OBSERVED", note_codes)
        self.assertTrue(note_codes & {"PERMISSION_READ_ONLY_CONFIRMED", "PERMISSION_READ_ONLY_UNEXPECTED_WRITE", "PERMISSION_READ_ONLY_NO_READ"})

    def test_read_only_file_access_flags_are_booleans(self) -> None:
        result = self._run_case("read_only_file")["result"]
        self.assertIsInstance(result["can_read"], bool)
        self.assertIsInstance(result["can_write"], bool)
        self.assertNotEqual(result["status"], "inconclusive")

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_write_to_read_only_encodes_permission_denied(self) -> None:
        result = self._run_case("write_to_read_only_file")["result"]
        self.assertFalse(result["can_write"])
        self.assertEqual(result["error_code"], "PERMISSION_DENIED")
        self.assertNotEqual(result["status"], "fail")

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_permission_denied_file_access_denied_semantics(self) -> None:
        result = self._run_case("permission_denied_file")["result"]
        self.assertFalse(result["can_read"])
        self.assertFalse(result["can_write"])
        self.assertEqual(result["error_code"], "PERMISSION_DENIED")
        self.assertEqual(result["status"], "warn")

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_permission_denied_directory_access_denied_semantics(self) -> None:
        result = self._run_case("permission_denied_directory")["result"]
        self.assertFalse(result["can_read"])
        self.assertEqual(result["error_code"], "PERMISSION_DENIED")

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_execute_permission_irrelevant_no_read_no_error_code(self) -> None:
        result = self._run_case("execute_permission_irrelevant")["result"]
        self.assertFalse(result["can_read"])
        self.assertIsNone(result["error_code"])

    def test_permission_failures_not_collapsed_to_inconclusive(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            with self.subTest(case_id=case_id):
                payload = self._run_case(case_id)
                self.assertNotEqual(payload["result"]["status"], "inconclusive")

    def test_simulated_note_present(self) -> None:
        payload = self._run_case("read_only_file")
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertIn("SIMULATED", note_codes)




class PermissionsEndToEndGtkTests(unittest.TestCase):
    """Run permission cases against the python-gtk target in simulation mode."""

    def _gtk_target(self) -> TargetConfig:
        return build_python_gtk_target(Path(__file__).resolve().parents[1])

    def _run_case(self, case_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "runs"
            summary = Runner().run(
                RunRequest(
                    target=self._gtk_target(),
                    output_dir=output_dir,
                    case_ids=[case_id],
                    execution_mode="simulation",
                    platform_metadata=_platform(),
                )
            )
            result_path = summary.output_dir / case_id / "result.json"
            return json.loads(result_path.read_text(encoding="utf-8"))

    def _assert_schema(self, payload: dict) -> None:
        for f in ("schema_version", "run_id", "platform", "target", "case", "result"):
            self.assertIn(f, payload)
        self.assertEqual(payload["schema_version"], "0.1")

    def test_all_permissions_cases_schema_compliant_gtk(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            with self.subTest(case_id=case_id):
                self._assert_schema(self._run_case(case_id))

    def test_gtk_read_only_file_has_permission_note(self) -> None:
        note_codes = {n["code"] for n in self._run_case("read_only_file")["result"]["notes"]}
        self.assertIn("PERMISSION_FIXTURE_OBSERVED", note_codes)

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_gtk_write_to_read_only_encodes_permission_denied(self) -> None:
        result = self._run_case("write_to_read_only_file")["result"]
        self.assertFalse(result["can_write"])
        self.assertEqual(result["error_code"], "PERMISSION_DENIED")

    @unittest.skipIf(_is_root(), "Permission checks are bypassed when running as root")
    def test_gtk_permission_denied_file_encodes_access_denied(self) -> None:
        result = self._run_case("permission_denied_file")["result"]
        self.assertFalse(result["can_read"])
        self.assertFalse(result["can_write"])
        self.assertEqual(result["error_code"], "PERMISSION_DENIED")
        self.assertEqual(result["status"], "warn")

    def test_gtk_permission_failures_not_generic_unknown(self) -> None:
        for case_id in PERMISSIONS_CASE_IDS:
            with self.subTest(case_id=case_id):
                self.assertNotEqual(self._run_case(case_id)["result"]["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main()

