"""Tests for Markdown report generation."""

from __future__ import annotations

from app.models import Task
from app.models import TaskStatus
from app.report import render_report


def _task(issue_number: int, status: TaskStatus, pr_url: str = '') -> Task:
    """Build a task for report tests."""
    return Task(
        issue_number=issue_number,
        issue_url=f'https://github.com/example/superset/issues/{issue_number}',
        issue_title=f'Issue {issue_number}',
        status=status,
        devin_session_id='devin-abc',
        pr_url=pr_url,
    )


def test_render_report_should_show_zero_total_when_empty() -> None:
    report = render_report([])

    assert 'Total tasks: 0' in report
    assert 'No tasks yet' in report


def test_render_report_should_include_a_row_per_task() -> None:
    tasks = [
        _task(1, TaskStatus.COMPLETED, pr_url='https://github.com/example/superset/pull/4'),
        _task(2, TaskStatus.SESSION_CREATED),
    ]

    report = render_report(tasks)

    assert '| #1 |' in report
    assert '| #2 |' in report
    assert 'pull/4' in report
    assert 'Total tasks: 2' in report


def test_render_report_should_escape_pipe_in_title() -> None:
    task = Task(
        issue_number=1,
        issue_url='https://github.com/example/superset/issues/1',
        issue_title='Fix a|b parsing',
        status=TaskStatus.WORKING,
    )

    report = render_report([task])

    assert 'Fix a\\|b parsing' in report


def test_render_report_should_summarize_status_counts() -> None:
    tasks = [
        _task(1, TaskStatus.COMPLETED),
        _task(2, TaskStatus.COMPLETED),
        _task(3, TaskStatus.FAILED),
    ]

    report = render_report(tasks)

    assert 'Completed: 2' in report
    assert 'Failed: 1' in report
