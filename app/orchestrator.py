from __future__ import annotations

import re
from collections.abc import Callable

import requests

from app.devin_client import DevinClient
from app.devin_client import DevinSessionSummary
from app.models import Issue
from app.models import Task
from app.models import TaskStatus
from app.models import classify_task_status
from app.prompt import build_remediation_prompt
from app.prompt import build_session_title
from app.report import render_report
from app.task_store import TaskStore
from app.task_store import utc_now_iso

# Task states that are still in progress and worth polling.
_ACTIVE_STATUSES: set[TaskStatus] = {
    TaskStatus.SESSION_CREATED,
    TaskStatus.WORKING,
    TaskStatus.BLOCKED,
}


class Orchestrator:
    """Delegates issues to Devin and tracks their progress."""

    def __init__(
        self,
        devin: DevinClient,
        store: TaskStore,
        report_path,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._devin = devin
        self._store = store
        self._report_path = report_path
        self._now = now

    def remediate_issue(self, issue: Issue) -> Task:
        """Create a Devin session for an issue and record it as a task."""
        prompt = build_remediation_prompt(issue)
        title = build_session_title(issue)
        session = self._devin.create_session(prompt=prompt, title=title)
        timestamp = self._now()
        task = Task(
            issue_number=issue.number,
            issue_url=issue.url,
            issue_title=issue.title,
            status=TaskStatus.SESSION_CREATED,
            devin_session_id=session.session_id,
            devin_session_url=session.url,
            created_at=timestamp,
            updated_at=timestamp,
            notes='Delegated to Devin',
        )
        self._store.upsert(task)
        self._write_report()
        return task

    def poll(self) -> list[Task]:
        """Refresh active tasks from Devin and regenerate the report."""
        tasks = self._store.load()
        for task in tasks:
            if task.status not in _ACTIVE_STATUSES or not task.devin_session_id:
                continue
            try:
                self._refresh_task(task)
            except requests.RequestException as exc:
                # Keep polling the remaining tasks even if one session lookup fails.
                task.notes = f'Failed to poll Devin: {exc}'
                task.updated_at = self._now()
        self._store.save(tasks)
        self._write_report()
        return tasks

    def sync_from_devin(self) -> list[Task]:
        """Rebuild the report from the bot's Devin sessions, then persist it.

        Unlike poll(), this needs no local tasks.json: it discovers the bot's
        sessions from Devin (recognized by their ``Remediate #<n>:`` title) and
        treats Devin as the source of truth. This is what the scheduled report
        workflow runs, so the published report stays current without local state.
        """
        now = self._now()
        seen: set[int] = set()
        tasks: list[Task] = []
        for summary in self._devin.list_sessions():
            task = _task_from_session(summary, now)
            if task is None:
                continue
            # The newest session per issue wins (the list is newest-first).
            if task.issue_number in seen:
                continue
            seen.add(task.issue_number)
            tasks.append(task)
        tasks.sort(key=lambda item: item.issue_number)
        self._store.save(tasks)
        self._write_report()
        return tasks

    def _refresh_task(self, task: Task) -> None:
        """Update a single task in place from its Devin session status."""
        status = self._devin.get_session(task.devin_session_id)
        if status.pr_url:
            task.pr_url = status.pr_url
        task.status = classify_task_status(status.status, status.status_detail, bool(task.pr_url))
        task.notes = _status_note(task.status, task.pr_url, status.status)
        task.updated_at = self._now()

    def _write_report(self) -> None:
        report = render_report(self._store.load())
        self._report_path.write_text(report, encoding='utf-8')


# Sessions opened by this bot are titled "Remediate #<n>: <issue title>".
_SESSION_TITLE_RE = re.compile(r'^Remediate #(\d+): (.*)$')


def _status_note(status: TaskStatus, pr_url: str, devin_status: str | None) -> str:
    """Build a human-readable note explaining a task's current status."""
    if status == TaskStatus.COMPLETED:
        return f'Devin opened a pull request: {pr_url}'
    if status == TaskStatus.FAILED:
        return 'Devin ended without creating a pull request'
    return f'Devin status: {devin_status or "unknown"}'


def _task_from_session(summary: DevinSessionSummary, now: str) -> Task | None:
    """Reconstruct a Task from a Devin session, or None if it is not ours."""
    if summary.title is None:
        return None
    match = _SESSION_TITLE_RE.match(summary.title)
    if match is None:
        return None
    status = classify_task_status(summary.status, summary.status_detail, bool(summary.pr_url))
    return Task(
        issue_number=int(match.group(1)),
        issue_url='',
        issue_title=match.group(2),
        status=status,
        devin_session_id=summary.session_id,
        devin_session_url=summary.url,
        pr_url=summary.pr_url,
        updated_at=now,
        notes=_status_note(status, summary.pr_url, summary.status),
    )
