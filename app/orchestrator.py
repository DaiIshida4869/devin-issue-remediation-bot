from __future__ import annotations

from collections.abc import Callable

import requests

from app.devin_client import DevinClient
from app.models import Issue
from app.models import Task
from app.models import TaskStatus
from app.models import is_session_finished
from app.models import map_devin_status
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

    def _refresh_task(self, task: Task) -> None:
        """Update a single task in place from its Devin session status."""
        status = self._devin.get_session(task.devin_session_id)
        if status.pr_url:
            task.pr_url = status.pr_url
        # The workflow's goal is a PR, so finishing without one is a failure to surface.
        if is_session_finished(status.status, status.status_detail) and not task.pr_url:
            task.status = TaskStatus.FAILED
            task.notes = 'Devin finished without creating a pull request'
        else:
            task.status = map_devin_status(status.status, status.status_detail)
            task.notes = f'Devin status: {status.status or "unknown"}'
        task.updated_at = self._now()

    def _write_report(self) -> None:
        report = render_report(self._store.load())
        self._report_path.write_text(report, encoding='utf-8')
