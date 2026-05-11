"""Linux portal and sandbox helpers for FileGate Phase 3 work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import configparser
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import unquote, urlparse


_FILECHOOSER_VERSION_RE = re.compile(r"readonly u version = (?P<version>\d+);")


@dataclass(slots=True)
class PortalMetadata:
    """Observed XDG Desktop Portal capability metadata."""

    available: bool
    gdbus_available: bool
    dbus_session_available: bool
    service_available: bool
    filechooser_interface_available: bool
    filechooser_version: int | None
    supports_open_file: bool
    supports_save_file: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SandboxMetadata:
    """Observed sandbox and Flatpak filesystem-grant metadata."""

    sandbox: str
    flatpak_id: str | None
    flatpak_info_path: str | None
    filesystem_permissions: list[str]
    host_home_access: str
    documents_portal_mount: str | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_portal_metadata(timeout_seconds: float = 3.0) -> PortalMetadata:
    """Probe whether the XDG Desktop Portal FileChooser interface is available."""
    notes: list[str] = []
    gdbus_path = shutil.which("gdbus")
    gdbus_available = gdbus_path is not None
    dbus_session_available = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))

    if not gdbus_available:
        notes.append("`gdbus` is not available in PATH, so direct portal probing is unavailable.")
        return PortalMetadata(
            available=False,
            gdbus_available=False,
            dbus_session_available=dbus_session_available,
            service_available=False,
            filechooser_interface_available=False,
            filechooser_version=None,
            supports_open_file=False,
            supports_save_file=False,
            notes=notes,
        )

    if not dbus_session_available:
        notes.append("No D-Bus session bus address is available, so portal requests cannot be issued.")
        return PortalMetadata(
            available=False,
            gdbus_available=True,
            dbus_session_available=False,
            service_available=False,
            filechooser_interface_available=False,
            filechooser_version=None,
            supports_open_file=False,
            supports_save_file=False,
            notes=notes,
        )

    completed = subprocess.run(
        [
            gdbus_path,
            "introspect",
            "--session",
            "--dest",
            "org.freedesktop.portal.Desktop",
            "--object-path",
            "/org/freedesktop/portal/desktop",
        ],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        notes.append(
            "XDG Desktop Portal introspection failed"
            + (f": {stderr}" if stderr else ".")
        )
        return PortalMetadata(
            available=False,
            gdbus_available=True,
            dbus_session_available=True,
            service_available=False,
            filechooser_interface_available=False,
            filechooser_version=None,
            supports_open_file=False,
            supports_save_file=False,
            notes=notes,
        )

    parsed = parse_portal_introspection(completed.stdout)
    return PortalMetadata(
        available=bool(parsed["filechooser_interface_available"] and parsed["supports_open_file"] and parsed["supports_save_file"]),
        gdbus_available=True,
        dbus_session_available=True,
        service_available=True,
        filechooser_interface_available=bool(parsed["filechooser_interface_available"]),
        filechooser_version=parsed["filechooser_version"],
        supports_open_file=bool(parsed["supports_open_file"]),
        supports_save_file=bool(parsed["supports_save_file"]),
        notes=list(parsed["notes"]),
    )


def parse_portal_introspection(output: str) -> dict[str, Any]:
    """Parse relevant FileChooser details from gdbus introspection output."""
    notes: list[str] = []
    filechooser_interface_available = "interface org.freedesktop.portal.FileChooser" in output
    supports_open_file = "OpenFile(in  s parent_window" in output
    supports_save_file = "SaveFile(in  s parent_window" in output

    filechooser_version: int | None = None
    if filechooser_interface_available:
        section_start = output.index("interface org.freedesktop.portal.FileChooser")
        section = output[section_start:]
        version_match = _FILECHOOSER_VERSION_RE.search(section)
        if version_match:
            filechooser_version = int(version_match.group("version"))
        else:
            notes.append("The FileChooser interface was found, but its version could not be parsed.")
    else:
        notes.append("The FileChooser portal interface was not present in portal introspection output.")

    if filechooser_interface_available and not supports_open_file:
        notes.append("The FileChooser interface was present, but OpenFile was not advertised.")
    if filechooser_interface_available and not supports_save_file:
        notes.append("The FileChooser interface was present, but SaveFile was not advertised.")

    return {
        "filechooser_interface_available": filechooser_interface_available,
        "filechooser_version": filechooser_version,
        "supports_open_file": supports_open_file,
        "supports_save_file": supports_save_file,
        "notes": notes,
    }


def detect_sandbox_metadata(
    *,
    environ: dict[str, str] | None = None,
    flatpak_info_path: Path | None = None,
) -> SandboxMetadata:
    """Detect sandbox metadata with Flatpak-focused filesystem grant parsing."""
    effective_environ = dict(environ or os.environ)
    info_path = flatpak_info_path or Path("/.flatpak-info")
    sandbox = _detect_sandbox_kind(effective_environ, info_path)
    notes: list[str] = []
    flatpak_id = effective_environ.get("FLATPAK_ID") or None
    filesystem_permissions: list[str] = []
    host_home_access = "not_applicable"

    if sandbox == "flatpak":
        if info_path.exists():
            flatpak_payload = parse_flatpak_info(info_path)
            flatpak_id = flatpak_id or flatpak_payload.get("flatpak_id")
            filesystem_permissions = flatpak_payload.get("filesystem_permissions", [])
            host_home_access = classify_flatpak_home_access(filesystem_permissions)
            notes.extend(flatpak_payload.get("notes", []))
        else:
            host_home_access = "unknown"
            notes.append(
                "Flatpak sandbox was detected, but `/.flatpak-info` was unavailable, so host filesystem grants could not be confirmed."
            )

        if host_home_access == "none":
            notes.append(
                "No explicit host home grant was detected. App-private storage may still exist inside the sandbox, but host home access is expected to require a grant or portal selection."
            )
        elif host_home_access in {"partial", "full"}:
            notes.append(
                "One or more explicit filesystem grants were detected, so a no-home-without-grant assertion is not a clean baseline in this environment."
            )

    documents_portal_mount = detect_documents_portal_mount(effective_environ)
    if documents_portal_mount is None:
        notes.append("No documents portal mount was detected at the standard runtime location.")

    return SandboxMetadata(
        sandbox=sandbox,
        flatpak_id=flatpak_id,
        flatpak_info_path=str(info_path) if info_path.exists() else None,
        filesystem_permissions=filesystem_permissions,
        host_home_access=host_home_access,
        documents_portal_mount=documents_portal_mount,
        notes=notes,
    )


def parse_flatpak_info(flatpak_info_path: Path) -> dict[str, Any]:
    """Parse a Flatpak .flatpak-info file for filesystem grants and app identity."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(flatpak_info_path, encoding="utf-8")
    filesystems_raw = parser.get("Context", "filesystems", fallback="")
    filesystem_permissions = [value.strip() for value in filesystems_raw.split(";") if value.strip()]
    return {
        "flatpak_id": parser.get("Application", "name", fallback=None),
        "filesystem_permissions": filesystem_permissions,
        "notes": [
            (
                "Parsed filesystem grants from `/.flatpak-info` Context.filesystems. "
                "Interpretation focuses on host-home visibility rather than all Flatpak permission semantics."
            )
        ],
    }


