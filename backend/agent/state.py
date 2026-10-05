"""Task state machine."""

from enum import StrEnum


class TaskState(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.PLANNING, TaskState.CANCELLED},
    TaskState.PLANNING: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.RUNNING: {
        TaskState.WAITING_FOR_APPROVAL,
        TaskState.WAITING_FOR_INPUT,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.WAITING_FOR_APPROVAL: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.WAITING_FOR_INPUT: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


def validate_transition(current: TaskState, target: TaskState) -> None:
    if target not in TRANSITIONS[current]:
        raise ValueError(f"Illegal task transition: {current} -> {target}")

