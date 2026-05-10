from __future__ import annotations

import unittest
from pathlib import Path

from filegate.bootstrap import prepare_target
from filegate.targets import build_preset_target, list_preset_targets


REPO_ROOT = Path(__file__).resolve().parent.parent


class TargetPresetAndBootstrapTests(unittest.TestCase):
    def test_python_gtk_preset_is_listed(self) -> None:
        target_ids = {entry["id"] for entry in list_preset_targets()}
        self.assertIn("python-gtk", target_ids)

    def test_build_python_gtk_preset(self) -> None:
        target = build_preset_target("python-gtk")
        self.assertEqual(target.name, "python-gtk")
        self.assertEqual(target.sample_app, "samples/python-gtk")
        self.assertEqual(target.command[0], "python3")
        self.assertTrue(target.command[1].endswith("samples/python-gtk/app.py"))

    def test_prepare_python_gtk_target(self) -> None:
        result = prepare_target("python-gtk", repo_root=REPO_ROOT)
        self.assertEqual(result.target_id, "python-gtk")
        self.assertEqual(result.status, "ready")
        self.assertTrue(any("GTK import check passed" in detail for detail in result.details))


if __name__ == "__main__":
    unittest.main()