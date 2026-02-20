"""
TasksClient — typed, high-level wrapper around the Google Tasks API v1.

Supports listing task lists, reading tasks, creating tasks with due dates,
completing tasks, and managing task list containers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .google_factory import GoogleServiceFactory
from .models import Task, TaskList

logger = logging.getLogger(__name__)

_DEFAULT_TASKLIST = "@default"


def _parse_rfc3339(s: str) -> Optional[datetime]:
    """Parse an RFC 3339 datetime string to a UTC-aware datetime, or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class TasksClient:
    """
    High-level Google Tasks operations.

    Google Tasks has two levels:
      - TaskList: a named container (e.g. "Work", "Personal")
      - Task: an item inside a list (with optional due date, notes, subtasks)

    Usage:
        factory = GoogleServiceFactory()
        tasks   = TasksClient(factory)

        lists = tasks.list_task_lists()
        items = tasks.get_tasks(include_completed=False)
        task_id = tasks.create_task("Review contract", due=datetime(2026, 3, 1))
    """

    def __init__(self, factory: GoogleServiceFactory) -> None:
        self._svc = factory.tasks

    # ── Task lists ────────────────────────────────────────────────────────────

    def list_task_lists(self) -> list[TaskList]:
        """Return all task lists in the account."""
        resp = self._svc.tasklists().list(maxResults=100).execute()
        return [_parse_tasklist(item) for item in resp.get("items", [])]

    def create_tasklist(self, title: str) -> str:
        """Create a new task list and return its list_id."""
        result = self._svc.tasklists().insert(body={"title": title}).execute()
        list_id = result["id"]
        logger.info("Created task list %s: %s", list_id, title)
        return list_id

    def delete_tasklist(self, tasklist_id: str) -> None:
        """Permanently delete a task list and all tasks within it."""
        self._svc.tasklists().delete(tasklist=tasklist_id).execute()
        logger.info("Deleted task list %s", tasklist_id)

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_tasks(
        self,
        tasklist_id: str = _DEFAULT_TASKLIST,
        include_completed: bool = False,
        max_results: int = 100,
    ) -> list[Task]:
        """
        Return tasks from a task list.

        Args:
            tasklist_id:        List ID or '@default' for the default list.
            include_completed:  Whether to include completed tasks.
            max_results:        Page size cap.
        """
        resp = self._svc.tasks().list(
            tasklist=tasklist_id,
            maxResults=max_results,
            showCompleted=include_completed,
            showHidden=include_completed,
        ).execute()
        return [_parse_task(t) for t in resp.get("items", [])]

    def get_open_tasks(self, tasklist_id: str = _DEFAULT_TASKLIST) -> list[Task]:
        """Return only incomplete (needsAction) tasks."""
        return [t for t in self.get_tasks(tasklist_id) if not t.is_done]

    def get_task(self, task_id: str, tasklist_id: str = _DEFAULT_TASKLIST) -> Task:
        """Fetch a single task by ID."""
        raw = self._svc.tasks().get(
            tasklist=tasklist_id, task=task_id
        ).execute()
        return _parse_task(raw)

    def create_task(
        self,
        title: str,
        tasklist_id: str = _DEFAULT_TASKLIST,
        due: Optional[datetime] = None,
        notes: str = "",
        parent_id: Optional[str] = None,
    ) -> str:
        """
        Create a task and return its task_id.

        Args:
            title:        Task title.
            tasklist_id:  Target list (defaults to '@default').
            due:          Optional due datetime (time portion is ignored by Tasks API).
            notes:        Optional notes / description.
            parent_id:    If provided, creates a subtask under this parent task ID.
        """
        body: dict = {"title": title, "status": "needsAction"}
        if notes:
            body["notes"] = notes
        if due:
            # Tasks API expects RFC 3339 with time component zeroed
            body["due"] = due.strftime("%Y-%m-%dT00:00:00.000Z")

        kwargs: dict = {"tasklist": tasklist_id, "body": body}
        if parent_id:
            kwargs["parent"] = parent_id

        result = self._svc.tasks().insert(**kwargs).execute()
        task_id = result["id"]
        logger.info("Created task %s: %s", task_id, title)
        return task_id

    def complete_task(
        self, task_id: str, tasklist_id: str = _DEFAULT_TASKLIST
    ) -> None:
        """Mark a task as completed."""
        self._svc.tasks().patch(
            tasklist=tasklist_id,
            task=task_id,
            body={"status": "completed"},
        ).execute()
        logger.info("Completed task %s", task_id)

    def reopen_task(
        self, task_id: str, tasklist_id: str = _DEFAULT_TASKLIST
    ) -> None:
        """Mark a completed task back to needsAction."""
        self._svc.tasks().patch(
            tasklist=tasklist_id,
            task=task_id,
            body={"status": "needsAction", "completed": None},
        ).execute()
        logger.info("Reopened task %s", task_id)

    def update_task(
        self,
        task_id: str,
        tasklist_id: str = _DEFAULT_TASKLIST,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        due: Optional[datetime] = None,
    ) -> None:
        """Patch one or more fields on an existing task."""
        body: dict = {}
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if due is not None:
            body["due"] = due.strftime("%Y-%m-%dT00:00:00.000Z")
        if body:
            self._svc.tasks().patch(
                tasklist=tasklist_id, task=task_id, body=body
            ).execute()
            logger.info("Updated task %s: %s", task_id, list(body.keys()))

    def delete_task(
        self, task_id: str, tasklist_id: str = _DEFAULT_TASKLIST
    ) -> None:
        """Permanently delete a task."""
        self._svc.tasks().delete(
            tasklist=tasklist_id, task=task_id
        ).execute()
        logger.info("Deleted task %s", task_id)


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_task(raw: dict) -> Task:
    return Task(
        task_id=raw["id"],
        title=raw.get("title", ""),
        status=raw.get("status", "needsAction"),
        notes=raw.get("notes", ""),
        due=_parse_rfc3339(raw.get("due", "")),
        completed_at=_parse_rfc3339(raw.get("completed", "")),
        parent_id=raw.get("parent"),
    )


def _parse_tasklist(raw: dict) -> TaskList:
    return TaskList(
        list_id=raw["id"],
        title=raw.get("title", ""),
        updated=_parse_rfc3339(raw.get("updated", "")),
    )
