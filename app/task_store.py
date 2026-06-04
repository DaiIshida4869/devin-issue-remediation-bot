from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path

from app.models import Task


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TaskStore:
    """Loads and saves tasks to a JSON file keyed by issue number."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[Task]:
        """Read all tasks from disk, returning an empty list when absent."""
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding='utf-8'))
        tasks: list[Task] = []
        for item in payload.get('tasks', []):
            tasks.append(Task.model_validate(item))
        return tasks

    def save(self, tasks: list[Task]) -> None:
        """Persist the full task list to disk, creating parent dirs as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized: list[dict] = []
        for task in tasks:
            serialized.append(task.model_dump())
        payload = {'tasks': serialized}
        self._path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')

    def upsert(self, task: Task) -> list[Task]:
        """Insert or replace a task by issue number and persist the result."""
        # The demo tracks a single repo, so the issue number is a sufficient key.
        tasks = self.load()
        merged: list[Task] = []
        for existing in tasks:
            if existing.issue_number != task.issue_number:
                merged.append(existing)
        merged.append(task)
        merged.sort(key=lambda item: item.issue_number)
        self.save(merged)
        return merged
