"""Status and enum strings fixed by SIMLAB-IF-001@r1 (PAS-M1-001 TASK §4).

These strings are canonical for every consumer. Do not add values without a
TASK §5 change entry.
"""
from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class ObjectiveKind(StrEnum):
    claim_test = "claim_test"
    assumption_test = "assumption_test"
    mechanism = "mechanism"
    design_comparison = "design_comparison"
    robustness = "robustness"
    follow_up = "follow_up"
    exploration = "exploration"


class ArmRole(StrEnum):
    baseline = "baseline"
    treatment = "treatment"
    control = "control"
    reference = "reference"
    other = "other"


class FeasibilityStatus(StrEnum):
    inspected = "inspected"
    missing = "missing"
    unverified = "unverified"
    needs_calibration = "needs_calibration"
    ran = "ran"


class RunKind(StrEnum):
    original = "original"
    replay = "replay"
    fresh_replication = "fresh_replication"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"  # infrastructure failure only, never a science outcome
    PAUSED = "PAUSED"  # phase 4 (PAS-M1-013)


TERMINAL_RUN = {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED}


class AttemptStatus(StrEnum):
    RUNNING = "RUNNING"  # store-internal while an attempt executes; never terminal
    COMPLETED = "COMPLETED"
    INVALID = "INVALID"
    LIMIT_REACHED = "LIMIT_REACHED"
    INTERRUPTED = "INTERRUPTED"
    BLOCKED = "BLOCKED"


class InvalidReason(StrEnum):
    numerical_failure = "numerical_failure"
    protocol_violation = "protocol_violation"
    incorrect_intervention = "incorrect_intervention"
    missing_required_observation = "missing_required_observation"
    corrupted_record = "corrupted_record"
    invalid_state_or_action_delivery = "invalid_state_or_action_delivery"


class CheckKind(StrEnum):
    known_answer = "known_answer"
    control_arm = "control_arm"
    rerun = "rerun"
    recomputation = "recomputation"
    watchdog = "watchdog"
    replay_identity = "replay_identity"


class CheckStatus(StrEnum):
    pass_ = "pass"
    fail = "fail"
    not_run = "not_run"


class Anchoring(StrEnum):
    anchored = "anchored"
    unanchored = "unanchored"


class EvidenceLevel(StrEnum):
    preview = "preview"
    simulation = "simulation"
    measured = "measured"
    validated_range = "validated_range"


class MeasurementScope(StrEnum):
    trial = "trial"
    pair = "pair"
    set = "set"


class CapabilityStatus(StrEnum):
    admitted = "admitted"
    supported = "supported"
    excluded = "excluded"
    missing = "missing"


class Severity(StrEnum):
    error = "error"
    warning = "warning"


class ArtifactKind(StrEnum):
    geometry = "geometry"
    collision = "collision"
    model_file = "model_file"
    procedure = "procedure"
    intervention = "intervention"
    measurement = "measurement"
    observation = "observation"
    component = "component"
