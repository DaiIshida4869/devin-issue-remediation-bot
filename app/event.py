from __future__ import annotations

import json
from pathlib import Path

from app.models import Issue


class EventParseError(ValueError):
    """Raised when an event payload cannot be parsed into an Issue."""


def parse_issue_event(payload: dict) -> Issue:
    """Extract an Issue from a GitHub `issues` webhook payload."""
    issue = payload.get('issue')
    if not isinstance(issue, dict):
        raise EventParseError('payload is missing an "issue" object')

    repository = payload.get('repository') or {}
    repo = repository.get('full_name', '')
    labels: list[str] = []
    for label in issue.get('labels', []):
        labels.append(label['name'])

    return Issue(
        number=issue['number'],
        title=issue['title'],
        body=issue.get('body') or '',
        url=issue['html_url'],
        repo=repo,
        labels=labels,
    )


def load_issue_event(path: str | Path) -> Issue:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    return parse_issue_event(payload)


def has_trigger_label(issue: Issue, trigger_label: str) -> bool:
    return trigger_label in issue.labels
