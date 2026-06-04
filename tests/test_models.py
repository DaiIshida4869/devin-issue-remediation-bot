"""Tests for domain model helpers."""

from __future__ import annotations

import pytest

from app.models import TaskStatus
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
        ('exit', 'finished', TaskStatus.COMPLETED),
        # Devin can report finished while the VM is still running.
        ('running', 'finished', TaskStatus.COMPLETED),
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
