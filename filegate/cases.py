"""Case registry for FileGate MVP execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

AUTOMATION_LEVELS = {"automatic", "semi_automatic", "manual"}


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
    dialog_type: str
    default_timeout_seconds: float = 10.0
    cancel_is_expected: bool = False

    def __post_init__(self) -> None:
        if self.automation_level not in AUTOMATION_LEVELS:
            raise ValueError(
                f"Unsupported automation level for {self.case_id}: {self.automation_level}"
            )

    def to_case_payload(self) -> dict[str, str]:
        return {
            "id": self.case_id,
            "name": self.name,
            "automation_level": self.automation_level,
        }


MVP_CASES: tuple[CaseDefinition, ...] = (
    CaseDefinition(
        case_id="open_file_single",
        name="Open file single",
        automation_level="semi_automatic",
        objective="Verify that a target returns a single selected file resource.",
        preconditions=("Target executable is available.",),
        steps=("Run the open file scenario.", "Collect the returned resource."),
        expected_result="Exactly one selected file resource is returned.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="open_file",
    ),
    CaseDefinition(
        case_id="open_file_multiple",
        name="Open file multiple",
        automation_level="semi_automatic",
        objective="Verify that a target returns multiple selected file resources.",
        preconditions=("Target executable is available.",),
        steps=("Run the open multiple files scenario.", "Collect returned resources."),
        expected_result="At least two selected file resources are returned.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="open_files",
    ),
    CaseDefinition(
        case_id="open_folder",
        name="Open folder",
        automation_level="semi_automatic",
        objective="Verify that a target returns a selected directory resource.",
        preconditions=("Target executable is available.",),
        steps=("Run the open folder scenario.", "Collect the returned resource."),
        expected_result="A selected folder resource is returned.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="open_folder",
    ),
    CaseDefinition(
        case_id="save_file_new",
        name="Save file new",
        automation_level="semi_automatic",
        objective="Verify that a target returns a writable save destination.",
        preconditions=("Target executable is available.",),
        steps=("Run the save file scenario.", "Collect the returned save location."),
        expected_result="A writable save destination is returned.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="save_file",
    ),
    CaseDefinition(
        case_id="cancel_open_dialog",
        name="Cancel open dialog",
        automation_level="semi_automatic",
        objective="Verify that expected dialog cancellation is encoded semantically.",
        preconditions=("Target executable is available.",),
        steps=("Run the open dialog cancellation scenario.", "Collect cancel result."),
        expected_result="Cancellation is reported as pass with USER_CANCELLED semantics.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="open_file",
        cancel_is_expected=True,
    ),
    CaseDefinition(
        case_id="cancel_save_dialog",
        name="Cancel save dialog",
        automation_level="semi_automatic",
        objective="Verify that expected save cancellation is encoded semantically.",
        preconditions=("Target executable is available.",),
        steps=("Run the save dialog cancellation scenario.", "Collect cancel result."),
        expected_result="Cancellation is reported as pass with USER_CANCELLED semantics.",
        artifacts=("scenario_json", "result_json", "stdout_log", "stderr_log"),
        dialog_type="save_file",
        cancel_is_expected=True,
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
