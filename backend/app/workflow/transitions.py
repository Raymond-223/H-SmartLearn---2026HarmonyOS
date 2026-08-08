"""Workflow state machine transitions."""

from enum import Enum


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    PROFILE_READY = "PROFILE_READY"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    DIAGNOSING = "DIAGNOSING"
    # Adaptive diagnosis sub-states: one question at a time, each answer folded
    # into the Beta posterior before the next item is chosen. A workflow that
    # arrives with a diagnosis already completed (via the /diagnosis API) skips
    # straight from DIAGNOSING to PATH_PLANNING.
    DIAGNOSIS_QUESTIONING = "DIAGNOSIS_QUESTIONING"
    LEARNER_MODEL_UPDATING = "LEARNER_MODEL_UPDATING"
    DIAGNOSIS_COMPLETED = "DIAGNOSIS_COMPLETED"
    PATH_PLANNING = "PATH_PLANNING"
    RETRIEVING = "RETRIEVING"
    GENERATING = "GENERATING"
    REVIEWING = "REVIEWING"
    REVISING = "REVISING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


# Valid state transitions
TRANSITIONS = {
    WorkflowStatus.CREATED: {WorkflowStatus.PROFILE_READY},
    WorkflowStatus.PROFILE_READY: {WorkflowStatus.ASSESSMENT_COMPLETED},
    WorkflowStatus.ASSESSMENT_COMPLETED: {WorkflowStatus.DIAGNOSING},
    WorkflowStatus.DIAGNOSING: {
        WorkflowStatus.DIAGNOSIS_QUESTIONING,
        WorkflowStatus.PATH_PLANNING,
    },
    # Ask -> score -> either ask again or finish. The self-loop between these two
    # is what makes the number of questions adaptive rather than fixed.
    # DIAGNOSIS_COMPLETED is reachable straight from questioning too: a session can
    # end with a question still pending (bank exhausted, time budget spent), and no
    # model update happens on that path.
    WorkflowStatus.DIAGNOSIS_QUESTIONING: {
        WorkflowStatus.LEARNER_MODEL_UPDATING,
        WorkflowStatus.DIAGNOSIS_COMPLETED,
    },
    WorkflowStatus.LEARNER_MODEL_UPDATING: {
        WorkflowStatus.DIAGNOSIS_QUESTIONING,
        WorkflowStatus.DIAGNOSIS_COMPLETED,
    },
    WorkflowStatus.DIAGNOSIS_COMPLETED: {WorkflowStatus.PATH_PLANNING},
    WorkflowStatus.PATH_PLANNING: {WorkflowStatus.RETRIEVING},
    WorkflowStatus.RETRIEVING: {WorkflowStatus.GENERATING},
    WorkflowStatus.GENERATING: {WorkflowStatus.REVIEWING},
    WorkflowStatus.REVIEWING: {WorkflowStatus.PUBLISHED, WorkflowStatus.REVISING, WorkflowStatus.FAILED},
    WorkflowStatus.REVISING: {WorkflowStatus.REVIEWING},
    WorkflowStatus.PUBLISHED: set(),
    WorkflowStatus.FAILED: set(),
}


# Any non-terminal state may fail.
for _state, _allowed in TRANSITIONS.items():
    if _allowed:
        _allowed.add(WorkflowStatus.FAILED)


def validate_transition(current: WorkflowStatus, next_state: WorkflowStatus) -> bool:
    """Check if a state transition is valid."""
    allowed = TRANSITIONS.get(current, set())
    return next_state in allowed
