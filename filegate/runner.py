"""Core runner flow for FileGate.

The runner intentionally separates case metadata from scenario construction so
the case catalog can grow without adding per-case branches to execution flow.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from threading import Event
from typing import Any

from filegate.artifact_validation import (
    ArtifactValidationError,
    validate_case_result_payload,
    validate_run_summary_consistency,
    validate_run_summary_payload,
)
from filegate.cases import (
    CaseDefinition,
    CaseRegistry,
    DEFAULT_CASE_REGISTRY,
    SimulationFixtureSpec,
)
from filegate.environment import PlatformMetadata, detect_platform_metadata

SCHEMA_VERSION = "0.1"
RESULT_STATUSES = {
    "pass",
    "fail",
    "warn",
    "skip",
    "manual_required",
    "unsupported",
    "timeout",
    "blocked",
    "inconclusive",
}


@dataclass(slots=True)
class TargetConfig:
    """Execution contract for a FileGate target process."""

    name: str
    command: list[str]
    sample_app: str
    version: str = "unknown"
    working_directory: Path | None = None
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RunRequest:
    """Input for a runner invocation."""

    target: TargetConfig
    output_dir: Path
    case_ids: list[str] | None = None
    run_id: str | None = None
    timeout_seconds: float | None = None
    platform_metadata: PlatformMetadata | None = None
    cancellation_event: Event | None = None
    simulation_root: Path | None = None
    execution_mode: str = "auto"


@dataclass(slots=True)
class CaseRunRecord:
    case_id: str
    status: str
    result_path: Path
    duration_ms: int


@dataclass(slots=True)
class RunSummary:
    run_id: str
    output_dir: Path
    target: TargetConfig
    case_records: list[CaseRunRecord]
    summary_path: Path


@dataclass(slots=True)
class PreparedFixture:
    """Materialized simulation fixture with absolute path metadata."""

    spec: SimulationFixtureSpec
    absolute_path: Path

    def to_payload(self) -> dict[str, Any]:
        payload = self.spec.to_contract_payload()
        payload["absolute_path"] = str(self.absolute_path)
        return payload


@dataclass(slots=True)
class ScenarioContext:
    """Inputs shared by scenario builders."""

    case: CaseDefinition
    run_id: str
    platform_metadata: PlatformMetadata
    simulation_root: Path
    simulation_enabled: bool


ScenarioBuilder = Callable[[ScenarioContext], dict[str, Any]]


@dataclass(slots=True)
class StepExecutionRecord:
    step_id: str
    step_index: int
    scenario_path: Path
    result_path: Path
    stdout_path: Path
    stderr_path: Path
    duration_ms: int
    payload: dict[str, Any]


class Runner:
    """Execute selected FileGate cases and persist normalized artifacts."""

    def __init__(self, case_registry: CaseRegistry = DEFAULT_CASE_REGISTRY) -> None:
        self._case_registry = case_registry
        self._scenario_builders: dict[str, ScenarioBuilder] = {
            "dialog_selection": self._build_dialog_selection_scenario,
            # multi_step cases use the dialog_selection builder for each individual step;
            # orchestration metadata is injected on top of the per-step payload by _run_target_step.
            "multi_step": self._build_dialog_selection_scenario,
        }

    def run(self, request: RunRequest) -> RunSummary:
        run_id = request.run_id or _generate_run_id(request.target.name)
        run_output_dir = request.output_dir / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)
        platform_metadata = request.platform_metadata or detect_platform_metadata()
        simulation_enabled = _resolve_simulation_enabled(
            request.execution_mode,
            platform_metadata,
        )

        case_records: list[CaseRunRecord] = []
        for case in self._case_registry.select(request.case_ids):
            if request.cancellation_event and request.cancellation_event.is_set():
                break
            case_records.append(
                self._execute_case(
                    request=request,
                    case=case,
                    run_id=run_id,
                    run_output_dir=run_output_dir,
                    platform_metadata=platform_metadata,
                    simulation_enabled=simulation_enabled,
                )
            )

        summary_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "platform": asdict(platform_metadata),
            "target": {
                "name": request.target.name,
                "version": request.target.version,
                "sample_app": request.target.sample_app,
            },
            "cases": [
                {
                    "case_id": record.case_id,
                    "status": record.status,
                    "duration_ms": record.duration_ms,
                    "result_path": str(record.result_path),
                }
                for record in case_records
            ],
        }
        summary_path = run_output_dir / "run-summary.json"
        validate_run_summary_payload(summary_payload, source=summary_path)
        case_payloads = [
            (
                record.result_path,
                json.loads(record.result_path.read_text(encoding="utf-8")),
            )
            for record in case_records
        ]
        validate_run_summary_consistency(summary_payload, case_payloads, source=summary_path)
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return RunSummary(run_id, run_output_dir, request.target, case_records, summary_path)

    def _execute_case(
        self,
        *,
        request: RunRequest,
        case: CaseDefinition,
        run_id: str,
        run_output_dir: Path,
        platform_metadata: PlatformMetadata,
        simulation_enabled: bool,
    ) -> CaseRunRecord:
        case_dir = run_output_dir / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        result_path = case_dir / "result.json"
        if case.scenario_builder_id == "multi_step":
            validated_payload = self._execute_multi_step_case(
                request=request,
                case=case,
                run_id=run_id,
                case_dir=case_dir,
                result_path=result_path,
                platform_metadata=platform_metadata,
                simulation_enabled=simulation_enabled,
            )
        else:
            validated_payload = self._execute_single_step_case(
                request=request,
                case=case,
                run_id=run_id,
                case_dir=case_dir,
                result_path=result_path,
                platform_metadata=platform_metadata,
                simulation_enabled=simulation_enabled,
            )

        result_path.write_text(
            json.dumps(validated_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return CaseRunRecord(
            case_id=case.case_id,
            status=validated_payload["result"]["status"],
            result_path=result_path,
            duration_ms=validated_payload["result"]["duration_ms"],
        )

    def _execute_single_step_case(
        self,
        *,
        request: RunRequest,
        case: CaseDefinition,
        run_id: str,
        case_dir: Path,
        result_path: Path,
        platform_metadata: PlatformMetadata,
        simulation_enabled: bool,
    ) -> dict[str, Any]:
        step_record = self._run_target_step(
            request=request,
            case=case,
            run_id=run_id,
            case_dir=case_dir,
            platform_metadata=platform_metadata,
            simulation_enabled=simulation_enabled,
            step_id="primary",
            step_index=1,
            total_steps=1,
            scenario_overrides={},
            scenario_name="scenario.json",
            step_result_name="result.json",
            stdout_name="stdout.log",
            stderr_name="stderr.log",
        )
        return self._load_and_validate_result(
            result_path=step_record.result_path,
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=request.target,
            duration_ms=step_record.duration_ms,
        )

    def _execute_multi_step_case(
        self,
        *,
        request: RunRequest,
        case: CaseDefinition,
        run_id: str,
        case_dir: Path,
        result_path: Path,
        platform_metadata: PlatformMetadata,
        simulation_enabled: bool,
    ) -> dict[str, Any]:
        simulation_root = request.simulation_root or case_dir / "simulation"
        steps = self._build_case_steps(
            case=case,
            case_dir=case_dir,
            simulation_root=simulation_root,
            simulation_enabled=simulation_enabled,
        )
        step_records: list[StepExecutionRecord] = []
        for step_index, step in enumerate(steps, start=1):
            step_records.append(
                self._run_target_step(
                    request=request,
                    case=case,
                    run_id=run_id,
                    case_dir=case_dir,
                    platform_metadata=platform_metadata,
                    simulation_enabled=simulation_enabled,
                    step_id=str(step["id"]),
                    step_index=step_index,
                    total_steps=len(steps),
                    scenario_overrides=dict(step.get("scenario_overrides") or {}),
                    scenario_name=f"scenario.step-{step_index}.json",
                    step_result_name=f"result.step-{step_index}.json",
                    stdout_name=f"stdout.step-{step_index}.log",
                    stderr_name=f"stderr.step-{step_index}.log",
                )
            )
            if request.cancellation_event and request.cancellation_event.is_set():
                break

        payload = self._aggregate_multi_step_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=request.target,
            step_records=step_records,
        )
        validate_case_result_payload(
            payload,
            source=result_path,
            expected_run_id=run_id,
            expected_case_id=case.case_id,
            expected_automation_level=case.automation_level,
        )
        return payload

    def _build_scenario_payload(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        simulation_root: Path,
        simulation_enabled: bool,
    ) -> dict[str, Any]:
        context = ScenarioContext(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            simulation_root=simulation_root,
            simulation_enabled=simulation_enabled,
        )
        builder = self._scenario_builders.get(case.scenario_builder_id)
        if builder is None:
            available = ", ".join(sorted(self._scenario_builders))
            raise ValueError(
                f"Unknown scenario builder '{case.scenario_builder_id}' for case '{case.case_id}'. "
                f"Available builders: {available}"
            )
        return builder(context)

    def register_scenario_builder(self, builder_id: str, builder: ScenarioBuilder) -> None:
        """Register a reusable scenario builder for future case families."""

        normalized = builder_id.strip()
        if not normalized:
            raise ValueError("builder_id must be a non-empty string.")
        self._scenario_builders[normalized] = builder

    def _build_dialog_selection_scenario(self, context: ScenarioContext) -> dict[str, Any]:
        case = context.case
        prepared_fixtures = self._prepare_simulation_fixtures(context)
        simulation_payload = self._build_simulation_payload(
            case=case,
            prepared_fixtures=prepared_fixtures,
            simulation_enabled=context.simulation_enabled,
        )

        return {
            "run_id": context.run_id,
            "platform": asdict(context.platform_metadata),
            "case": case.to_case_payload(),
            "dialog": case.dialog.to_payload(fallback_title=case.name),
            "expectation": case.expectation.to_payload(),
            "simulation": simulation_payload,
            "fixtures": {
                "root": str(context.simulation_root),
                "items": [fixture.to_payload() for fixture in prepared_fixtures],
            },
            "extensions": self._build_extension_payload(case.extensions),
            "scenario_contract": {
                "builder_id": case.scenario_builder_id,
                "family": case.family,
                "tags": list(case.tags),
                "target_notes": [
                    "Targets should treat dialog, expectation, simulation, and extensions as the stable scenario contract.",
                    "Avoid inferring semantics from case.id when a dedicated contract section provides the same information.",
                ],
            },
        }

    def _prepare_simulation_fixtures(self, context: ScenarioContext) -> list[PreparedFixture]:
        if not context.simulation_enabled:
            return []

        context.simulation_root.mkdir(parents=True, exist_ok=True)
        prepared: list[PreparedFixture] = []
        for fixture_spec in context.case.simulation.fixtures:
            absolute_path = context.simulation_root / fixture_spec.relative_path
            self._materialize_fixture(fixture_spec, absolute_path)
            prepared.append(PreparedFixture(spec=fixture_spec, absolute_path=absolute_path))
        return prepared

    def _materialize_fixture(self, fixture_spec: SimulationFixtureSpec, absolute_path: Path) -> None:
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        if fixture_spec.kind == "directory":
            if fixture_spec.materialize:
                absolute_path.mkdir(parents=True, exist_ok=True)
        elif fixture_spec.kind == "file":
            if fixture_spec.materialize:
                absolute_path.write_text(fixture_spec.content or "", encoding="utf-8")
        elif fixture_spec.kind == "symlink":
            if fixture_spec.materialize:
                target = fixture_spec.symlink_target
                if target is None:
                    raise ValueError(
                        f"Fixture '{fixture_spec.fixture_id}' requires symlink_target for kind='symlink'."
                    )
                if absolute_path.exists() or absolute_path.is_symlink():
                    absolute_path.unlink()
                absolute_path.symlink_to(target)
        else:  # pragma: no cover
            raise ValueError(f"Unsupported fixture kind '{fixture_spec.kind}'.")

        if fixture_spec.permissions is not None and fixture_spec.materialize:
            try:
                absolute_path.chmod(fixture_spec.permissions)
            except FileNotFoundError:
                pass

    def _build_simulation_payload(
        self,
        *,
        case: CaseDefinition,
        prepared_fixtures: list[PreparedFixture],
        simulation_enabled: bool,
    ) -> dict[str, Any]:
        payload = {
            "enabled": simulation_enabled,
            **case.simulation.to_contract_payload(),
        }

        if not simulation_enabled:
            return payload

        selection_paths = [
            str(prepared.absolute_path)
            for prepared in prepared_fixtures
            if prepared.spec.is_selection_fixture
        ]
        if case.dialog_type == "open_files":
            if selection_paths:
                payload["selected_paths"] = selection_paths
        elif selection_paths:
            payload["selected_path"] = selection_paths[0]

        return payload

    def _build_extension_payload(self, extensions: Mapping[str, Any]) -> dict[str, Any]:
        default_sections = {
            "path": {},
            "filters": {},
            "permissions": {},
            "persistence": {},
        }
        normalized = {section: dict(value) for section, value in default_sections.items()}
        for section_name, payload in dict(extensions).items():
            if isinstance(payload, Mapping):
                normalized[section_name] = dict(payload)
            else:
                normalized[section_name] = {"value": payload}
        return normalized
    def _run_target_step(
        self,
        *,
        request: RunRequest,
        case: CaseDefinition,
        run_id: str,
        case_dir: Path,
        platform_metadata: PlatformMetadata,
        simulation_enabled: bool,
        step_id: str,
        step_index: int,
        total_steps: int,
        scenario_overrides: dict[str, Any],
        scenario_name: str,
        step_result_name: str,
        stdout_name: str,
        stderr_name: str,
    ) -> StepExecutionRecord:
        scenario_path = case_dir / scenario_name
        stdout_path = case_dir / stdout_name
        stderr_path = case_dir / stderr_name
        step_result_path = case_dir / step_result_name
        step_simulation_root = (request.simulation_root or case_dir / "simulation") / f"step-{step_index}"

        scenario_payload = self._build_scenario_payload(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            simulation_root=step_simulation_root,
            simulation_enabled=simulation_enabled,
        )
        scenario_payload.setdefault("orchestration", {})
        scenario_payload["orchestration"].update(
            {
                "mode": case.orchestration,
                "step_id": step_id,
                "step_index": step_index,
                "total_steps": total_steps,
            }
        )
        scenario_payload = _deep_merge_dicts(scenario_payload, scenario_overrides)
        scenario_path.write_text(
            json.dumps(scenario_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        started = time.monotonic()
        process_result = self._invoke_target(
            target=request.target,
            scenario_path=scenario_path,
            output_path=step_result_path,
            timeout_seconds=request.timeout_seconds or case.default_timeout_seconds,
            cancellation_event=request.cancellation_event,
        )
        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        stdout_path.write_text(process_result["stdout"], encoding="utf-8")
        stderr_path.write_text(process_result["stderr"], encoding="utf-8")

        if process_result["timed_out"] or process_result["cancelled"]:
            payload = self._build_runner_managed_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=request.target,
                duration_ms=duration_ms,
                timed_out=process_result["timed_out"],
                cancelled=process_result["cancelled"],
                return_code=process_result["return_code"],
                notes=[
                    {
                        "code": "step_context",
                        "message": f"Runner-managed result was produced for step {step_index}/{total_steps} ({step_id}).",
                    }
                ],
            )
            step_result_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif not step_result_path.exists():
            payload = self._build_runner_managed_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=request.target,
                duration_ms=duration_ms,
                timed_out=False,
                cancelled=False,
                return_code=process_result["return_code"],
                status_override="inconclusive",
                notes=[
                    {
                        "code": "missing_result_output",
                        "message": "Target process exited without producing a result JSON file.",
                    },
                    {
                        "code": "step_context",
                        "message": f"The missing result occurred during step {step_index}/{total_steps} ({step_id}).",
                    },
                ],
            )
            step_result_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        payload = self._load_and_validate_result(
            result_path=step_result_path,
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=request.target,
            duration_ms=duration_ms,
        )
        step_result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return StepExecutionRecord(
            step_id=step_id,
            step_index=step_index,
            scenario_path=scenario_path,
            result_path=step_result_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            duration_ms=payload["result"]["duration_ms"],
            payload=payload,
        )

    def _build_case_steps(
        self,
        *,
        case: CaseDefinition,
        case_dir: Path,
        simulation_root: Path,
        simulation_enabled: bool,
    ) -> list[dict[str, Any]]:
        if case.orchestration == "repeat_dialog":
            return [
                {"id": "initial_open", "scenario_overrides": {}},
                {"id": "repeat_open", "scenario_overrides": {}},
            ]

        if case.orchestration == "restart_dialog":
            restart_file = str((simulation_root / "restart-dialog-selection.txt").resolve())
            return [
                {
                    "id": "before_restart",
                    "scenario_overrides": {
                        "simulation": {
                            "selected_path": restart_file,
                        }
                    },
                },
                {
                    "id": "after_restart",
                    "scenario_overrides": {
                        "simulation": {
                            "selected_path": restart_file,
                        },
                        "expectation": {
                            "post_restart": True,
                        }
                    },
                },
            ]

        if case.orchestration == "restart_probe":
            persisted_path = str((simulation_root / "persisted-resource.txt").resolve())
            return [
                {
                    "id": "grant_initial_access",
                    "scenario_overrides": {
                        "simulation": {
                            "selected_path": persisted_path,
                        },
                        "expectation": {
                            "persistence_case": True,
                        },
                    },
                },
                {
                    "id": "probe_after_restart",
                    "scenario_overrides": {
                        "dialog": {
                            "type": "probe_resource",
                        },
                        "expectation": {
                            "post_restart": True,
                            "expect_same_resource_as": "grant_initial_access",
                            "persistence_case": True,
                        },
                        "simulation": {
                            "probe_path": persisted_path,
                            "persisted_access": True,
                        },
                    },
                },
            ]

        if case.orchestration == "revocation_probe":
            revoked_path = str((simulation_root / "revoked-resource.txt").resolve())
            return [
                {
                    "id": "grant_initial_access",
                    "scenario_overrides": {
                        "simulation": {
                            "selected_path": revoked_path,
                        },
                        "expectation": {
                            "revocation_case": True,
                        },
                    },
                },
                {
                    "id": "probe_after_revocation",
                    "scenario_overrides": {
                        "dialog": {
                            "type": "probe_resource",
                        },
                        "expectation": {
                            "revocation_case": True,
                            "expect_same_resource_as": "grant_initial_access",
                            "revocation_observation_required": True,
                        },
                        "simulation": {
                            "probe_path": revoked_path,
                            "revoke_access": True,
                        },
                    },
                },
            ]

        if case.orchestration == "timeout_observation":
            return [
                {
                    "id": "await_dialog_timeout",
                    "scenario_overrides": {
                        "expectation": {
                            "runner_timeout_expected": True,
                        },
                        "simulation": {
                            "sleep_before_result_seconds": max(case.default_timeout_seconds * 3, 2.0),
                        },
                    },
                }
            ]

        raise ValueError(f"Unsupported orchestration mode: {case.orchestration}")

    def _aggregate_multi_step_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        if not step_records:
            return self._build_runner_managed_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                duration_ms=0,
                timed_out=False,
                cancelled=False,
                return_code=None,
                status_override="inconclusive",
                notes=[
                    {
                        "code": "no_step_results",
                        "message": "No step results were produced for the multi-step case.",
                    }
                ],
            )

        if case.orchestration == "repeat_dialog":
            return self._aggregate_repeat_dialog_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                step_records=step_records,
            )
        if case.orchestration == "restart_dialog":
            return self._aggregate_restart_dialog_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                step_records=step_records,
            )
        if case.orchestration == "restart_probe":
            return self._aggregate_restart_probe_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                step_records=step_records,
            )
        if case.orchestration == "revocation_probe":
            return self._aggregate_revocation_probe_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                step_records=step_records,
            )
        if case.orchestration == "timeout_observation":
            return self._aggregate_timeout_result(
                case=case,
                run_id=run_id,
                platform_metadata=platform_metadata,
                target=target,
                step_records=step_records,
            )
        raise ValueError(f"Unsupported orchestration mode: {case.orchestration}")

    def _aggregate_repeat_dialog_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        step_notes = _step_summary_notes(step_records)
        step_notes.append(
            {
                "code": "repeated_dialog_observation",
                "message": "This case records back-to-back dialog invocations to detect stale state or regression across repeated use.",
            }
        )
        statuses = [record.payload["result"]["status"] for record in step_records]
        final_status = "pass" if all(status == "pass" for status in statuses) else "fail"
        example = [record.payload["result"].get("returned_value_example") for record in step_records]
        return self._build_aggregated_case_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=target,
            duration_ms=sum(record.duration_ms for record in step_records),
            status=final_status,
            returned_resource_type="path",
            returned_value_example=example,
            can_read=all(bool(record.payload["result"].get("can_read")) for record in step_records),
            can_write=all(bool(record.payload["result"].get("can_write")) for record in step_records),
            error_code=None if final_status == "pass" else _first_non_null_error_code(step_records),
            notes=step_notes,
        )

    def _aggregate_restart_dialog_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        step_notes = _step_summary_notes(step_records)
        step_notes.append(
            {
                "code": "restart_observation",
                "message": "The second step represents a fresh target launch after the initial dialog execution.",
            }
        )
        final_status = "pass" if all(record.payload["result"]["status"] == "pass" for record in step_records) else "fail"
        return self._build_aggregated_case_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=target,
            duration_ms=sum(record.duration_ms for record in step_records),
            status=final_status,
            returned_resource_type="path",
            returned_value_example=[record.payload["result"].get("returned_value_example") for record in step_records],
            can_read=all(bool(record.payload["result"].get("can_read")) for record in step_records),
            can_write=all(bool(record.payload["result"].get("can_write")) for record in step_records),
            error_code=None if final_status == "pass" else _first_non_null_error_code(step_records),
            notes=step_notes,
        )

    def _aggregate_restart_probe_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        initial = step_records[0].payload["result"]
        probe = step_records[-1].payload["result"]
        persisted = bool(probe.get("can_read")) or bool(probe.get("can_write"))
        status = "pass" if persisted else "warn"
        error_code = None if persisted else (probe.get("error_code") or "PERSISTENCE_DENIED")
        notes = _step_summary_notes(step_records)
        notes.append(
            {
                "code": "persistence_expectation",
                "message": "Persistence after restart is environment-coupled; absence of persistence is recorded explicitly without assuming a universal failure.",
            }
        )
        notes.append(
            {
                "code": "persistence_observation",
                "message": (
                    "Access to the previously selected resource remained available after restart."
                    if persisted
                    else "Access to the previously selected resource was not available after restart."
                ),
            }
        )
        return self._build_aggregated_case_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=target,
            duration_ms=sum(record.duration_ms for record in step_records),
            status=status,
            returned_resource_type=str(initial.get("returned_resource_type") or "unknown"),
            returned_value_example={
                "initial": initial.get("returned_value_example"),
                "post_restart_probe": probe.get("returned_value_example"),
            },
            can_read=bool(probe.get("can_read")),
            can_write=bool(probe.get("can_write")),
            error_code=error_code,
            notes=notes,
        )

    def _aggregate_revocation_probe_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        initial = step_records[0].payload["result"]
        probe = step_records[-1].payload["result"]
        revoked = not (bool(probe.get("can_read")) or bool(probe.get("can_write")))
        status = "manual_required" if revoked else "warn"
        error_code = "ACCESS_REVOKED" if revoked else None
        notes = _step_summary_notes(step_records)
        notes.append(
            {
                "code": "manual_revocation_case",
                "message": "This case remains manual because true runtime revocation depends on platform-specific external action or sandbox behavior.",
            }
        )
        notes.append(
            {
                "code": "revocation_observation",
                "message": (
                    "The previously selected resource was no longer accessible after revocation."
                    if revoked
                    else "The previously selected resource still appeared accessible after the revocation probe; inspect environment-specific behavior."
                ),
            }
        )
        return self._build_aggregated_case_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=target,
            duration_ms=sum(record.duration_ms for record in step_records),
            status=status,
            returned_resource_type=str(initial.get("returned_resource_type") or "unknown"),
            returned_value_example={
                "initial": initial.get("returned_value_example"),
                "post_revocation_probe": probe.get("returned_value_example"),
            },
            can_read=bool(probe.get("can_read")),
            can_write=bool(probe.get("can_write")),
            error_code=error_code,
            notes=notes,
        )

    def _aggregate_timeout_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        step_records: list[StepExecutionRecord],
    ) -> dict[str, Any]:
        step = step_records[-1].payload["result"]
        notes = _step_summary_notes(step_records)
        notes.append(
            {
                "code": "timeout_semantics",
                "message": "This case verifies runner timeout vocabulary when the dialog is left open past the configured deadline.",
            }
        )
        status = "timeout" if step.get("status") == "timeout" else "fail"
        return self._build_aggregated_case_result(
            case=case,
            run_id=run_id,
            platform_metadata=platform_metadata,
            target=target,
            duration_ms=sum(record.duration_ms for record in step_records),
            status=status,
            returned_resource_type=str(step.get("returned_resource_type") or "unknown"),
            returned_value_example=step.get("returned_value_example"),
            can_read=bool(step.get("can_read")),
            can_write=bool(step.get("can_write")),
            error_code=step.get("error_code"),
            notes=notes,
        )

    def _build_aggregated_case_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        duration_ms: int,
        status: str,
        returned_resource_type: str,
        returned_value_example: Any,
        can_read: bool,
        can_write: bool,
        error_code: str | None,
        notes: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "platform": asdict(platform_metadata),
            "target": {
                "name": target.name,
                "version": target.version,
                "sample_app": target.sample_app,
            },
            "case": case.to_case_payload(),
            "result": {
                "status": status,
                "duration_ms": duration_ms,
                "returned_resource_type": returned_resource_type,
                "returned_value_example": returned_value_example,
                "can_read": can_read,
                "can_write": can_write,
                "error_code": error_code,
                "notes": notes,
            },
        }

    def _invoke_target(
        self,
        *,
        target: TargetConfig,
        scenario_path: Path,
        output_path: Path,
        timeout_seconds: float,
        cancellation_event: Event | None,
    ) -> dict[str, Any]:
        command = [
            *target.command,
            "--scenario",
            str(scenario_path.resolve()),
            "--output",
            str(output_path.resolve()),
        ]
        process = subprocess.Popen(
            command,
            cwd=target.working_directory,
            env={**os.environ, **target.environment},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        deadline = time.monotonic() + timeout_seconds
        timed_out = False
        cancelled = False
        while process.poll() is None:
            if cancellation_event and cancellation_event.is_set():
                cancelled = True
                process.terminate()
                break
            if time.monotonic() >= deadline:
                timed_out = True
                process.terminate()
                break
            time.sleep(0.05)

        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": process.returncode,
            "timed_out": timed_out,
            "cancelled": cancelled,
        }

    def _build_runner_managed_result(
        self,
        *,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        duration_ms: int,
        timed_out: bool,
        cancelled: bool,
        return_code: int | None,
        status_override: str | None = None,
        notes: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        result_notes = list(notes or [])
        status = status_override or "pass"
        if timed_out:
            status = "timeout"
            result_notes.append(
                {
                    "code": "runner_timeout",
                    "message": "Target execution exceeded the configured timeout.",
                }
            )
        elif cancelled:
            status = "blocked"
            result_notes.append(
                {
                    "code": "runner_cancelled",
                    "message": "Target execution was cancelled by the runner.",
                }
            )
        if return_code not in (0, None):
            result_notes.append(
                {
                    "code": "target_return_code",
                    "message": f"Target exited with return code {return_code}.",
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "platform": asdict(platform_metadata),
            "target": {
                "name": target.name,
                "version": target.version,
                "sample_app": target.sample_app,
            },
            "case": case.to_case_payload(),
            "result": {
                "status": status,
                "duration_ms": duration_ms,
                "returned_resource_type": "unknown",
                "returned_value_example": None,
                "can_read": False,
                "can_write": False,
                "error_code": None,
                "notes": result_notes,
            },
        }

    def _load_and_validate_result(
        self,
        *,
        result_path: Path,
        case: CaseDefinition,
        run_id: str,
        platform_metadata: PlatformMetadata,
        target: TargetConfig,
        duration_ms: int,
    ) -> dict[str, Any]:
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArtifactValidationError(
                "case result artifact",
                result_path,
                [
                    "Target wrote invalid JSON "
                    f"(line {exc.lineno}, column {exc.colno}): {exc.msg}"
                ],
            ) from exc

        if not isinstance(payload, dict):
            raise ArtifactValidationError(
                "case result artifact",
                result_path,
                [f"Target result root must be a JSON object, got {type(payload).__name__}."],
            )

        validate_case_result_payload(
            payload,
            source=result_path,
            expected_run_id=run_id,
            expected_case_id=case.case_id,
            expected_automation_level=case.automation_level,
        )

        result_duration = payload["result"]["duration_ms"]
        if result_duration > max(duration_ms + 1000, duration_ms * 2 + 1000):
            raise ArtifactValidationError(
                "case result artifact",
                result_path,
                [
                    "result.duration_ms is implausibly larger than the runner-observed case duration "
                    f"({result_duration} ms reported vs {duration_ms} ms observed)."
                ],
            )

        reported_target = payload.get("target")
        expected_target = {
            "name": target.name,
            "sample_app": target.sample_app,
        }
        if not isinstance(reported_target, dict) or {
            "name": reported_target.get("name"),
            "sample_app": reported_target.get("sample_app"),
        } != expected_target:
            raise ArtifactValidationError(
                "case result artifact",
                result_path,
                [
                    "target block must match the invoked target identity for name and sample_app. "
                    f"Expected {expected_target}, got {reported_target}."
                ],
            )

        if payload.get("platform") != asdict(platform_metadata):
            raise ArtifactValidationError(
                "case result artifact",
                result_path,
                [
                    "platform block must match the platform metadata captured for the run. "
                    f"Expected {asdict(platform_metadata)}, got {payload.get('platform')}."
                ],
            )

        return payload


def build_target_from_command(
    *,
    name: str,
    command: str,
    sample_app: str,
    version: str = "unknown",
    working_directory: str | None = None,
    environment: dict[str, str] | None = None,
) -> TargetConfig:
    return TargetConfig(
        name=name,
        command=shlex.split(command),
        sample_app=sample_app,
        version=version,
        working_directory=Path(working_directory) if working_directory else None,
        environment=environment or {},
    )


def _generate_run_id(target_name: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{timestamp}-{target_name}"


def _resolve_simulation_enabled(mode: str, platform_metadata: PlatformMetadata) -> bool:
    normalized = mode.lower().strip()
    if normalized == "simulation":
        return True
    if normalized == "interactive":
        return False
    if normalized != "auto":
        raise ValueError("execution_mode must be one of: auto, interactive, simulation")

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    session_known = str(platform_metadata.session_type or "unknown").lower() != "unknown"
    return not (has_display and session_known)


def _deep_merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in overrides.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


def _step_summary_notes(step_records: list[StepExecutionRecord]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    for record in step_records:
        step_result = record.payload.get("result", {})
        notes.append(
            {
                "code": f"step_{record.step_index}_status",
                "message": (
                    f"Step {record.step_index} ({record.step_id}) finished with status "
                    f"'{step_result.get('status')}' in {record.duration_ms} ms."
                ),
            }
        )
        for note in step_result.get("notes") or []:
            if not isinstance(note, dict):
                continue
            code = str(note.get("code") or "step_note").strip() or "step_note"
            message = str(note.get("message") or "").strip()
            if not message:
                continue
            notes.append(
                {
                    "code": f"step_{record.step_index}_{code.lower()}",
                    "message": f"Step {record.step_index} ({record.step_id}): {message}",
                }
            )
    return notes


def _first_non_null_error_code(step_records: list[StepExecutionRecord]) -> str | None:
    for record in step_records:
        error_code = record.payload.get("result", {}).get("error_code")
        if error_code is not None:
            return str(error_code)
    return None
