"""Tests for GitHub issue event parsing."""

from __future__ import annotations

import json

import pytest

from app.event import EventParseError
from app.event import has_trigger_label
from app.event import load_issue_event
from app.event import parse_issue_event
from app.models import Issue


def test_parse_issue_event_should_extract_issue_fields() -> None:
    payload = {
        'action': 'labeled',
        'issue': {
            'number': 7,
            'title': 'Fix typo',
            'html_url': 'https://github.com/example/superset/issues/7',
            'body': 'A small typo.',
            'labels': [{'name': 'devin-remediate'}],
        },
        'repository': {'full_name': 'example/superset'},
    }

    issue = parse_issue_event(payload)

    assert issue.number == 7
    assert issue.title == 'Fix typo'
    assert issue.repo == 'example/superset'
    assert issue.labels == ['devin-remediate']


def test_parse_issue_event_should_default_missing_body_to_empty() -> None:
    payload = {
        'issue': {
            'number': 1,
            'title': 'No body',
            'html_url': 'https://github.com/example/superset/issues/1',
            'body': None,
            'labels': [],
        },
        'repository': {'full_name': 'example/superset'},
    }

    issue = parse_issue_event(payload)

    assert issue.body == ''
    assert issue.labels == []


def test_parse_issue_event_should_raise_when_issue_missing() -> None:
    with pytest.raises(EventParseError):
        parse_issue_event({'action': 'labeled'})


def test_load_issue_event_should_read_from_file(tmp_path) -> None:
    payload = {
        'issue': {
            'number': 2,
            'title': 'From file',
            'html_url': 'https://github.com/example/superset/issues/2',
            'body': 'body',
            'labels': [],
        },
        'repository': {'full_name': 'example/superset'},
    }
    event_path = tmp_path / 'event.json'
    event_path.write_text(json.dumps(payload), encoding='utf-8')

    issue = load_issue_event(event_path)

    assert issue.number == 2


def test_has_trigger_label_should_be_true_when_present() -> None:
    issue = Issue(number=1, title='t', url='u', repo='r', labels=['devin-remediate'])

    assert has_trigger_label(issue, 'devin-remediate') is True


def test_has_trigger_label_should_be_false_when_absent() -> None:
    issue = Issue(number=1, title='t', url='u', repo='r', labels=['documentation'])

    assert has_trigger_label(issue, 'devin-remediate') is False
