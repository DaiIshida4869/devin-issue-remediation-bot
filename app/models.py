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


def map_devin_status(status: str | None, status_detail: str | None) -> TaskStatus:
    """Translate a Devin v3 session status into a TaskStatus.

    Completion is decided by the orchestrator from the presence of a pull
    request, not here: a Devin session commonly lingers in ``waiting_for_user``
    ("awaiting instructions") long after the work is done, so the session status
    alone cannot tell us the task succeeded. This maps the pre-PR lifecycle.
    """
    if status in ('new', 'claimed'):
        return TaskStatus.SESSION_CREATED
    if status == 'suspended':
        return TaskStatus.BLOCKED
    if status in ('running', 'resuming'):
        if status_detail in _BLOCKED_DETAILS:
            return TaskStatus.BLOCKED
        return TaskStatus.WORKING
    if status in ('exit', 'error'):
        return TaskStatus.FAILED
    return TaskStatus.WORKING
