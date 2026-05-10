"""Preset target definitions for bundled FileGate sample applications."""

from __future__ import annotations

from pathlib import Path

from filegate.runner import TargetConfig
from filegate.targets.electron import build_electron_target


def build_python_tkinter_target(repo_root: Path | None = None) -> TargetConfig:
    """Build a TargetConfig for the bundled Python Tkinter sample app."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    sample_dir = root / "samples" / "python-tkinter"
    app_path = sample_dir / "app.py"
    return TargetConfig(
        name="python-tkinter",
        command=["python3", str(app_path)],
        sample_app="samples/python-tkinter",
        version="unknown",
        working_directory=root,
    )


def list_preset_targets() -> list[dict[str, str]]:
    """Return metadata for known bundled target presets."""
    return [
        {
            "id": "python-tkinter",
            "description": "Bundled Python Tkinter sample target.",
        },
        {
            "id": "electron",
            "description": "Bundled Electron sample target.",
        },
    ]


def build_preset_target(target_id: str) -> TargetConfig:
    """Resolve and build a preset target by its identifier."""
    normalized = target_id.strip().lower()
    if normalized == "python-tkinter":
        return build_python_tkinter_target()
    if normalized == "electron":
        return build_electron_target()
    raise KeyError(f"Unknown target preset '{target_id}'.")