def classify_flatpak_home_access(filesystem_permissions: list[str]) -> str:
    """Classify host home access scope from Flatpak filesystem permission entries."""
    normalized = [permission.strip() for permission in filesystem_permissions if permission.strip()]
    if not normalized:
        return "none"

    full_entries = {"home", "host"}
    if any(entry in full_entries or entry.startswith("home:") or entry.startswith("host:") for entry in normalized):
        return "full"

    if any(entry.startswith("~/") or entry.startswith("xdg-") for entry in normalized):
        return "partial"

    return "none"


def detect_documents_portal_mount(environ: dict[str, str] | None = None) -> str | None:
    """Detect the standard document portal mount when it exists."""
    effective_environ = environ or os.environ
    runtime_dir = effective_environ.get("XDG_RUNTIME_DIR")
    candidates: list[Path] = []
    if runtime_dir:
        candidates.append(Path(runtime_dir) / "doc")
    candidates.append(Path(f"/run/user/{os.getuid()}/doc"))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def file_uri_to_path(uri: str) -> str | None:
    """Convert a file:// URI returned by portals to a local filesystem path when possible."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    if parsed.netloc not in {"", "localhost"}:
        return None
    return unquote(parsed.path)


def _detect_sandbox_kind(environ: dict[str, str], flatpak_info_path: Path) -> str:
    if flatpak_info_path.exists() or environ.get("FLATPAK_ID"):
        return "flatpak"
    if any(environ.get(name) for name in ("SNAP", "SNAP_NAME", "SNAP_INSTANCE_NAME")):
        return "snap"
    if environ.get("APPIMAGE"):
        return "appimage"
    return "none"