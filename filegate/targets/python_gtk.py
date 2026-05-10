"""Python GTK target adapter helpers."""

from __future__ import annotations

from pathlib import Path
import subprocess

from filegate.runner import TargetConfig

PYTHON_GTK_SAMPLE_APP = "samples/python-gtk"


def build_python_gtk_target(repo_root: Path | None = None) -> TargetConfig:
    """Build a TargetConfig for the bundled Python GTK sample app."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    sample_dir = root / "samples" / "python-gtk"
    app_path = sample_dir / "app.py"
    version = _detect_python_gtk_version(root)
    return TargetConfig(
        name="python-gtk",
        command=["python3", str(app_path)],
        sample_app=PYTHON_GTK_SAMPLE_APP,
        version=version,
        working_directory=root,
    )


def _detect_python_gtk_version(root: Path) -> str:
    command = [
        "python3",
        "-c",
        (
            "import gi; "
            "gi.require_version('Gtk', '4.0'); "
            "from gi.repository import Gtk; "
            "print(f'{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}')"
        ),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"