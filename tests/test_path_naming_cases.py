"""Tests for FG-03 dialog-basics (save_file_overwrite) and path/naming cases.

Validates case registry entries, runner scenario building, and end-to-end
simulation execution against the python-tkinter target.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from filegate.cases import DEFAULT_CASE_REGISTRY
from filegate.environment import PlatformMetadata
from filegate.runner import RunRequest, Runner, TargetConfig
from filegate.targets import build_python_tkinter_target

PATH_NAMING_CASE_IDS = (
    "path_with_spaces",
    "unicode_filename",
    "polish_characters_filename",
    "very_long_filename",
    "nested_directory_path",
    "relative_vs_absolute_path",
    "case_sensitive_collision",
)

ALL_NEW_CASE_IDS = ("save_file_overwrite",) + PATH_NAMING_CASE_IDS


def _platform() -> PlatformMetadata:
    return PlatformMetadata(
        os="linux",
        distribution="Test Linux",
        version="1",
        desktop_environment="test",
        session_type="wayland",
        sandbox="none",
    )


class PathNamingRegistryTests(unittest.TestCase):
    def test_all_new_cases_in_registry(self) -> None:
        available = {case.case_id for case in DEFAULT_CASE_REGISTRY.all()}
        for case_id in ALL_NEW_CASE_IDS:
            self.assertIn(case_id, available, f"Case '{case_id}' missing from registry")

    def test_save_file_overwrite_uses_dialog_basics_family(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("save_file_overwrite")
        self.assertEqual(case.family, "dialog_basics")
        self.assertEqual(case.dialog.dialog_type, "save_file")
        self.assertEqual(case.automation_level, "semi_automatic")

    def test_path_naming_cases_use_path_naming_family(self) -> None:
        for case_id in PATH_NAMING_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.family, "path_naming", f"Case '{case_id}' wrong family")

    def test_path_naming_cases_use_open_file_dialog(self) -> None:
        for case_id in PATH_NAMING_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.dialog.dialog_type, "open_file", f"Case '{case_id}' wrong dialog type")

    def test_save_file_overwrite_fixture_is_materialized(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("save_file_overwrite")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        self.assertTrue(selection_fixtures[0].materialize)

    def test_path_with_spaces_fixture_contains_spaces(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("path_with_spaces")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        self.assertIn(" ", selection_fixtures[0].relative_path)

    def test_unicode_filename_fixture_has_unicode_chars(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("unicode_filename")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        self.assertTrue(any(ord(c) > 127 for c in selection_fixtures[0].relative_path))

    def test_polish_characters_fixture_has_diacritics(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("polish_characters_filename")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        fixture_path = selection_fixtures[0].relative_path
        self.assertTrue(any(c in fixture_path for c in "ąćęłńóśźż"))

    def test_very_long_filename_fixture_length(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("very_long_filename")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        filename = Path(selection_fixtures[0].relative_path).name
        self.assertGreaterEqual(len(filename), 200)

    def test_nested_directory_path_has_four_levels(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("nested_directory_path")
        selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
        self.assertEqual(len(selection_fixtures), 1)
        parts = Path(selection_fixtures[0].relative_path).parts
        self.assertGreaterEqual(len(parts), 5)

    def test_case_sensitive_collision_has_two_fixtures(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("case_sensitive_collision")
        self.assertEqual(len(case.simulation.fixtures), 2)
        roles = {f.role for f in case.simulation.fixtures}
        self.assertIn("selection", roles)
        self.assertIn("supporting", roles)

    def test_relative_vs_absolute_expects_absolute(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("relative_vs_absolute_path")
        ext = case.extensions.get("path", {})
        self.assertTrue(ext.get("expect_absolute"))

    def test_path_naming_cases_use_dialog_selection_builder(self) -> None:
        for case_id in ALL_NEW_CASE_IDS:
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.scenario_builder_id, "dialog_selection", f"Case '{case_id}' unexpected builder")


class PathNamingScenarioBuilderTests(unittest.TestCase):
    def _build(self, case_id: str) -> dict:
        case = DEFAULT_CASE_REGISTRY.get(case_id)
        return Runner()._build_scenario_payload(
            case=case,
            run_id="run-test",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )

    def test_path_with_spaces_selected_path_contains_spaces(self) -> None:
        scenario = self._build("path_with_spaces")
        self.assertIn(" ", scenario["simulation"]["selected_path"])

    def test_unicode_filename_selected_path_unicode(self) -> None:
        scenario = self._build("unicode_filename")
        self.assertTrue(any(ord(c) > 127 for c in scenario["simulation"]["selected_path"]))

    def test_polish_characters_selected_path_has_diacritics(self) -> None:
        scenario = self._build("polish_characters_filename")
        selected = scenario["simulation"]["selected_path"]
        self.assertTrue(any(c in selected for c in "ąćęłńóśźż"))

    def test_very_long_filename_selected_path_long(self) -> None:
        scenario = self._build("very_long_filename")
        self.assertGreaterEqual(len(Path(scenario["simulation"]["selected_path"]).name), 200)

    def test_nested_directory_selected_path_deep(self) -> None:
        scenario = self._build("nested_directory_path")
        self.assertIn("level4", scenario["simulation"]["selected_path"])

    def test_relative_vs_absolute_extensions(self) -> None:
        scenario = self._build("relative_vs_absolute_path")
        self.assertTrue(scenario["extensions"]["path"].get("expect_absolute"))

    def test_save_file_overwrite_dialog_type_and_path(self) -> None:
        scenario = self._build("save_file_overwrite")
        self.assertEqual(scenario["dialog"]["type"], "save_file")
        self.assertIn("selected_path", scenario["simulation"])

    def test_case_sensitive_collision_two_fixture_items(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("case_sensitive_collision")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-test",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(len(scenario["fixtures"]["items"]), 2)



class PathNamingEndToEndTests(unittest.TestCase):
    """Run new cases through the python-tkinter target in simulation mode."""

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
        for field in ("schema_version", "run_id", "platform", "target", "case", "result"):
            self.assertIn(field, payload)
        self.assertIn("id", payload["case"])
        self.assertIn("automation_level", payload["case"])
        self.assertIn("status", payload["result"])
        self.assertIn("duration_ms", payload["result"])
        self.assertIn("returned_resource_type", payload["result"])
        self.assertEqual(payload["schema_version"], "0.1")

    def test_save_file_overwrite_schema_pass(self) -> None:
        payload = self._run_case("save_file_overwrite")
        self._assert_schema(payload)
        self.assertIn(payload["result"]["status"], {"pass", "warn"})
        self.assertIn("SIMULATED", {n["code"] for n in payload["result"]["notes"]})

    def test_path_with_spaces_note(self) -> None:
        payload = self._run_case("path_with_spaces")
        self._assert_schema(payload)
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertTrue(note_codes & {"SPACES_PRESERVED", "SPACES_NOT_OBSERVED"})

    def test_unicode_filename_note(self) -> None:
        payload = self._run_case("unicode_filename")
        self._assert_schema(payload)
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertTrue(note_codes & {"UNICODE_PRESERVED", "UNICODE_CORRUPTION"})

    def test_polish_characters_note(self) -> None:
        payload = self._run_case("polish_characters_filename")
        self._assert_schema(payload)
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertTrue(note_codes & {"UNICODE_PRESERVED", "UNICODE_CORRUPTION"})

    def test_very_long_filename_note(self) -> None:
        payload = self._run_case("very_long_filename")
        self._assert_schema(payload)
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertTrue(note_codes & {"LONG_FILENAME_PRESERVED", "LONG_FILENAME_TRUNCATED"})

    def test_nested_directory_note(self) -> None:
        payload = self._run_case("nested_directory_path")
        self._assert_schema(payload)
        self.assertIn("NESTING_DEPTH_OBSERVED", {n["code"] for n in payload["result"]["notes"]})

    def test_relative_vs_absolute_note(self) -> None:
        payload = self._run_case("relative_vs_absolute_path")
        self._assert_schema(payload)
        note_codes = {n["code"] for n in payload["result"]["notes"]}
        self.assertTrue(note_codes & {"PATH_IS_ABSOLUTE", "PATH_NOT_ABSOLUTE"})

    def test_case_sensitive_collision_note(self) -> None:
        payload = self._run_case("case_sensitive_collision")
        self._assert_schema(payload)
        self.assertIn("CASE_COLLISION_SELECTION", {n["code"] for n in payload["result"]["notes"]})

    def test_all_new_cases_schema_compliant(self) -> None:
        for case_id in ALL_NEW_CASE_IDS:
            with self.subTest(case_id=case_id):
                self._assert_schema(self._run_case(case_id))


if __name__ == "__main__":
    unittest.main()
