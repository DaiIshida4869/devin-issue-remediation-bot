"""Tests for domain model helpers."""

from __future__ import annotations

import pytest

from app.models import TaskStatus
from app.models import classify_task_status
from app.models import map_devin_status


@pytest.mark.parametrize(
    ('status', 'status_detail', 'expected'),
    [
        ('new', None, TaskStatus.SESSION_CREATED),
        ('claimed', None, TaskStatus.SESSION_CREATED),
        ('running', 'working', TaskStatus.WORKING),
        ('resuming', None, TaskStatus.WORKING),
        ('running', 'waiting_for_user', TaskStatus.BLOCKED),
        ('running', 'waiting_for_approval', TaskStatus.BLOCKED),
        ('suspended', None, TaskStatus.BLOCKED),
        # Completion is keyed off the PR (in the orchestrator), not the session
        # status, so an ended session with no PR maps to FAILED here.
        ('exit', 'finished', TaskStatus.FAILED),
        ('exit', 'usage_limit_exceeded', TaskStatus.FAILED),
        ('error', None, TaskStatus.FAILED),
    ],
)
def test_map_devin_status_should_map_known_values(
    status: str, status_detail: str | None, expected: TaskStatus
) -> None:
    assert map_devin_status(status, status_detail) == expected


def test_map_devin_status_should_default_to_working_for_none() -> None:
    assert map_devin_status(None, None) == TaskStatus.WORKING


def test_map_devin_status_should_default_to_working_for_unknown() -> None:
    assert map_devin_status('some_future_state', None) == TaskStatus.WORKING


def test_classify_task_status_should_be_completed_when_pr_present() -> None:
    # A PR is the success signal even while the session waits on a human.
    assert classify_task_status('running', 'waiting_for_user', has_pr=True) == TaskStatus.COMPLETED


def test_classify_task_status_should_fall_back_to_session_status_without_pr() -> None:
    assert classify_task_status('running', 'working', has_pr=False) == TaskStatus.WORKING
    assert classify_task_status('exit', None, has_pr=False) == TaskStatus.FAILED
