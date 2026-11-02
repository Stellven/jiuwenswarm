"""SIMLAB-IF-001@r1 record models: Experiment, Manifest, Result, typed error.

Field names follow PAS-M1-001 TASK §4 exactly. Sub-structures that the field
table leaves to the owning task are fixed here and exported as JSON Schema
(`simlab/schemas/`), which is drift-checked against these models.

Every model forbids unknown fields: an unknown field is a finding.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    Anchoring,
    ArmRole,
    ArtifactKind,
    AttemptStatus,
    CheckKind,
    CheckStatus,
    EvidenceLevel,
    FeasibilityStatus,
    InvalidReason,
    MeasurementScope,
    ObjectiveKind,
    RunKind,
    RunStatus,
    Severity,
)

SCHEMA_VERSION = "simlab-if-001@r1"
Id = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:\-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Scalar = Union[float, int, str, bool, None]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- experiment parts
class StandIn(Model):
    stands_in_for: str
    stand_in: str
    origin: str


class ProtocolItem(Model):
    item_id: Id
    item_kind: Literal["predicate", "threshold", "arm", "variable", "trial_count", "measurement", "procedure", "other"]
    value: Any = None
    origin: str | None = Field(None, description="Source reference with locator, or 'requester_declared'")


class SourceRef(Model):
    source_id: Id
    ref: str
    sha256: Sha256 | None = None


class FeasibilityEntry(Model):
    dependency_id: Id
    dependency_kind: Literal["engine", "library", "asset", "code", "weights", "data", "model", "service", "other"]
    status: FeasibilityStatus
    reason: str = ""
    evidence_ref: str | None = None
    affected_arms: list[Id] = Field(default_factory=list)


class EngineDecl(Model):
    engine: Literal["mujoco"]
    version: str
    why: str


class ResolvedConfiguration(Model):
    """Every effective engine and runner setting. Required fields have no default:
    nothing implicit. The executor records the effective engine options as run."""
    engine: Literal["mujoco"]
    timestep: float = Field(gt=0, le=1.0)
    integrator: Literal["Euler", "RK4", "implicit", "implicitfast"]
    solver: Literal["PGS", "CG", "Newton"]
    iterations: int = Field(ge=1, le=10000)
    tolerance: float = Field(ge=0)
    ls_iterations: int = Field(50, ge=0, le=10000)
    noslip_iterations: int = Field(0, ge=0, le=10000)
    cone: Literal["pyramidal", "elliptic"] = "pyramidal"
    impratio: float = Field(1.0, gt=0)
    gravity: list[float] | None = Field(None, min_length=3, max_length=3, description="m/s^2; None keeps the model file's value (recorded as run)")
    enable_flags: list[str] = Field(default_factory=list)
    disable_flags: list[str] = Field(default_factory=list)
    control_every_steps: int = Field(1, ge=1, description="Controller components are called every N steps")


class AssetsRef(Model):
    manifest_id: Id
    manifest_sha256: Sha256


class ComponentBinding(Model):
    extension_point: Literal["scene", "controller", "measurement"]
    artifact: str = Field(min_length=1, description="Artifact path in the bound manifest")
    params: dict[str, Any] = Field(default_factory=dict)


class Arm(Model):
    arm_id: Id
    role: ArmRole
    components: list[ComponentBinding]
    params: dict[str, Scalar] = Field(default_factory=dict, description="Model-file template parameters for this arm")
    description: str = ""


class Level(Model):
    level_id: Id
    settings: dict[str, Scalar | list[float]] = Field(default_factory=dict)


class Factor(Model):
    factor_id: Id
    levels: list[Level]


class Condition(Model):
    condition_id: Id
    levels: dict[str, str] = Field(default_factory=dict, description="factor_id -> level_id")


class Distribution(Model):
    kind: Literal["normal", "uniform", "choice"]
    mean: float | None = None
    std: float | None = None
    low: float | None = None
    high: float | None = None
    choices: list[Scalar] | None = None


class RandomVariable(Model):
    name: Id
    distribution: Distribution
    bounds: tuple[float, float] | None = Field(None, description="Admissible range; a sample outside it cannot be applied as declared")


class Randomness(Model):
    seed_policy: Literal["fixed", "derived"]
    base_seed: int = Field(ge=0, lt=2**63)
    random_variables: list[RandomVariable] = Field(default_factory=list)


class Comparison(Model):
    comparison_id: Id
    measurement_id: Id | None = None
    arms: list[Id] = Field(default_factory=list)
    counted: bool = True
    unit_of_inference: str | None = None
    pairing: str | None = None
    aggregation: str | None = None
    required_precision: float | None = None


class Design(Model):
    factors: list[Factor] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list, description="Empty with factors: full factorial; empty without: one nominal condition")
    pairing: Literal["none", "paired"] = "none"
    replicates: int = Field(ge=0, le=100000)
    episodes: int = Field(ge=0, le=100000)
    randomness: Randomness
    comparisons: list[Comparison] = Field(default_factory=list)


class Requirement(Model):
    signal: str
    component: int = 0
    op: Literal["<", "<=", ">", ">=", "abs<"]
    value: float


class Step(Model):
    step_id: Id
    duration_s: float = Field(gt=0)
    require: list[Requirement] = Field(default_factory=list, description="Protocol preconditions checked at the step's end")
    description: str = ""


class InitialState(Model):
    keyframe: str | None = None
    qpos: dict[str, float | str | list[float]] = Field(default_factory=dict)
    qvel: dict[str, float | str | list[float]] = Field(default_factory=dict)


class EventDecl(Model):
    event_id: Id
    kind: Literal["contact_begin", "contact_end", "threshold"]
    geoms: list[str] = Field(default_factory=list, description="contact events: one or two geom names")
    signal: str | None = None
    component: int = 0
    value: float | None = None
    direction: Literal["up", "down", "any"] = "any"


class Intervention(Model):
    intervention_id: Id
    at_s: float | str = Field(description="Simulation time, or a template parameter name '${name}'")
    action: Literal["set_qpos", "set_qvel", "add_qvel", "apply_force", "set_ctrl", "set_gravity"]
    target: str = ""
    value: float | str | list[float | str]
    duration_s: float = Field(0.0, ge=0)
    bounds: tuple[float, float] | None = None


class CheckpointPoint(Model):
    checkpoint_point_id: Id
    step_end: Id | None = None
    time_s: float | None = None


class Procedure(Model):
    steps: list[Step]
    initial_state: InitialState = Field(default_factory=InitialState)
    events: list[EventDecl] = Field(default_factory=list)
    interventions: list[Intervention] = Field(default_factory=list)
    checkpoints: list[CheckpointPoint] = Field(default_factory=list)


class MeasurementDefinition(Model):
    kind: Literal[
        # trial scope, standard (independently recomputed)
        "final", "initial", "at_time", "max", "min", "mean", "max_abs", "range", "displacement",
        "first_crossing_time", "period", "fit_acceleration", "decay_rate", "relative_drift",
        "event_time", "event_count", "velocity_ratio_at_event",
        # pair and set scope
        "pair_difference", "pair_ratio", "set_mean", "set_std", "set_min", "set_max", "set_count",
        # component code at the `measurement` extension point (not independently recomputed)
        "component",
    ]
    signal: str | None = None
    component: int = 0
    t: float | None = None
    t_start: float | None = None
    t_end: float | None = None
    level: float | None = None
    direction: Literal["up", "down", "any"] = "any"
    event_id: Id | None = None
    t_end_event: Id | None = Field(None, description="velocity_ratio_at_event: the event that ends the interaction")
    signal_b: str | None = Field(None, description="velocity_ratio_at_event: subtract this signal (relative velocity)")
    window_s: float | None = Field(None, ge=0, description="velocity_ratio_at_event: sample this long before and after")
    of: Id | None = Field(None, description="pair/set scope: the trial measurement aggregated")
    arms: list[Id] = Field(default_factory=list, description="pair scope: [reference arm, compared arm]; set scope: arms included")
    by_condition: bool = True
    artifact: str | None = Field(None, description="component kind: artifact path of the measurement component")


class Measurement(Model):
    measurement_id: Id
    definition: MeasurementDefinition
    scope: MeasurementScope
    unit: str
    signals: list[str] = Field(default_factory=list)
    required: bool = False


class TraceSignal(Model):
    signal: str
    unit: str
    frame: str = "world"
    rate_hz: float | None = Field(None, gt=0, description="None: every step")


class Tolerance(Model):
    abs: float | None = Field(None, ge=0)
    rel: float | None = Field(None, ge=0)


class Variation(Model):
    setting: str = Field(description="'config.<field>' or 'param:<template parameter>'")
    values: list[Scalar]


class CheckDecl(Model):
    check_id: Id
    check_kind: Literal["known_answer", "control_arm", "rerun", "recomputation"]
    required: bool = True
    tolerance: Tolerance | None = Field(None, description="IF-001 §5 A1: comparison tolerance")
    origin: str | None = None
    # known_answer
    measurement_id: Id | None = None
    expected: float | None = None
    arm_id: Id | None = None
    condition_id: Id | None = None
    # control_arm
    arms: list[Id] = Field(default_factory=list)
    # rerun
    samples_per_arm: int = Field(5, ge=1, le=1000)
    variations: list[Variation] = Field(default_factory=list)
    required_precision: dict[str, Tolerance] = Field(default_factory=dict)
    # recomputation
    measurements: list[Id] = Field(default_factory=list, description="Empty: every standard trial measurement")


class Predicate(Model):
    predicate_id: Id
    measurement_id: Id
    op: Literal["<", "<=", ">", ">=", "==", "!="]
    value: float
    origin: str | None = None


class Threshold(Model):
    threshold_id: Id
    value: float
    unit: str = ""
    applies_to: str = ""
    origin: str | None = None


class Watchdog(Model):
    max_speed: float | None = Field(None, gt=0, description="m/s or rad/s on any generalized velocity")
    max_penetration: float | None = Field(None, gt=0, description="m")
    max_energy_growth: float | None = Field(None, gt=0, description="relative to max(|E0|, energy_floor)")
    energy_floor: float = Field(1e-9, gt=0)


class ComponentLimits(Model):
    cpu_s: float = Field(30.0, gt=0)
    memory_mb: int = Field(1536, ge=64)


class Limits(Model):
    max_sim_time_s: float = Field(gt=0)
    max_wall_s: float = Field(gt=0, description="per attempt")
    watchdog: Watchdog = Field(default_factory=Watchdog)
    component: ComponentLimits = Field(default_factory=ComponentLimits)


class Deviation(Model):
    deviation: str
    reason: str
    origin: str


class ParentRef(Model):
    run_id: Id | None = None
    checkpoint_id: Id | None = None


class Experiment(Model):
    record: Literal["simlab-experiment"] = "simlab-experiment"
    schema_version: Literal["simlab-if-001@r1"]
    experiment_id: Id | None = None
    objective: str = Field(min_length=1)
    objective_kind: ObjectiveKind
    declared_stand_ins: list[StandIn] = Field(default_factory=list)
    protocol_items: list[ProtocolItem] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    feasibility: list[FeasibilityEntry] = Field(default_factory=list)
    engines: list[EngineDecl]
    resolved_configuration: ResolvedConfiguration
    assets: AssetsRef | None = None
    arms: list[Arm]
    design: Design
    procedure: Procedure
    measurements: list[Measurement] = Field(default_factory=list)
    probes: list[TraceSignal] = Field(default_factory=list)
    trace_signals: list[TraceSignal] = Field(default_factory=list)
    checks: list[CheckDecl] = Field(default_factory=list)
    predicates: list[Predicate] = Field(default_factory=list)
    thresholds: list[Threshold] = Field(default_factory=list)
    limits: Limits
    deviations: list[Deviation] = Field(default_factory=list)
    parent: ParentRef | None = None


# --------------------------------------------------------------------------- manifest
class ManifestArtifact(Model):
    path: str
    kind: ArtifactKind
    sha256: Sha256
    bytes: int = Field(ge=0)
    extension_point: str | None = None


class ExtensionBinding(Model):
    extension_point: str
    artifact: str


class Manifest(Model):
    record: Literal["simlab-manifest"] = "simlab-manifest"
    schema_version: Literal["simlab-if-001@r1"]
    manifest_id: Id
    manifest_sha256: Sha256
    experiment_id: Id
    artifacts: list[ManifestArtifact]
    extension_bindings: list[ExtensionBinding] = Field(default_factory=list)


# --------------------------------------------------------------------------- result
class Attempt(Model):
    attempt_id: Id
    status: AttemptStatus
    invalid_reason: InvalidReason | None = None
    reason: str = ""
    seeds: dict[str, int] = Field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None
    stop: str | None = Field(None, description="Why the trial stopped: completed, watchdog:<bound>, limit:<limit>, cancel")
    state_digest: Sha256 | None = None


class MeasurementValue(Model):
    measurement_id: str
    value: float | bool | None
    unit: str = ""
    attempt_id: str | None = None
    validity: Literal["valid", "invalid"] = "valid"
    note: str = ""


class Trial(Model):
    trial_id: Id
    arm_id: Id
    condition: Id
    replicate: int
    episode: int
    pair_id: str | None = None
    attempts: list[Attempt]
    measurements: list[MeasurementValue] = Field(default_factory=list)


class CrossTrialMeasurement(Model):
    measurement_id: str
    scope: MeasurementScope
    key: dict[str, Any] = Field(default_factory=dict)
    value: float | None
    unit: str = ""
    n: int = 0
    validity: Literal["valid", "invalid"] = "valid"
    note: str = ""


class CheckResult(Model):
    check_id: str
    check_kind: CheckKind
    required: bool
    status: CheckStatus
    observed: dict[str, Any] = Field(default_factory=dict)
    affected_measurements: list[str] = Field(default_factory=list)


class MeasurementValidity(Model):
    measurement_id: str
    validity: Literal["valid", "invalid"]
    failed_checks: list[str] = Field(default_factory=list)


class CheckpointRef(Model):
    checkpoint_id: Id
    point: str
    trial_id: str
    attempt_id: str
    time_s: float
    state_sha256: Sha256


class TraceRef(Model):
    ref: str
    trial_id: str
    attempt_id: str
    arm_id: str
    signal: str
    unit: str
    n: int
    t_start: float | None
    t_end: float | None
    sha256: Sha256


class CapabilityGap(Model):
    requested_change: str
    reason: str


class Resources(Model):
    wall_s: float
    cpu_s: float
    peak_ram_mb: float
    gpu: str
    peak_vram_mb: float | None
    disk_written_mb: float


class Result(Model):
    record: Literal["simlab-result"] = "simlab-result"
    schema_version: Literal["simlab-if-001@r1"]
    run_id: Id
    experiment_id: Id
    manifest_sha256: Sha256
    run_kind: RunKind
    parent: ParentRef | None = None
    replay_of: Id | None = None
    status: RunStatus
    status_reason: str = ""
    identity: dict[str, Any]
    hardware: dict[str, Any]
    trials: list[Trial]
    cross_trial_measurements: list[CrossTrialMeasurement] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    anchoring: Anchoring
    measurement_validity: list[MeasurementValidity] = Field(default_factory=list)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    checkpoints: list[CheckpointRef] = Field(default_factory=list)
    traces: list[TraceRef] = Field(default_factory=list)
    feasibility: list[FeasibilityEntry] = Field(default_factory=list)
    deviations: list[Deviation] = Field(default_factory=list)
    capability_gaps: list[CapabilityGap] = Field(default_factory=list)
    resources: Resources | None = None
    provenance: dict[str, Any]
    evidence_level: EvidenceLevel | None = Field(None, description="None while no level is earned (run not complete or a required check failed)")
    counts_as_evidence: bool = True


class TypedError(Model):
    code: str
    message: str
    path: str = ""
    severity: Severity = Severity.error


RECORDS: dict[str, type[Model]] = {
    "simlab-experiment": Experiment,
    "simlab-manifest": Manifest,
    "simlab-result": Result,
    "simlab-error": TypedError,
}
