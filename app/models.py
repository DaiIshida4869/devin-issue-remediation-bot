from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from pydantic import Field


class TaskStatus(str, Enum):
    """Lifecycle states of a remediation task."""

    SESSION_CREATED = 'session_created'
    WORKING = 'working'
    BLOCKED = 'blocked'
    COMPLETED = 'completed'
    FAILED = 'failed'


class Issue(BaseModel):
    """A GitHub issue selected for remediation."""

    number: int
    title: str
    body: str = ''
    url: str
    repo: str
    labels: list[str] = Field(default_factory=list)


class Task(BaseModel):
    """A unit of work delegated to Devin and tracked over time."""

    issue_number: int
    issue_url: str
    issue_title: str
    status: TaskStatus = TaskStatus.SESSION_CREATED
    devin_session_id: str = ''
    devin_session_url: str = ''
    pr_url: str = ''
    created_at: str = ''
    updated_at: str = ''
    notes: str = ''


# Devin v3 status_detail values that mean the session is waiting on a human.
_BLOCKED_DETAILS: set[str] = {
    'waiting_for_user',
    'waiting_for_approval',
}


def is_session_finished(status: str | None, status_detail: str | None) -> bool:
    """Return True when a v3 session has completed its task.

    Devin can report ``finished`` while the coarse ``status`` is still
    ``running`` (task done, VM not yet torn down) or once it has reached
    ``exit``. Either case means the remediation attempt is over.
    """
    return status_detail == 'finished' and status in ('running', 'exit')


def map_devin_status(status: str | None, status_detail: str | None) -> TaskStatus:
    """Translate a Devin v3 session status into a TaskStatus.

    v3 exposes a coarse ``status`` plus a finer ``status_detail``. We collapse
    both onto our own lifecycle, defaulting to WORKING for anything unexpected.
    """
    if status in ('new', 'claimed'):
        return TaskStatus.SESSION_CREATED
    if is_session_finished(status, status_detail):
        return TaskStatus.COMPLETED
    if status == 'suspended':
        return TaskStatus.BLOCKED
    if status in ('running', 'resuming'):
        if status_detail in _BLOCKED_DETAILS:
            return TaskStatus.BLOCKED
        return TaskStatus.WORKING
    if status == 'exit':
        return TaskStatus.FAILED
    if status == 'error':
        return TaskStatus.FAILED
    return TaskStatus.WORKING
