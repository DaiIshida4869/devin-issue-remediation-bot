"""Tests for the orchestrator coordinating Devin, storage, and reporting."""

from __future__ import annotations

from collections.abc import Callable

import requests
from pytest_mock import MockerFixture

from app.devin_client import DevinClient
from app.devin_client import DevinSession
from app.devin_client import DevinSessionStatus
from app.devin_client import DevinSessionSummary
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


def test_poll_should_complete_when_pr_present_even_while_awaiting_user(
    tmp_path, mocker: MockerFixture, sample_issue: Issue, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.create_session.return_value = DevinSession(session_id='devin-abc', url='')
    # Devin opened a PR but the session lingers in waiting_for_user ("awaiting instructions").
    devin.get_session.return_value = DevinSessionStatus(
        status='running',
        status_detail='waiting_for_user',
        pr_url='https://github.com/example/superset/pull/8',
        raw={},
    )
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)
    orchestrator.remediate_issue(sample_issue)

    tasks = orchestrator.poll()

    assert tasks[0].status == TaskStatus.COMPLETED
    assert tasks[0].pr_url == 'https://github.com/example/superset/pull/8'


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


def test_sync_from_devin_should_rebuild_report_from_matching_sessions(
    tmp_path, mocker: MockerFixture, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    devin.list_sessions.return_value = [
        DevinSessionSummary(
            session_id='s7',
            url='https://app.devin.ai/sessions/s7',
            title='Remediate #7: Clarify docs',
            status='running',
            status_detail='waiting_for_user',
            pr_url='https://github.com/example/superset/pull/8',
        ),
        # A session that is not ours (no "Remediate #" title) is ignored.
        DevinSessionSummary(
            session_id='sx', url='u', title='Add test coverage', status='running', status_detail='working', pr_url=''
        ),
    ]
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)

    tasks = orchestrator.sync_from_devin()

    assert len(tasks) == 1
    assert tasks[0].issue_number == 7
    assert tasks[0].issue_title == 'Clarify docs'
    # A delivered PR marks the task completed even while the session awaits the user.
    assert tasks[0].status == TaskStatus.COMPLETED
    report = (tmp_path / 'report.md').read_text(encoding='utf-8')
    assert '| #7 |' in report


def test_sync_from_devin_should_keep_one_task_per_issue(
    tmp_path, mocker: MockerFixture, fixed_clock: Callable[[], str]
) -> None:
    devin = mocker.Mock(spec=DevinClient)
    # Returned out of order; sync should keep the one with the newest created_at.
    devin.list_sessions.return_value = [
        DevinSessionSummary(
            session_id='older',
            url='u',
            title='Remediate #7: x',
            status='exit',
            status_detail='finished',
            pr_url='pr',
            created_at=100,
        ),
        DevinSessionSummary(
            session_id='newest',
            url='u',
            title='Remediate #7: x',
            status='running',
            status_detail='working',
            pr_url='',
            created_at=200,
        ),
    ]
    orchestrator = _orchestrator(tmp_path, devin, fixed_clock)

    tasks = orchestrator.sync_from_devin()

    assert len(tasks) == 1
    assert tasks[0].devin_session_id == 'newest'


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
