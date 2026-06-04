from __future__ import annotations

from collections import Counter

from app.models import Task
from app.models import TaskStatus

_STATUS_LABELS: dict[TaskStatus, str] = {
    TaskStatus.SESSION_CREATED: 'Session Created',
    TaskStatus.WORKING: 'Working',
    TaskStatus.BLOCKED: 'Blocked',
    TaskStatus.COMPLETED: 'Completed',
    TaskStatus.FAILED: 'Failed',
}


def _status_label(status: TaskStatus) -> str:
    return _STATUS_LABELS.get(status, status.value)


def _md_cell(value: str) -> str:
    """Escape pipe and newline characters so they do not break the table layout."""
    return value.replace('|', '\\|').replace('\n', ' ')


def _summary_line(tasks: list[Task]) -> str:
    counts: Counter[TaskStatus] = Counter()
    for task in tasks:
        counts[task.status] += 1
    parts: list[str] = []
    for status in TaskStatus:
        if counts[status] > 0:
            parts.append(f'{_status_label(status)}: {counts[status]}')
    if not parts:
        return 'No tasks yet'
    return ' | '.join(parts)


def render_report(tasks: list[Task]) -> str:
    lines: list[str] = []
    lines.append('# Devin Remediation Report')
    lines.append('')
    lines.append(f'Total tasks: {len(tasks)}')
    lines.append('')
    lines.append(f'Status summary: {_summary_line(tasks)}')
    lines.append('')
    lines.append('| Issue | Title | Status | Devin Session | PR | Notes |')
    lines.append('|---|---|---|---|---|---|')
    for task in tasks:
        session = task.devin_session_url or task.devin_session_id or '-'
        pr = task.pr_url or '-'
        if task.notes:
            notes = _md_cell(task.notes)
        else:
            notes = '-'
        title = _md_cell(task.issue_title)
        lines.append(
            f'| #{task.issue_number} | {title} | {_status_label(task.status)} '
            f'| {session} | {pr} | {notes} |'
        )
    lines.append('')
    return '\n'.join(lines)
