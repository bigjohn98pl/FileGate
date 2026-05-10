"""Bootstrap and readiness checks for bundled sample targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(slots=True)
class PreparationResult:
    target_id: str
    status: str
    details: list[str]


def prepare_target(target_id: str, repo_root: Path | None = None) -> PreparationResult:
    normalized = target_id.strip().lower()
    root = (repo_root or Path(__file__).resolve().parent.parent).resolve()

    if normalized == "electron":
        return _prepare_electron(root)
    if normalized == "python-gtk":
        return _prepare_python_gtk(root)
    if normalized == "python-tkinter":
        return _prepare_python_tkinter(root)

    raise KeyError(f"Unknown target preset '{target_id}'.")


def prepare_all_targets(repo_root: Path | None = None) -> list[PreparationResult]:
    return [
        prepare_target("python-gtk", repo_root=repo_root),
        prepare_target("python-tkinter", repo_root=repo_root),
        prepare_target("electron", repo_root=repo_root),
    ]


def _prepare_python_tkinter(root: Path) -> PreparationResult:
    details: list[str] = []
    command = ["python3", "-c", "import tkinter; print('tkinter-ok')"]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if completed.returncode == 0:
        details.append("Tkinter import check passed.")
        return PreparationResult("python-tkinter", "ready", details)

    details.append("Tkinter import check failed.")
    if completed.stderr.strip():
        details.append(completed.stderr.strip())
    return PreparationResult("python-tkinter", "failed", details)


def _prepare_python_gtk(root: Path) -> PreparationResult:
    details: list[str] = []
    command = [
        "python3",
        "-c",
        (
            "import gi; "
            "gi.require_version('Gtk', '4.0'); "
            "from gi.repository import Gtk; "
            "print(f'gtk4-ok:{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}')"
        ),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if completed.returncode == 0:
        version_output = completed.stdout.strip() or "gtk4-ok"
        details.append(f"GTK import check passed ({version_output}).")
        return PreparationResult("python-gtk", "ready", details)

    details.append("GTK import check failed.")
    if completed.stderr.strip():
        details.append(completed.stderr.strip())
    return PreparationResult("python-gtk", "failed", details)


def _prepare_electron(root: Path) -> PreparationResult:
    details: list[str] = []
    sample_dir = root / "samples" / "electron"

    if shutil.which("npm") is None:
        return PreparationResult("electron", "failed", ["npm not found in PATH."])

    install = subprocess.run(["npm", "install"], cwd=sample_dir, capture_output=True, text=True)
    if install.returncode != 0:
        details.append("npm install failed.")
        if install.stderr.strip():
            details.append(install.stderr.strip())
        return PreparationResult("electron", "failed", details)

    details.append("npm install completed.")
    version_check = subprocess.run(
        ["npm", "exec", "--", "electron", "--version"],
        cwd=sample_dir,
        capture_output=True,
        text=True,
    )
    if version_check.returncode == 0:
        details.append(f"Electron ready: {version_check.stdout.strip()}")
        return PreparationResult("electron", "ready", details)

    details.append("Electron health-check failed.")
    if version_check.stderr.strip():
        details.append(version_check.stderr.strip())
    return PreparationResult("electron", "failed", details)
