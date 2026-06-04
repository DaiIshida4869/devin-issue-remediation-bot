"""Tests for the JSON-backed task store."""

from __future__ import annotations

from app.models import Task
from app.models import TaskStatus
from app.task_store import TaskStore


def _make_task(issue_number: int, status: TaskStatus = TaskStatus.SESSION_CREATED) -> Task:
    """Build a minimal task for store tests."""
    return Task(
        issue_number=issue_number,
        issue_url=f'https://github.com/example/superset/issues/{issue_number}',
        issue_title=f'Issue {issue_number}',
        status=status,
    )


def test_load_should_return_empty_list_when_file_absent(tmp_path) -> None:
    store = TaskStore(tmp_path / 'tasks.json')

    assert store.load() == []


def test_save_then_load_should_round_trip(tmp_path) -> None:
    store = TaskStore(tmp_path / 'tasks.json')
    tasks = [_make_task(1), _make_task(2)]

    store.save(tasks)
    loaded = store.load()

    assert [task.issue_number for task in loaded] == [1, 2]


def test_upsert_should_replace_existing_task_by_issue_number(tmp_path) -> None:
    store = TaskStore(tmp_path / 'tasks.json')
    store.save([_make_task(1, TaskStatus.SESSION_CREATED)])

    store.upsert(_make_task(1, TaskStatus.COMPLETED))
    loaded = store.load()

    assert len(loaded) == 1
    assert loaded[0].status == TaskStatus.COMPLETED


def test_upsert_should_keep_tasks_sorted_by_issue_number(tmp_path) -> None:
    store = TaskStore(tmp_path / 'tasks.json')

    store.upsert(_make_task(3))
    store.upsert(_make_task(1))
    store.upsert(_make_task(2))

    assert [task.issue_number for task in store.load()] == [1, 2, 3]
