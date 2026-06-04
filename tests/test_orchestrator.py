"""Tests for the orchestrator coordinating Devin, storage, and reporting."""

from __future__ import annotations

from collections.abc import Callable

import requests
from pytest_mock import MockerFixture

from app.devin_client import DevinClient
from app.devin_client import DevinSession
from app.devin_client import DevinSessionStatus
from app.models import Issue
from app.models import TaskStatus
from app.orchestrator import Orchestrator
from app.task_store import TaskStore


def _orchestrator(tmp_path, devin: DevinClient, clock: Callable[[], str]) -> Orchestrator:
    """Build an orchestrator backed by a temp store and report file."""
    store = TaskStore(tmp_path / 'tasks.json')
    return Orchestrator(devin=devin, store=store, report_path=tmp_path / 'report.md', now=clock)


def test_remediate_issue_should_create_session_and_store_task(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(
        session_id='devin-abc', url='https://app.devin.ai/sessions/abc'
    )
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)

    task = orchestrator.remediate_issue(sample_issue)

    assert task.status == TaskStatus.SESSION_CREATED
    assert task.devin_session_id == 'devin-abc'
    assert task.created_at == '2026-06-03T10:00:00+00:00'
    devin.create_session.assert_called_once()


def test_remediate_issue_should_write_report_file(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)

    orchestrator.remediate_issue(sample_issue)

    report = (tmp_path / 'report.md').read_text(encoding='utf-8')
    assert '# Devin Remediation Report' in report
    assert '| #1 |' in report


def test_poll_should_update_status_and_pr_for_active_tasks(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    devin.get_session.return_value = DevinSessionStatus(
        status='exit', status_detail='finished', pr_url='https://github.com/example/superset/pull/4', raw={}
    )
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)

    tasks = orchestrator.poll()

    assert tasks[0].status == TaskStatus.COMPLETED
    assert tasks[0].pr_url == 'https://github.com/example/superset/pull/4'


def test_poll_should_complete_when_finished_while_still_running(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    # Devin can report status_detail 'finished' while the coarse status is still 'running'.
    devin.get_session.return_value = DevinSessionStatus(
        status='running', status_detail='finished', pr_url='https://github.com/example/superset/pull/7', raw={}
    )
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)

    tasks = orchestrator.poll()

    assert tasks[0].status == TaskStatus.COMPLETED
    assert tasks[0].pr_url == 'https://github.com/example/superset/pull/7'


def test_poll_should_mark_finished_without_pr_as_failed(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    devin.get_session.return_value = DevinSessionStatus(status='exit', status_detail='finished', pr_url='', raw={})
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)

    tasks = orchestrator.poll()

    assert tasks[0].status == TaskStatus.FAILED
    assert 'without creating a pull request' in tasks[0].notes


def test_poll_should_record_error_and_continue_on_request_exception(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    devin.get_session.side_effect = requests.ConnectionError('boom')
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)

    tasks = orchestrator.poll()

    assert tasks[0].status == TaskStatus.SESSION_CREATED
    assert 'Failed to poll Devin' in tasks[0].notes


def test_poll_should_skip_completed_tasks(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    devin.get_session.return_value = DevinSessionStatus(status='exit', status_detail='finished', pr_url='', raw={})
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)
    orchestrator.poll()

    orchestrator.poll()

    assert devin.get_session.call_count == 1
