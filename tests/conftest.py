"""Shared fixtures for the test suite."""

from __future__ import annotations

import pytest

from app.models import Issue


@pytest.fixture
def sample_issue() -> Issue:
    """A representative issue carrying the trigger label."""
    return Issue(
        number=1,
        title='Improve developer setup documentation clarity',
        body='Clarify the prerequisites and add a troubleshooting note.',
        url='https://github.com/example/superset/issues/1',
        repo='example/superset',
        labels=['documentation', 'devin-remediate'],
    )


@pytest.fixture
def fixed_clock() -> object:
    """A deterministic clock returning a constant ISO timestamp."""

    def _now() -> str:
        return '2026-06-03T10:00:00+00:00'

    return _now
