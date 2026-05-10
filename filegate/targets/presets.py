"""Preset target definitions for bundled FileGate sample applications."""

from __future__ import annotations

from pathlib import Path

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - environment-specific fallback
    tk = None

from filegate.runner import TargetConfig
from filegate.targets.electron import build_electron_target
from filegate.targets.python_gtk import build_python_gtk_target


def build_python_tkinter_target(repo_root: Path | None = None) -> TargetConfig:
    """Build a TargetConfig for the bundled Python Tkinter sample app."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    sample_dir = root / "samples" / "python-tkinter"
    app_path = sample_dir / "app.py"
    version = str(getattr(tk, "TkVersion", "unknown")) if tk is not None else "unknown"
    return TargetConfig(
        name="python-tkinter",
        command=["python3", str(app_path)],
        sample_app="samples/python-tkinter",
        version=version,
        working_directory=root,
    )


def build_linux_portal_target(repo_root: Path | None = None) -> TargetConfig:
    """Build a TargetConfig for the bundled Linux portal sample target."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    sample_dir = root / "samples" / "linux-portal"
    app_path = sample_dir / "app.py"
    return TargetConfig(
        name="linux-portal",
        command=["python3", str(app_path)],
        sample_app="samples/linux-portal",
        version="0.1",
        working_directory=root,
    )


def list_preset_targets() -> list[dict[str, str]]:
    """Return metadata for known bundled target presets."""
    return [
        {
            "id": "python-gtk",
            "description": "Bundled Python GTK 4 sample target.",
        },
        {
            "id": "python-tkinter",
            "description": "Bundled Python Tkinter sample target.",
        },
        {
            "id": "electron",
            "description": "Bundled Electron sample target.",
        },
        {
            "id": "linux-portal",
            "description": "Bundled Linux XDG Desktop Portal sample target.",
        },
    ]


def build_preset_target(target_id: str) -> TargetConfig:
    """Resolve and build a preset target by its identifier."""
    normalized = target_id.strip().lower()
    if normalized == "python-gtk":
        return build_python_gtk_target()
    if normalized == "python-tkinter":
        return build_python_tkinter_target()
    if normalized == "electron":
        return build_electron_target()
    if normalized == "linux-portal":
        return build_linux_portal_target()
    raise KeyError(f"Unknown target preset '{target_id}'.")
