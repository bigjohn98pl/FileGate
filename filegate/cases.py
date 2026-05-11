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
ORCHESTRATION_MODES = {
    "single",
    "repeat_dialog",
    "restart_dialog",
    "restart_probe",
    "revocation_probe",
    "timeout_observation",
}


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
    orchestration: str = "single"

    def __post_init__(self) -> None:
        if self.automation_level not in AUTOMATION_LEVELS:
            raise ValueError(
                f"Unsupported automation level for {self.case_id}: {self.automation_level}"
            )
        if not self.scenario_builder_id.strip():
            raise ValueError("scenario_builder_id must be a non-empty string.")
        if self.orchestration not in ORCHESTRATION_MODES:
            raise ValueError(
                f"Unsupported orchestration mode for {self.case_id}: {self.orchestration}"
            )

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
    CaseDefinition(
        case_id="open_dialog_multiple_times",
        name="Open dialog multiple times",
        automation_level="semi_automatic",
        objective="Verify that repeated dialog use remains stable across back-to-back invocations.",
        preconditions=("Target executable is available.",),
        steps=(
            "Run the dialog open scenario twice in sequence.",
            "Collect both returned resources and compare the observed behavior.",
        ),
        expected_result="Both dialog invocations complete without stale state, crashes, or schema regressions.",
        artifacts=(
            "scenario_json",
            "result_json",
            "stdout_log",
            "stderr_log",
            "step_result_json",
        ),
        dialog=DialogSpec(dialog_type="open_file"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="selected_file",
                    relative_path="repeat-selection.txt",
                    role="selection",
                    content="FileGate repeat dialog fixture\n",
                ),
            ),
        ),
        family="stability_persistence",
        tags=("stability_persistence", "open", "repeat"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            persistence={"expectation": "not_evaluated"},
        ),
        scenario_builder_id="multi_step",
        orchestration="repeat_dialog",
    ),
    CaseDefinition(
        case_id="open_after_app_restart",
        name="Open after app restart",
        automation_level="semi_automatic",
        objective="Verify that the target can open the same dialog flow again after a full app restart.",
        preconditions=("Target executable is available.",),
        steps=(
            "Run the dialog scenario once and collect the returned resource.",
            "Restart the target application and run the dialog scenario again.",
            "Compare the post-restart observation with the initial run.",
        ),
        expected_result="The dialog works again after restart and the post-restart run is recorded explicitly.",
        artifacts=(
            "scenario_json",
            "result_json",
            "stdout_log",
            "stderr_log",
            "step_result_json",
        ),
        dialog=DialogSpec(dialog_type="open_file"),
        family="stability_persistence",
        tags=("stability_persistence", "open", "restart"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            persistence={"expectation": "not_evaluated"},
        ),
        scenario_builder_id="multi_step",
        orchestration="restart_dialog",
    ),
    CaseDefinition(
        case_id="persistent_access_after_restart",
        name="Persistent access after restart",
        automation_level="semi_automatic",
        objective="Observe whether access to a previously selected resource remains available after target restart.",
        preconditions=("Target executable is available.",),
        steps=(
            "Select a resource and record the returned value and access flags.",
            "Restart the target.",
            "Probe the previously selected resource after restart and record the observation.",
        ),
        expected_result="Persistence behavior after restart is encoded explicitly in status and notes.",
        artifacts=(
            "scenario_json",
            "result_json",
            "stdout_log",
            "stderr_log",
            "step_result_json",
        ),
        dialog=DialogSpec(dialog_type="open_file"),
        family="stability_persistence",
        tags=("stability_persistence", "open", "persistence", "restart"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            persistence={"expectation": "explicit_observation"},
        ),
        scenario_builder_id="multi_step",
        orchestration="restart_probe",
    ),
    CaseDefinition(
        case_id="revoked_access_behavior",
        name="Revoked access behavior",
        automation_level="manual",
        objective="Record how access revocation is surfaced after a previously granted resource becomes unavailable.",
        preconditions=(
            "Target executable is available.",
            "A revocation mechanism or controlled test fixture is available.",
        ),
        steps=(
            "Select a resource and confirm initial access.",
            "Revoke or remove the granted resource.",
            "Probe the previously selected resource and record the revocation observation.",
        ),
        expected_result="Revocation behavior is encoded explicitly without overstating automation coverage.",
        artifacts=(
            "scenario_json",
            "result_json",
            "stdout_log",
            "stderr_log",
            "step_result_json",
        ),
        dialog=DialogSpec(dialog_type="open_file"),
        family="stability_persistence",
        tags=("stability_persistence", "open", "revocation", "manual"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            persistence={"expectation": "revocation_observation"},
        ),
        scenario_builder_id="multi_step",
        orchestration="revocation_probe",
    ),
    CaseDefinition(
        case_id="timeout_when_dialog_not_closed",
        name="Timeout when dialog not closed",
        automation_level="semi_automatic",
        objective="Verify that runner timeout semantics are captured when a dialog remains open past the configured deadline.",
        preconditions=("Target executable is available.",),
        steps=(
            "Launch the dialog scenario.",
            "Do not close the dialog before the timeout expires.",
            "Record the runner-managed timeout result.",
        ),
        expected_result="The run records an explicit timeout status with structured notes.",
        artifacts=(
            "scenario_json",
            "result_json",
            "stdout_log",
            "stderr_log",
            "step_result_json",
        ),
        dialog=DialogSpec(dialog_type="open_file"),
        family="stability_persistence",
        tags=("stability_persistence", "open", "timeout"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            persistence={"expectation": "not_evaluated"},
        ),
        scenario_builder_id="multi_step",
        default_timeout_seconds=1.0,
        orchestration="timeout_observation",
    ),
    CaseDefinition(
        case_id="flatpak_open_file_portal",
        name="Flatpak open file portal",
        automation_level="semi_automatic",
        objective="Verify a portal-mediated open-file request under Flatpak-oriented assumptions and capture returned URI/path behavior.",
        preconditions=(
            "Linux environment with XDG Desktop Portal FileChooser support.",
            "Interactive execution requires a desktop session and portal backend.",
        ),
        steps=(
            "Run the portal-oriented open-file scenario.",
            "Observe whether the result is returned as URI, path, or both via notes.",
            "Capture sandbox grant observations.",
        ),
        expected_result="A portal-mediated file selection is recorded with explicit portal and sandbox metadata.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"resource_type_preference": "uri"},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="portal_open_file",
                    relative_path="portal-open.txt",
                    role="selection",
                    content="portal-open\n",
                    metadata={"use_uri": True},
                ),
            ),
        ),
        family="xdg_portal",
        tags=("xdg_portal", "open", "flatpak", "portal"),
        scenario_builder_id="portal_selection",
        default_timeout_seconds=30.0,
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            portal={"portal_expected": True, "sandbox_expected": True, "resource_type_preference": "uri"},
        ),
    ),
    CaseDefinition(
        case_id="flatpak_save_file_portal",
        name="Flatpak save file portal",
        automation_level="semi_automatic",
        objective="Verify a portal-mediated save-file request under Flatpak-oriented assumptions and capture returned URI/path behavior.",
        preconditions=(
            "Linux environment with XDG Desktop Portal FileChooser support.",
            "Interactive execution requires a desktop session and portal backend.",
        ),
        steps=(
            "Run the portal-oriented save-file scenario.",
            "Observe whether the result is returned as URI, path, or both via notes.",
            "Capture sandbox grant observations.",
        ),
        expected_result="A portal-mediated save selection is recorded with explicit portal and sandbox metadata.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="save_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"resource_type_preference": "uri"},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="portal_save_file",
                    relative_path="portal-save.txt",
                    role="selection",
                    materialize=False,
                    metadata={"use_uri": True},
                ),
            ),
        ),
        family="xdg_portal",
        tags=("xdg_portal", "save", "flatpak", "portal"),
        scenario_builder_id="portal_selection",
        default_timeout_seconds=30.0,
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            permissions={"requires_write_access": True},
            portal={"portal_expected": True, "sandbox_expected": True, "resource_type_preference": "uri"},
        ),
    ),
    CaseDefinition(
        case_id="portal_cancel_behavior",
        name="Portal cancel behavior",
        automation_level="semi_automatic",
        objective="Verify that portal cancellation is encoded semantically and keeps portal context visible.",
        preconditions=("Linux environment with XDG Desktop Portal FileChooser support.",),
        steps=("Run the portal-oriented dialog and cancel it.", "Capture portal response semantics."),
        expected_result="Cancellation is reported semantically with explicit portal notes.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            cancel_is_expected=True,
            options={"resource_type_preference": "uri"},
        ),
        simulation=SimulationSpec(cancel=True),
        family="xdg_portal",
        tags=("xdg_portal", "open", "portal", "cancel"),
        scenario_builder_id="portal_selection",
        default_timeout_seconds=30.0,
        extensions=_extension_contract(
            path={"selection_mode": "single"},
            portal={"portal_expected": True, "sandbox_expected": True, "resource_type_preference": "uri"},
        ),
    ),
    CaseDefinition(
        case_id="portal_returns_uri_or_path",
        name="Portal returns URI or path",
        automation_level="semi_automatic",
        objective="Record whether the portal-facing target observed a URI, a host path, or a converted file path for a selected resource.",
        preconditions=("Linux environment with XDG Desktop Portal FileChooser support.",),
        steps=("Run the portal-oriented open-file scenario.", "Record observed resource-return semantics."),
        expected_result="The result explicitly states whether the observed resource was URI-backed, path-backed, or converted from URI.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"resource_type_preference": "uri"},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="portal_uri_or_path_file",
                    relative_path="portal-uri-or-path.txt",
                    role="selection",
                    content="portal-uri-or-path\n",
                    metadata={"use_uri": True},
                ),
            ),
        ),
        family="xdg_portal",
        tags=("xdg_portal", "open", "portal", "uri_path_semantics"),
        scenario_builder_id="portal_selection",
        default_timeout_seconds=30.0,
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            portal={"portal_expected": True, "sandbox_expected": True, "resource_type_preference": "uri"},
        ),
    ),
    CaseDefinition(
        case_id="sandbox_no_home_access_without_grant",
        name="Sandbox no home access without grant",
        automation_level="automatic",
        objective="Record whether a Flatpak-like sandbox exposes host home access without explicit filesystem grants.",
        preconditions=("Sandbox metadata detection is available.",),
        steps=(
            "Inspect sandbox metadata and filesystem grants.",
            "Report whether host home access appears absent, partial, or full.",
        ),
        expected_result="The output explicitly documents host home access observations and whether the environment is a clean no-grant baseline.",
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        simulation=SimulationSpec(
            options={"metadata_only": True},
        ),
        family="xdg_portal",
        tags=("xdg_portal", "sandbox", "flatpak", "automatic"),
        scenario_builder_id="portal_selection",
        extensions=_extension_contract(
            portal={"portal_expected": False, "sandbox_expected": True},
        ),
    ),
    # ── Dialog basics – save overwrite ────────────────────────────────────────
    CaseDefinition(
        case_id="save_file_overwrite",
        name="Save file overwrite",
        automation_level="semi_automatic",
        objective=(
            "Verify that a save dialog can be directed at an already-existing file "
            "and that the target reports the resulting write-access flags and any "
            "overwrite-confirmation semantics."
        ),
        preconditions=("Target executable is available.",),
        steps=(
            "Materialize a pre-existing file at the save destination.",
            "Run the save dialog scenario pointing to the pre-existing file.",
            "Collect the returned path and access flags.",
        ),
        expected_result=(
            "The returned path refers to the pre-existing file and write access is "
            "confirmed; notes document overwrite-confirmation behavior observed."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="save_file"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="overwrite_target",
                    relative_path="overwrite-target.txt",
                    role="selection",
                    materialize=True,
                    content="Original content before overwrite\n",
                ),
            ),
        ),
        family="dialog_basics",
        tags=("dialog_basics", "save", "overwrite"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "precondition": "file_exists",
            },
            permissions={"requires_write_access": True},
            persistence={"expectation": "not_evaluated"},
        ),
    ),
    # ── Path and naming ───────────────────────────────────────────────────────
    CaseDefinition(
        case_id="path_with_spaces",
        name="Path with spaces",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target correctly handles and returns a path that contains "
            "space characters in the directory or filename component."
        ),
        preconditions=("Target executable is available.",),
        steps=(
            "Materialize a file inside a directory whose name contains spaces.",
            "Run the open-file scenario against the spaced path.",
            "Verify the returned path is complete and untruncated.",
        ),
        expected_result=(
            "The returned path preserves the embedded spaces without truncation, "
            "encoding, or quoting artefacts."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"expect_spaces_preserved": True},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="spaced_path_file",
                    relative_path="path with spaces/file with spaces.txt",
                    role="selection",
                    content="FileGate path-with-spaces fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "spaces"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "spaces_in_path",
            },
        ),
    ),
    CaseDefinition(
        case_id="unicode_filename",
        name="Unicode filename",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target correctly handles and returns a filename that "
            "contains non-ASCII Unicode characters outside the Latin-1 range."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports Unicode filenames.",
        ),
        steps=(
            "Materialize a file with a Unicode filename.",
            "Run the open-file scenario against the Unicode filename.",
            "Verify the returned path preserves the Unicode characters.",
        ),
        expected_result=(
            "The returned path preserves all Unicode characters without corruption, "
            "replacement, or lossy encoding."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="unicode_file",
                    relative_path="zażółć-gęślą-jaźń.txt",
                    role="selection",
                    content="FileGate unicode filename fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "unicode", "encoding"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "unicode_filename",
                "encoding_risk": "unicode_normalization",
            },
        ),
    ),
    CaseDefinition(
        case_id="polish_characters_filename",
        name="Polish characters filename",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target correctly handles filenames containing Polish "
            "diacritic characters (ą ć ę ł ń ó ś ź ż and their uppercase variants)."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports UTF-8 filenames.",
        ),
        steps=(
            "Materialize a file with Polish diacritics in the filename.",
            "Run the open-file scenario against the file.",
            "Verify the returned path preserves the diacritics.",
        ),
        expected_result=(
            "The returned path preserves all Polish diacritics without substitution "
            "or mojibake; notes document any observed locale-dependent behaviour."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="polish_file",
                    relative_path="plik-z-polskimi-znakami-ąćęłńóśźż.txt",
                    role="selection",
                    content="FileGate polish-characters fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "polish", "unicode", "diacritics"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "polish_diacritics",
                "encoding_risk": "locale_interaction",
            },
        ),
    ),
    CaseDefinition(
        case_id="very_long_filename",
        name="Very long filename",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target can handle filenames at or near the filesystem "
            "maximum length (255 bytes on most POSIX systems) without truncation."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports long filenames.",
        ),
        steps=(
            "Materialize a file whose filename is 200+ characters long.",
            "Run the open-file scenario against the long-named file.",
            "Verify the returned path preserves the full filename length.",
        ),
        expected_result=(
            "The returned path contains the full untruncated filename; notes document "
            "any observed truncation or length-limit behaviour."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"min_filename_length": 200},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="long_filename_file",
                    relative_path=("a" * 200 + ".txt"),
                    role="selection",
                    content="FileGate very-long-filename fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "long_filename"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "very_long_filename",
                "filename_length": 204,
            },
        ),
    ),
    CaseDefinition(
        case_id="nested_directory_path",
        name="Nested directory path",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target correctly returns a path that is several directory "
            "levels deep relative to the filesystem root."
        ),
        preconditions=("Target executable is available.",),
        steps=(
            "Materialize a file inside a deeply nested directory tree.",
            "Run the open-file scenario against the nested file.",
            "Verify the returned path contains all intermediate directories.",
        ),
        expected_result=(
            "The returned path preserves all directory levels without truncation or "
            "flattening; notes document any depth-related limitations."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="nested_file",
                    relative_path="level1/level2/level3/level4/nested-file.txt",
                    role="selection",
                    content="FileGate nested-directory fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "nested_directory"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "nested_directory",
                "nesting_depth": 4,
            },
        ),
    ),
    CaseDefinition(
        case_id="relative_vs_absolute_path",
        name="Relative vs absolute path",
        automation_level="semi_automatic",
        objective=(
            "Verify that a target always returns an absolute path regardless of "
            "whether the scenario fixture is resolved from a relative working directory."
        ),
        preconditions=("Target executable is available.",),
        steps=(
            "Materialize a fixture with a path relative to the simulation root.",
            "Run the open-file scenario and collect the returned path.",
            "Check whether the returned path is absolute.",
        ),
        expected_result=(
            "The returned path is absolute (starts with '/'); notes document any "
            "target-specific relative-path behaviour."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(
            expected_selection_count=1,
            options={"expect_absolute_path": True},
        ),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="relative_path_file",
                    relative_path="relative-path-fixture.txt",
                    role="selection",
                    content="FileGate relative-vs-absolute fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "relative_path", "absolute_path"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "relative_vs_absolute",
                "expect_absolute": True,
            },
        ),
    ),
    CaseDefinition(
        case_id="case_sensitive_collision",
        name="Case sensitive collision",
        automation_level="semi_automatic",
        objective=(
            "Verify how a target handles two fixture files that differ only in the "
            "case of their filename, which is significant on case-sensitive Linux "
            "filesystems but collapses to one entry on macOS HFS+ and Windows NTFS."
        ),
        preconditions=(
            "Target executable is available.",
            "Case-sensitive filesystem (standard Linux ext4/btrfs).",
        ),
        steps=(
            "Materialize two fixtures that differ only by case: File.txt and file.txt.",
            "Run the open-file scenario selecting the lowercase variant.",
            "Verify the returned path reflects the exact case used.",
        ),
        expected_result=(
            "The returned path preserves the exact case of the selected filename; "
            "notes document any case-folding or collision behaviour."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="lowercase_file",
                    relative_path="case-collision/file.txt",
                    role="selection",
                    content="FileGate lowercase case-collision fixture\n",
                ),
                SimulationFixtureSpec(
                    fixture_id="uppercase_file",
                    relative_path="case-collision/File.txt",
                    role="supporting",
                    content="FileGate uppercase case-collision fixture\n",
                ),
            ),
        ),
        family="path_naming",
        tags=("path_naming", "open", "case_sensitivity"),
        extensions=_extension_contract(
            path={
                "expected_resource_kind": "file",
                "selection_mode": "single",
                "path_variant": "case_sensitive_collision",
                "case_sensitivity_risk": "filesystem_dependent",
            },
        ),
    ),
    # ── Permissions ───────────────────────────────────────────────────────────
    CaseDefinition(
        case_id="read_only_file",
        name="Read only file",
        automation_level="automatic",
        objective=(
            "Verify that a read-only file (permissions 0o444) can be selected via an "
            "open dialog and that the target explicitly reports can_read=True and "
            "can_write=False without collapsing the result into a generic unknown outcome."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports POSIX permission bits.",
        ),
        steps=(
            "Materialize a file with read-only permissions (0o444).",
            "Run the open-file scenario selecting the read-only file.",
            "Verify can_read=True and can_write=False are reported explicitly.",
        ),
        expected_result=(
            "can_read=True, can_write=False, error_code=null, status=pass; "
            "notes confirm the read-only permission observation."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="read_only_file",
                    relative_path="permissions/read-only-file.txt",
                    role="selection",
                    materialize=True,
                    content="FileGate read-only permissions fixture\n",
                    permissions=0o444,
                ),
            ),
        ),
        family="permissions",
        tags=("permissions", "open", "read_only"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            permissions={
                "permission_case": True,
                "fixture_permissions_octal": "0o444",
                "permission_case_semantics": "read_only_accessible",
                "expected_can_read": True,
                "expected_can_write": False,
                "expected_error_code": None,
            },
        ),
    ),
    CaseDefinition(
        case_id="write_to_read_only_file",
        name="Write to read only file",
        automation_level="automatic",
        objective=(
            "Verify that attempting to write to a read-only file (0o444) via a save "
            "dialog produces can_write=False and error_code=PERMISSION_DENIED explicitly, "
            "without collapsing the denial into a generic unknown outcome."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports POSIX permission bits.",
        ),
        steps=(
            "Materialize a pre-existing file with read-only permissions (0o444).",
            "Run the save-file scenario pointing at the read-only file.",
            "Verify can_write=False and error_code=PERMISSION_DENIED are reported.",
        ),
        expected_result=(
            "can_read=True, can_write=False, error_code=PERMISSION_DENIED, status=warn; "
            "notes document that write access was denied due to read-only permissions."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="save_file"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="read_only_save_target",
                    relative_path="permissions/read-only-save-target.txt",
                    role="selection",
                    materialize=True,
                    content="FileGate read-only save target fixture\n",
                    permissions=0o444,
                ),
            ),
        ),
        family="permissions",
        tags=("permissions", "save", "read_only", "write_denied"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            permissions={
                "permission_case": True,
                "fixture_permissions_octal": "0o444",
                "permission_case_semantics": "write_denied_read_only",
                "requires_write_access": True,
                "expected_can_read": True,
                "expected_can_write": False,
                "expected_error_code": "PERMISSION_DENIED",
            },
        ),
    ),
    CaseDefinition(
        case_id="permission_denied_file",
        name="Permission denied file",
        automation_level="automatic",
        objective=(
            "Verify that a file with no access permissions (0o000) is handled so that "
            "can_read=False, can_write=False, and error_code=PERMISSION_DENIED are set "
            "explicitly rather than falling through to a generic unknown outcome."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports POSIX permission bits.",
            "Test process is not running as root (root bypasses permission checks).",
        ),
        steps=(
            "Materialize a file with no permissions (0o000).",
            "Run the open-file scenario selecting the inaccessible file.",
            "Verify can_read=False, can_write=False, and error_code=PERMISSION_DENIED.",
        ),
        expected_result=(
            "can_read=False, can_write=False, error_code=PERMISSION_DENIED, status=warn; "
            "notes document that access was denied due to restrictive permissions."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="denied_file",
                    relative_path="permissions/denied-file.txt",
                    role="selection",
                    materialize=True,
                    content="FileGate permission-denied fixture\n",
                    permissions=0o000,
                ),
            ),
        ),
        family="permissions",
        tags=("permissions", "open", "access_denied"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            permissions={
                "permission_case": True,
                "fixture_permissions_octal": "0o000",
                "permission_case_semantics": "access_denied",
                "expected_can_read": False,
                "expected_can_write": False,
                "expected_error_code": "PERMISSION_DENIED",
            },
        ),
    ),
    CaseDefinition(
        case_id="permission_denied_directory",
        name="Permission denied directory",
        automation_level="automatic",
        objective=(
            "Verify that a directory with no access permissions (0o000) is handled so "
            "that can_read=False and error_code=PERMISSION_DENIED are set explicitly "
            "rather than falling through to a generic unknown outcome."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports POSIX permission bits.",
            "Test process is not running as root (root bypasses permission checks).",
        ),
        steps=(
            "Materialize a directory with no permissions (0o000).",
            "Run the open-folder scenario selecting the inaccessible directory.",
            "Verify can_read=False and error_code=PERMISSION_DENIED.",
        ),
        expected_result=(
            "can_read=False, can_write=False, error_code=PERMISSION_DENIED, status=warn; "
            "notes document that directory access was denied due to restrictive permissions."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_folder"),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="denied_directory",
                    relative_path="permissions/denied-directory",
                    kind="directory",
                    role="selection",
                    materialize=True,
                    permissions=0o000,
                ),
            ),
        ),
        family="permissions",
        tags=("permissions", "open", "directory", "access_denied"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "directory", "selection_mode": "single"},
            permissions={
                "permission_case": True,
                "fixture_permissions_octal": "0o000",
                "permission_case_semantics": "access_denied",
                "expected_can_read": False,
                "expected_can_write": False,
                "expected_error_code": "PERMISSION_DENIED",
            },
        ),
    ),

    CaseDefinition(
        case_id="execute_permission_irrelevant",
        name="Execute permission irrelevant",
        automation_level="automatic",
        objective=(
            "Verify that a file with execute-only permissions (0o111) is handled so "
            "that can_read=False is reported explicitly, confirming that the execute bit "
            "does not grant read access to regular files."
        ),
        preconditions=(
            "Target executable is available.",
            "Filesystem supports POSIX permission bits.",
            "Test process is not running as root (root bypasses permission checks).",
        ),
        steps=(
            "Materialize a file with execute-only permissions (0o111).",
            "Run the open-file scenario selecting the execute-only file.",
            "Verify can_read=False is explicitly reported.",
        ),
        expected_result=(
            "can_read=False, can_write=False, error_code=null, status=pass; "
            "notes confirm that execute-only permission correctly denies read access."
        ),
        artifacts=DEFAULT_ARTIFACTS,
        dialog=DialogSpec(dialog_type="open_file"),
        expectation=ExpectationSpec(expected_selection_count=1),
        simulation=SimulationSpec(
            fixtures=(
                SimulationFixtureSpec(
                    fixture_id="execute_only_file",
                    relative_path="permissions/execute-only-file.txt",
                    role="selection",
                    materialize=True,
                    content="FileGate execute-only permissions fixture\n",
                    permissions=0o111,
                ),
            ),
        ),
        family="permissions",
        tags=("permissions", "open", "execute_only"),
        extensions=_extension_contract(
            path={"expected_resource_kind": "file", "selection_mode": "single"},
            permissions={
                "permission_case": True,
                "fixture_permissions_octal": "0o111",
                "permission_case_semantics": "execute_only_no_read",
                "expected_can_read": False,
                "expected_can_write": False,
                "expected_error_code": None,
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
