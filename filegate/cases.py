"""Case registry and scenario metadata for FileGate execution.

The runner consumes the data structures in this module to build target
scenarios without hardcoding behavior for individual case IDs.

Extension strategy
------------------
New case families should prefer extending the declarative metadata below:

- ``DialogSpec`` for target-facing dialog configuration,
- ``ExpectationSpec`` for result-policy expectations,
- ``SimulationFixtureSpec`` + ``SimulationSpec`` for reusable fixture layout,
- ``CaseDefinition.extensions`` for namespaced family-specific contracts such as
  ``path``, ``filters``, ``permissions``, and ``persistence``.

When a family cannot be expressed with the default dialog-selection scenario
builder, assign a new ``scenario_builder_id`` and register the implementation in
:mod:`filegate.runner`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

AUTOMATION_LEVELS = {"automatic", "semi_automatic", "manual"}
FIXTURE_KINDS = {"file", "directory", "symlink"}


@dataclass(frozen=True, slots=True)
class DialogSpec:
    """Stable target-facing dialog contract."""

    dialog_type: str
    title: str | None = None
    initialdir: str | None = None
    initialfile: str | None = None
    defaultextension: str | None = None
    filetypes: tuple[tuple[str, str], ...] = ()
    mustexist: bool | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dialog_type.strip():
            raise ValueError("dialog_type must be a non-empty string.")

    def to_payload(self, *, fallback_title: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.dialog_type,
            "title": self.title or fallback_title,
        }
        if self.initialdir:
            payload["initialdir"] = self.initialdir
        if self.initialfile:
            payload["initialfile"] = self.initialfile
        if self.defaultextension:
            payload["defaultextension"] = self.defaultextension
        if self.filetypes:
            payload["filetypes"] = [list(item) for item in self.filetypes]
        if self.mustexist is not None:
            payload["mustexist"] = self.mustexist
        payload.update(dict(self.options))
        return payload


@dataclass(frozen=True, slots=True)
class ExpectationSpec:
    """Case expectation contract emitted to targets."""

    cancel_is_expected: bool = False
    expected_selection_count: int | None = None
    min_selection_count: int | None = None
    max_selection_count: int | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "cancel_is_expected": self.cancel_is_expected,
        }
        if self.expected_selection_count is not None:
            payload["expected_selection_count"] = self.expected_selection_count
        if self.min_selection_count is not None:
            payload["min_selection_count"] = self.min_selection_count
        if self.max_selection_count is not None:
            payload["max_selection_count"] = self.max_selection_count
        payload.update(dict(self.options))
        return payload


@dataclass(frozen=True, slots=True)
class SimulationFixtureSpec:
    """Reusable fixture specification for scenario preparation."""

    fixture_id: str
    relative_path: str
    kind: str = "file"
    role: str = "supporting"
    materialize: bool = True
    content: str | None = None
    permissions: int | None = None
    symlink_target: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id must be a non-empty string.")
        if not self.relative_path.strip():
            raise ValueError("relative_path must be a non-empty string.")
        if self.kind not in FIXTURE_KINDS:
            raise ValueError(
                f"Unsupported fixture kind '{self.kind}'. Expected one of: {sorted(FIXTURE_KINDS)}"
            )

    @property
    def is_selection_fixture(self) -> bool:
        return self.role == "selection"

    def to_contract_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.fixture_id,
            "relative_path": self.relative_path,
            "kind": self.kind,
            "role": self.role,
            "materialize": self.materialize,
        }
        if self.permissions is not None:
            payload["permissions"] = oct(self.permissions)
        if self.symlink_target is not None:
            payload["symlink_target"] = self.symlink_target
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class SimulationSpec:
    """Simulation behavior and reusable fixture layout for a case."""

    fixtures: tuple[SimulationFixtureSpec, ...] = ()
    cancel: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)

    def to_contract_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "cancel": self.cancel,
            "fixtures": [fixture.to_contract_payload() for fixture in self.fixtures],
        }
        payload.update(dict(self.options))
        return payload


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    """Canonical FileGate case metadata used by the runner."""

    case_id: str
    name: str
    automation_level: str
    objective: str
    preconditions: tuple[str, ...]
    steps: tuple[str, ...]
    expected_result: str
    artifacts: tuple[str, ...]
    dialog: DialogSpec
    expectation: ExpectationSpec = ExpectationSpec()
    simulation: SimulationSpec = SimulationSpec()
    family: str = "dialog_basics"
    tags: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)
    scenario_builder_id: str = "dialog_selection"
    default_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.automation_level not in AUTOMATION_LEVELS:
            raise ValueError(
                f"Unsupported automation level for {self.case_id}: {self.automation_level}"
            )
        if not self.scenario_builder_id.strip():
            raise ValueError("scenario_builder_id must be a non-empty string.")

    def to_case_payload(self) -> dict[str, str]:
        return {
            "id": self.case_id,
            "name": self.name,
            "automation_level": self.automation_level,
        }

    def to_catalog_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family": self.family,
            "name": self.name,
            "automation_level": self.automation_level,
            "objective": self.objective,
            "preconditions": list(self.preconditions),
            "steps": list(self.steps),
            "expected_result": self.expected_result,
            "artifacts": list(self.artifacts),
            "tags": list(self.tags),
            "scenario_builder_id": self.scenario_builder_id,
        }

    @property
    def dialog_type(self) -> str:
        return self.dialog.dialog_type

    @property
    def cancel_is_expected(self) -> bool:
        return self.expectation.cancel_is_expected


DEFAULT_ARTIFACTS = ("scenario_json", "result_json", "stdout_log", "stderr_log")


def _extension_contract(
    *,
    path: Mapping[str, Any] | None = None,
    filters: Mapping[str, Any] | None = None,
    permissions: Mapping[str, Any] | None = None,
    persistence: Mapping[str, Any] | None = None,
    **extra_sections: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": dict(path or {}),
        "filters": dict(filters or {}),
        "permissions": dict(permissions or {}),
        "persistence": dict(persistence or {}),
    }
    for section_name, section_payload in extra_sections.items():
        payload[section_name] = dict(section_payload)
    return payload


MVP_CASES: tuple[CaseDefinition, ...] = (
    CaseDefinition(
        case_id="open_file_single",
        name="Open file single",
        automation_level="semi_automatic",
        objective="Verify that a target returns a single selected file resource.",
        preconditions=("Target executable is available.",),
        steps=("Run the open file scenario.", "Collect the returned resource."),
        expected_result="Exactly one selected file resource is returned.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_file",
                    relative_path="single.txt",
                    role="selection",
                    content="FileGate single selection fixture\n",
                ),
            ),
        ),
        tags=("dialog_basics", "open", "single_selection"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
            },
        ),
    ),
    CaseDefinition(
        case_id="open_file_multiple",
        name="Open file multiple",
        automation_level="semi_automatic",
        objective="Verify that a target returns multiple selected file resources.",
        preconditions=("Target executable is available.",),
        steps=("Run the open multiple files scenario.", "Collect returned resources."),
        expected_result="At least two selected file resources are returned.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_files"),
        expectation=ExpectationSpec(min_selection_count=2),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_file_a",
                    relative_path="multi-a.txt",
                    role="selection",
                    content="A\n",
                ),
                SimulationFixtureSpec(
                    fixture_id="selected_file_b",
                    relative_path="multi-b.txt",
                    role="selection",
                    content="B\n",
                ),
            ),
        ),
        tags=("dialog_basics", "open", "multi_selection"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "multiple",
            },
        ),
    ),
    CaseDefinition(
        case_id="open_folder",
        name="Open folder",
        automation_level="semi_automatic",
        objective="Verify that a target returns a selected directory resource.",
        preconditions=("Target executable is available.",),
        steps=("Run the open folder scenario.", "Collect the returned resource."),
        expected_result="A selected folder resource is returned.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_folder"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_folder",
                    relative_path="selected-folder",
                    kind="directory",
                    role="selection",
                ),
            ),
        ),
        tags=("dialog_basics", "open", "directory_selection"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "directory",
                "selection_mode": "single",
            },
        ),
    ),
    CaseDefinition(
        case_id="save_file_new",
        name="Save file new",
        automation_level="semi_automatic",
        objective="Verify that a target returns a writable save destination.",
        preconditions=("Target executable is available.",),
        steps=("Run the save file scenario.", "Collect the returned save location."),
        expected_result="A writable save destination is returned.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="save_file"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="save_destination",
                    relative_path="saved-output.txt",
                    role="selection",
                    materialize=False,
                ),
            ),
        ),
        tags=("dialog_basics", "save", "new_destination"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
            },
            permissions={
                "requires_write_access": True,
            },
            persistence={
                "expectation": "not_evaluated",
            },
        ),
    ),
    CaseDefinition(
        case_id="filter_pdf_only",
        name="Filter PDF only",
        automation_level="semi_automatic",
        objective="Verify that open dialogs can be configured with a PDF-only file filter and report the observed selection behavior.",
        preconditions=("Target executable is available.",),
        steps=("Run the PDF-only open file scenario.", "Collect the returned resource and filter observations."),
        expected_result="A selected file is returned with structured notes describing the configured PDF filter and any observed framework differences.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(
            dialog_type="open_file",
            filetypes=(
                ("PDF documents", "*.pdf"),
                ("All files", "*.*"),
            ),
        ),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={
                "selected_filter_label": "PDF documents",
                "allowed_extensions": [".pdf"],
                "selection_should_match_filter": True,
            },
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_document",
                    relative_path="selected-document.pdf",
                    role="selection",
                    content="%PDF-1.4\n% FileGate PDF filter fixture\n",
                ),
            ),
            options={"selected_filter_label": "PDF documents"},
        ),
        family="file_type_filters",
        tags=("file_type_filters", "open", "pdf", "filter"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            filters={"configured_filter": "pdf_only", "expected_extension": ".pdf"},
        ),
    ),
    CaseDefinition(
        case_id="filter_images_only",
        name="Filter images only",
        automation_level="semi_automatic",
        objective="Verify that open dialogs can be configured with an image-only file filter and report the observed selection behavior.",
        preconditions=("Target executable is available.",),
        steps=("Run the image-only open file scenario.", "Collect the returned resource and filter observations."),
        expected_result="A selected file is returned with structured notes describing the configured image filter and any observed framework differences.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(
            dialog_type="open_file",
            filetypes=(
                ("Image files", "*.png;*.jpg;*.jpeg;*.gif"),
                ("All files", "*.*"),
            ),
        ),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={
                "selected_filter_label": "Image files",
                "allowed_extensions": [".png", ".jpg", ".jpeg", ".gif"],
                "selection_should_match_filter": True,
            },
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_image",
                    relative_path="selected-image.png",
                    role="selection",
                    content="PNG\r\nFileGate image filter fixture\n",
                ),
            ),
            options={"selected_filter_label": "Image files"},
        ),
        family="file_type_filters",
        tags=("file_type_filters", "open", "image", "filter"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            filters={"configured_filter": "images_only", "allowed_extensions": [".png", ".jpg", ".jpeg", ".gif"]},
        ),
    ),
    CaseDefinition(
        case_id="filter_multiple_mime_types",
        name="Filter multiple MIME types",
        automation_level="semi_automatic",
        objective="Verify that open dialogs can be configured with multiple file-type filters and report which configured filter intent was exercised.",
        preconditions=("Target executable is available.",),
        steps=("Run the multi-filter open file scenario.", "Collect the returned resource and filter observations."),
        expected_result="A selected file is returned with structured notes describing the configured multi-filter set and any observed framework differences.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(
            dialog_type="open_file",
            filetypes=(
                ("PDF documents", "*.pdf"),
                ("Image files", "*.png;*.jpg;*.jpeg"),
                ("Text files", "*.txt;*.md"),
            ),
        ),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={
                "selected_filter_label": "Image files",
                "allowed_extensions": [".png", ".jpg", ".jpeg"],
                "selection_should_match_filter": True,
            },
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_image",
                    relative_path="selected-image.jpg",
                    role="selection",
                    content="JPEG FileGate multi-filter fixture\n",
                ),
            ),
            options={"selected_filter_label": "Image files"},
        ),
        family="file_type_filters",
        tags=("file_type_filters", "open", "multi_filter"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            filters={"configured_filter": "multiple_mime_types", "exercised_filter": "image_files"},
        ),
    ),
    CaseDefinition(
        case_id="extension_auto_append_on_save",
        name="Extension auto append on save",
        automation_level="semi_automatic",
        objective="Verify whether a save dialog appends the configured default extension when the user omits it.",
        preconditions=("Target executable is available.",),
        steps=("Run the save scenario with a configured default extension.", "Collect the returned save path and extension observations."),
        expected_result="The returned save path and result notes make the observed auto-append behavior explicit.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(
            dialog_type="save_file",
            initialfile="auto-append-target",
            defaultextension=".txt",
            filetypes=(
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ),
        ),
        expectation=ExpectationSpec(
            options={
                "selected_filter_label": "Text files",
                "expected_extension": ".txt",
                "expect_auto_append": True,
            },
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="save_destination",
                    relative_path="auto-append-target.txt",
                    role="selection",
                    materialize=False,
                ),
            ),
            options={"selected_filter_label": "Text files"},
        ),
        family="save_semantics",
        tags=("save_semantics", "save", "extension", "auto_append"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            filters={"configured_filter": "text_files", "default_extension": ".txt"},
            persistence={"expectation": "not_evaluated"},
        ),
    ),
    CaseDefinition(
        case_id="wrong_extension_selected",
        name="Wrong extension selected",
        automation_level="semi_automatic",
        objective="Verify how a save dialog behaves when the chosen filename extension differs from the selected filter/default extension.",
        preconditions=("Target executable is available.",),
        steps=("Run the save scenario with an intentionally mismatched extension.", "Collect the returned save path and mismatch observations."),
        expected_result="The returned save path and result notes explicitly document whether the target preserved, replaced, or supplemented the mismatched extension.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(
            dialog_type="save_file",
            initialfile="mismatched-extension",
            defaultextension=".txt",
            filetypes=(
                ("Text files", "*.txt"),
                ("PDF documents", "*.pdf"),
            ),
        ),
        expectation=ExpectationSpec(
            options={
                "selected_filter_label": "Text files",
                "expected_extension": ".txt",
                "mismatched_extension": ".pdf",
                "allow_mismatched_extension": True,
            },
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="save_destination",
                    relative_path="mismatched-extension.pdf",
                    role="selection",
                    materialize=False,
                ),
            ),
            options={"selected_filter_label": "Text files"},
        ),
        family="save_semantics",
        tags=("save_semantics", "save", "extension", "mismatch"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            filters={"configured_filter": "text_files", "mismatched_extension": ".pdf"},
            persistence={"expectation": "not_evaluated"},
        ),
    ),
    CaseDefinition(
        case_id="cancel_open_dialog",
        name="Cancel open dialog",
        automation_level="semi_automatic",
        objective="Verify that expected dialog cancellation is encoded semantically.",
        preconditions=("Target executable is available.",),
        steps=("Run the open dialog cancellation scenario.", "Collect cancel result."),
        expected_result="Cancellation is reported as pass with USER_CANCELLED semantics.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(cancel_is_expected=True),
        simulation=SimulationSpec(cancel=True),
        tags=("dialog_basics", "open", "cancel"),
        extensions=_extension_contract(
            path={
                "selection_mode": "single",
            },
        ),
    ),
    CaseDefinition(
        case_id="cancel_save_dialog",
        name="Cancel save dialog",
        automation_level="semi_automatic",
        objective="Verify that expected save cancellation is encoded semantically.",
        preconditions=("Target executable is available.",),
        steps=("Run the save dialog cancellation scenario.", "Collect cancel result."),
        expected_result="Cancellation is reported as pass with USER_CANCELLED semantics.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="save_file"),
        expectation=ExpectationSpec(cancel_is_expected=True),
        simulation=SimulationSpec(cancel=True),
        tags=("dialog_basics", "save", "cancel"),
        extensions=_extension_contract(
            path={
                "selection_mode": "single",
            },
            permissions={
                "requires_write_access": True,
            },
        ),
    ),
)


class CaseRegistry:
    """Lookup and selection helper for FileGate case definitions."""

    def __init__(self, cases: Iterable[CaseDefinition] = MVP_CASES) -> None:
        self._cases = {case.case_id: case for case in cases}

    def all(self) -> list[CaseDefinition]:
        return list(self._cases.values())

    def get(self, case_id: str) -> CaseDefinition:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._cases))
            raise KeyError(f"Unknown case '{case_id}'. Available cases: {available}") from exc

    def select(self, case_ids: Iterable[str] | None = None) -> list[CaseDefinition]:
        if case_ids is None:
            return self.all()
        return [self.get(case_id) for case_id in case_ids]


DEFAULT_CASE_REGISTRY = CaseRegistry()
