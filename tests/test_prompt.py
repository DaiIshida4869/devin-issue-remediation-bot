"""Tests for Devin prompt construction."""

from __future__ import annotations

from app.models import Issue
from app.prompt import build_remediation_prompt
from app.prompt import build_session_title


def test_build_remediation_prompt_should_include_issue_and_repo(sample_issue: Issue) -> None:
    prompt = build_remediation_prompt(sample_issue)

    assert sample_issue.url in prompt
    assert 'https://github.com/example/superset' in prompt
    assert sample_issue.title in prompt
    assert 'smallest safe change' in prompt


def test_build_remediation_prompt_should_handle_empty_body() -> None:
    issue = Issue(number=3, title='Empty', body='   ', url='u', repo='example/superset')

    prompt = build_remediation_prompt(issue)

    assert '(no description provided)' in prompt


def test_build_session_title_should_include_number_and_title(sample_issue: Issue) -> None:
    title = build_session_title(sample_issue)

    assert title == 'Remediate #1: Improve developer setup documentation clarity'
