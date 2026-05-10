from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from filegate.linux_portal import (
    classify_flatpak_home_access,
    detect_sandbox_metadata,
    file_uri_to_path,
    parse_flatpak_info,
    parse_portal_introspection,
)


PORTAL_INTROSPECTION_FIXTURE = """
node /org/freedesktop/portal/desktop {
  interface org.freedesktop.portal.FileChooser {
    methods:
      OpenFile(in  s parent_window,
               in  s title,
               in  a{sv} options,
               out o handle);
      SaveFile(in  s parent_window,
               in  s title,
               in  a{sv} options,
               out o handle);
    properties:
      readonly u version = 4;
  };
};
"""


class LinuxPortalTests(unittest.TestCase):
    def test_parse_portal_introspection_extracts_capabilities(self) -> None:
        parsed = parse_portal_introspection(PORTAL_INTROSPECTION_FIXTURE)

        self.assertTrue(parsed["filechooser_interface_available"])
        self.assertEqual(parsed["filechooser_version"], 4)
        self.assertTrue(parsed["supports_open_file"])
        self.assertTrue(parsed["supports_save_file"])
        self.assertEqual(parsed["notes"], [])

    def test_file_uri_to_path_converts_local_file_uri(self) -> None:
        self.assertEqual(file_uri_to_path("file:///tmp/Example%20File.txt"), "/tmp/Example File.txt")
        self.assertIsNone(file_uri_to_path("document://portal/1"))

    def test_classify_flatpak_home_access(self) -> None:
        self.assertEqual(classify_flatpak_home_access([]), "none")
        self.assertEqual(classify_flatpak_home_access(["home"]), "full")
        self.assertEqual(classify_flatpak_home_access(["xdg-documents", "xdg-download"]), "partial")
        self.assertEqual(classify_flatpak_home_access(["/tmp"]), "none")

    def test_parse_flatpak_info_extracts_filesystem_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            info_path = Path(tmp_dir) / ".flatpak-info"
            info_path.write_text(
                "[Application]\nname=org.example.App\n\n[Context]\nfilesystems=xdg-documents;home;\n",
                encoding="utf-8",
            )

            parsed = parse_flatpak_info(info_path)

        self.assertEqual(parsed["flatpak_id"], "org.example.App")
        self.assertEqual(parsed["filesystem_permissions"], ["xdg-documents", "home"])

    def test_detect_sandbox_metadata_for_flatpak_without_home_grant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_doc = Path(tmp_dir) / "doc"
            runtime_doc.mkdir()
            info_path = Path(tmp_dir) / ".flatpak-info"
            info_path.write_text(
                "[Application]\nname=org.example.App\n\n[Context]\nfilesystems=xdg-documents;\n",
                encoding="utf-8",
            )

            metadata = detect_sandbox_metadata(
                environ={
                    "FLATPAK_ID": "org.example.App",
                    "XDG_RUNTIME_DIR": tmp_dir,
                },
                flatpak_info_path=info_path,
            )

        self.assertEqual(metadata.sandbox, "flatpak")
        self.assertEqual(metadata.host_home_access, "partial")
        self.assertEqual(metadata.documents_portal_mount, str(runtime_doc))
        self.assertIn("explicit filesystem grants", " ".join(metadata.notes).lower())


if __name__ == "__main__":
    unittest.main()