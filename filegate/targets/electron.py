"""Electron target adapter helpers."""

from __future__ import annotations

import json
from pathlib import Path

from filegate.runner import TargetConfig

ELECTRON_SAMPLE_APP = "samples/electron"


def build_electron_target(repo_root: Path | None = None) -> TargetConfig:
    """Build a TargetConfig for the bundled Electron sample app."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    sample_dir = root / "samples" / "electron"
    package_json_path = sample_dir / "package.json"

    version = "unknown"
    if package_json_path.exists():
        payload = json.loads(package_json_path.read_text(encoding="utf-8"))
        version = str(payload.get("devDependencies", {}).get("electron") or payload.get("version") or "unknown")

    return TargetConfig(
        name="electron",
        command=["npm", "start", "--"],
        sample_app=ELECTRON_SAMPLE_APP,
        version=version,
        working_directory=sample_dir,
    )