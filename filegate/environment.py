"""Environment detection helpers for FileGate."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.metadata
import os
from pathlib import Path
import platform as py_platform
import sys
from typing import Any

import tomllib


UNKNOWN_RELIABILITY = "best_effort"
RELIABLE = "reliable"


@dataclass(slots=True)
class PlatformMetadata:
    """Platform fields aligned with the FileGate result schema."""

    os: str | None
    distribution: str | None
    version: str | None
    desktop_environment: str | None
    session_type: str | None
    sandbox: str | None


@dataclass(slots=True)
class DependencyStatus:
    """Resolved status of a required runtime dependency."""

    name: str
    requirement: str
    installed_version: str | None
    available: bool


@dataclass(slots=True)
class RuntimeMetadata:
    """Runtime metadata used by the doctor command."""

    python_version: str
    required_dependencies: list[DependencyStatus] = field(default_factory=list)


@dataclass(slots=True)
class DoctorReport:
    """Structured output for `filegate doctor`."""

    schema_version: str
    platform: PlatformMetadata
    runtime: RuntimeMetadata
    reliability: dict[str, str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a JSON-serializable dictionary."""
        return asdict(self)


def detect_environment() -> DoctorReport:
    """Detect runtime metadata for the current environment."""
    platform_metadata = detect_platform_metadata()
    runtime_metadata = detect_runtime_metadata()
    reliability = build_reliability_map(platform_metadata)
    notes = build_notes(platform_metadata, runtime_metadata)

    return DoctorReport(
        schema_version="0.1",
        platform=platform_metadata,
        runtime=runtime_metadata,
        reliability=reliability,
        notes=notes,
    )


def detect_platform_metadata() -> PlatformMetadata:
    """Detect platform metadata with Linux-first probing and explicit fallbacks."""
    system_name = py_platform.system().lower() or None

    distribution: str | None = None
    version: str | None = None

    if system_name == "linux":
        distribution, version = _detect_linux_distribution()
    else:
        # TODO: Expand distribution/version probing for Windows and macOS.
        version = py_platform.release() or None

    return PlatformMetadata(
        os=system_name,
        distribution=distribution,
        version=version,
        desktop_environment=_detect_desktop_environment(),
        session_type=_detect_session_type(),
        sandbox=_detect_sandbox(),
    )


def detect_runtime_metadata() -> RuntimeMetadata:
    """Detect Python runtime metadata and required dependency status."""
    return RuntimeMetadata(
        python_version=sys.version.split()[0],
        required_dependencies=_detect_required_dependencies(),
    )


def build_reliability_map(platform_metadata: PlatformMetadata) -> dict[str, str]:
    """Describe which reported fields are reliable versus best-effort."""
    reliability = {
        "os": RELIABLE if platform_metadata.os is not None else UNKNOWN_RELIABILITY,
        "distribution": RELIABLE if platform_metadata.distribution is not None else UNKNOWN_RELIABILITY,
        "version": RELIABLE if platform_metadata.version is not None else UNKNOWN_RELIABILITY,
        "desktop_environment": UNKNOWN_RELIABILITY,
        "session_type": UNKNOWN_RELIABILITY,
        "sandbox": RELIABLE if platform_metadata.sandbox in {"flatpak", "snap", "none"} else UNKNOWN_RELIABILITY,
        "python_version": RELIABLE,
        "required_dependencies": RELIABLE,
    }

    if platform_metadata.os != "linux":
        reliability["distribution"] = UNKNOWN_RELIABILITY

    if platform_metadata.desktop_environment is None:
        reliability["desktop_environment"] = UNKNOWN_RELIABILITY

    if platform_metadata.session_type is not None:
        reliability["session_type"] = RELIABLE

    return reliability


def build_notes(
    platform_metadata: PlatformMetadata,
    runtime_metadata: RuntimeMetadata,
) -> list[str]:
    """Build user-facing notes about reliability and fallback behavior."""
    notes: list[str] = [
        "OS, distribution, version, sandbox, and Python version are intended as primary reporting metadata.",
        "Desktop environment and session type rely on local environment variables and should be treated as best-effort unless independently verified.",
        "Missing values are reported as null so downstream reporting can distinguish unknown metadata from absent fields.",
    ]

    if platform_metadata.os != "linux":
        notes.append(
            "Non-Linux platform probing currently uses fallback detection only; Linux-first logic is isolated for future expansion."
        )

    missing_dependencies = [
        dependency.name
        for dependency in runtime_metadata.required_dependencies
        if not dependency.available
    ]
    if missing_dependencies:
        notes.append(
            "Missing required runtime dependencies detected: " + ", ".join(sorted(missing_dependencies))
        )

    return notes


def _detect_linux_distribution() -> tuple[str | None, str | None]:
    """Read Linux distribution metadata from os-release when available."""
    os_release_path = Path("/etc/os-release")
    if not os_release_path.exists():
        return None, None

    values: dict[str, str] = {}
    for line in os_release_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        values[key] = raw_value.strip().strip('"')

    distribution = values.get("NAME") or values.get("ID")
    version = values.get("VERSION_ID") or values.get("VERSION")
    return distribution, version


def _detect_desktop_environment() -> str | None:
    """Detect the active desktop environment from common session variables."""
    candidates = (
        os.environ.get("XDG_CURRENT_DESKTOP"),
        os.environ.get("DESKTOP_SESSION"),
        os.environ.get("GDMSESSION"),
    )
    for candidate in candidates:
        if not candidate:
            continue
        normalized = candidate.replace(":", "/").strip()
        if normalized:
            return normalized
    return None


def _detect_session_type() -> str | None:
    """Detect the session type, preferring XDG_SESSION_TYPE."""
    session_type = os.environ.get("XDG_SESSION_TYPE")
    if session_type:
        return session_type.strip().lower() or None

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return None


def _detect_sandbox() -> str:
    """Detect whether FileGate is running inside a known sandbox."""
    if Path("/.flatpak-info").exists() or os.environ.get("FLATPAK_ID"):
        return "flatpak"
    if any(os.environ.get(name) for name in ("SNAP", "SNAP_NAME", "SNAP_INSTANCE_NAME")):
        return "snap"
    return "none"


def _detect_required_dependencies() -> list[DependencyStatus]:
    """Resolve status for dependencies declared in pyproject.toml."""
    dependencies = _read_declared_dependencies()
    statuses: list[DependencyStatus] = []

    for dependency in dependencies:
        package_name = dependency.split(";", 1)[0].strip().split()[0]
        normalized_name = _extract_distribution_name(package_name)
        try:
            installed_version = importlib.metadata.version(normalized_name)
            available = True
        except importlib.metadata.PackageNotFoundError:
            installed_version = None
            available = False

        statuses.append(
            DependencyStatus(
                name=normalized_name,
                requirement=dependency,
                installed_version=installed_version,
                available=available,
            )
        )

    return statuses


def _read_declared_dependencies() -> list[str]:
    """Read project dependencies from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        project_config = tomllib.load(handle)
    return list(project_config.get("project", {}).get("dependencies", []))


def _extract_distribution_name(requirement: str) -> str:
    """Extract a package/distribution name from a PEP 508 requirement string."""
    separators = ("<", ">", "=", "!", "~", "[", " ")
    end_index = len(requirement)
    for separator in separators:
        separator_index = requirement.find(separator)
        if separator_index != -1:
            end_index = min(end_index, separator_index)
    return requirement[:end_index].strip()