"""Tests for FG-04 filter/save-extension cases using the FG-02 extensible architecture."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from filegate.cases import DEFAULT_CASE_REGISTRY
from filegate.environment import PlatformMetadata
from filegate.runner import Runner, TargetConfig


class CaseAndRunnerTests(unittest.TestCase):
    def test_new_cases_are_listed_in_registry(self) -> None:
        expected_case_ids = {
            "filter_pdf_only",
            "filter_images_only",
            "filter_multiple_mime_types",
            "extension_auto_append_on_save",
            "wrong_extension_selected",
        }
        available = {case.case_id for case in DEFAULT_CASE_REGISTRY.all()}
        self.assertTrue(expected_case_ids.issubset(available))

    def test_runner_builds_filter_pdf_scenario(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("filter_pdf_only")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(scenario["dialog"]["type"], "open_file")
        self.assertEqual(scenario["expectation"]["selected_filter_label"], "PDF documents")
        self.assertEqual(scenario["expectation"]["allowed_extensions"], [".pdf"])
        self.assertTrue(str(scenario["simulation"]["selected_path"]).endswith("selected-document.pdf"))

    def test_runner_builds_filter_images_scenario(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("filter_images_only")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(scenario["dialog"]["type"], "open_file")
        self.assertEqual(scenario["expectation"]["selected_filter_label"], "Image files")
        self.assertEqual(scenario["expectation"]["allowed_extensions"], [".png", ".jpg", ".jpeg", ".gif"])
        self.assertTrue(str(scenario["simulation"]["selected_path"]).endswith("selected-image.png"))
        self.assertTrue(scenario["expectation"]["selection_should_match_filter"])

    def test_runner_builds_filter_multiple_mime_types_scenario(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("filter_multiple_mime_types")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(scenario["dialog"]["type"], "open_file")
        filetypes = scenario["dialog"].get("filetypes", [])
        self.assertEqual(len(filetypes), 3)
        self.assertEqual(scenario["expectation"]["selected_filter_label"], "Image files")
        self.assertTrue(str(scenario["simulation"]["selected_path"]).endswith("selected-image.jpg"))

    def test_runner_builds_save_extension_scenario(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("extension_auto_append_on_save")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(scenario["dialog"]["type"], "save_file")
        self.assertEqual(scenario["dialog"]["defaultextension"], ".txt")
        self.assertEqual(scenario["dialog"]["initialfile"], "auto-append-target")
        self.assertEqual(scenario["expectation"]["expected_extension"], ".txt")
        self.assertTrue(scenario["expectation"]["expect_auto_append"])
        self.assertTrue(str(scenario["simulation"]["selected_path"]).endswith("auto-append-target.txt"))

    def test_runner_builds_wrong_extension_scenario(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("wrong_extension_selected")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=True,
        )
        self.assertEqual(scenario["dialog"]["type"], "save_file")
        self.assertEqual(scenario["dialog"]["defaultextension"], ".txt")
        self.assertEqual(scenario["dialog"]["initialfile"], "mismatched-extension")
        self.assertEqual(scenario["expectation"]["expected_extension"], ".txt")
        self.assertEqual(scenario["expectation"]["mismatched_extension"], ".pdf")
        self.assertTrue(scenario["expectation"]["allow_mismatched_extension"])
        self.assertTrue(str(scenario["simulation"]["selected_path"]).endswith("mismatched-extension.pdf"))

    def test_filter_cases_use_file_type_filters_family(self) -> None:
        for case_id in ("filter_pdf_only", "filter_images_only", "filter_multiple_mime_types"):
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.family, "file_type_filters")

    def test_save_semantic_cases_use_save_semantics_family(self) -> None:
        for case_id in ("extension_auto_append_on_save", "wrong_extension_selected"):
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            self.assertEqual(case.family, "save_semantics")

    def test_filter_cases_use_declarative_dialog_spec(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("filter_pdf_only")
        filetypes = case.dialog.filetypes
        self.assertGreater(len(filetypes), 0)
        self.assertEqual(filetypes[0], ("PDF documents", "*.pdf"))

    def test_simulation_fixtures_are_selection_fixtures(self) -> None:
        for case_id in ("filter_pdf_only", "filter_images_only", "filter_multiple_mime_types"):
            case = DEFAULT_CASE_REGISTRY.get(case_id)
            selection_fixtures = [f for f in case.simulation.fixtures if f.is_selection_fixture]
            self.assertEqual(len(selection_fixtures), 1)

    def test_no_simulation_without_enabled_flag(self) -> None:
        case = DEFAULT_CASE_REGISTRY.get("filter_pdf_only")
        scenario = Runner()._build_scenario_payload(
            case=case,
            run_id="run-1",
            platform_metadata=_platform(),
            simulation_root=(Path(tempfile.mkdtemp()) / "simulation").resolve(),
            simulation_enabled=False,
        )
        self.assertFalse(scenario["simulation"]["enabled"])
        self.assertNotIn("selected_path", scenario["simulation"])


def _platform() -> PlatformMetadata:
    return PlatformMetadata(
        os="linux",
        distribution="Test Linux",
        version="1",
        desktop_environment="test",
        session_type="wayland",
        sandbox="none",
    )


def _target() -> TargetConfig:
    return TargetConfig(
        name="test-target",
        command=["python3", "app.py"],
        sample_app="samples/test-target",
        version="1.0",
    )


if __name__ == "__main__":
    unittest.main()
