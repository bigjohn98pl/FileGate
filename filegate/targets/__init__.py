"""Target adapters for known FileGate sample applications."""

from filegate.targets.electron import build_electron_target
from filegate.targets.presets import (
    build_preset_target,
    build_python_tkinter_target,
    list_preset_targets,
)

__all__ = [
    "build_electron_target",
    "build_python_tkinter_target",
    "build_preset_target",
    "list_preset_targets",
]