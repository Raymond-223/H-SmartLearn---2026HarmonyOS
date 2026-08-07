"""Workflow state machine transitions."""

from enum import Enum


class WorkflowStatus(str, Enum):
    CREATED = "CREATED"
    PROFILE_READY = "PROFILE_READY"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    DIAGNOSING = "DIAGNOSING"
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
    WorkflowStatus.DIAGNOSING: {WorkflowStatus.PATH_PLANNING},
    WorkflowStatus.PATH_PLANNING: {WorkflowStatus.RETRIEVING},
    WorkflowStatus.RETRIEVING: {WorkflowStatus.GENERATING},
    WorkflowStatus.GENERATING: {WorkflowStatus.REVIEWING},
    WorkflowStatus.REVIEWING: {WorkflowStatus.PUBLISHED, WorkflowStatus.REVISING, WorkflowStatus.FAILED},
    WorkflowStatus.REVISING: {WorkflowStatus.REVIEWING},
    WorkflowStatus.PUBLISHED: set(),
    WorkflowStatus.FAILED: set(),
}


def validate_transition(current: WorkflowStatus, next_state: WorkflowStatus) -> bool:
    """Check if a state transition is valid."""
    allowed = TRANSITIONS.get(current, set())
    return next_state in allowed
