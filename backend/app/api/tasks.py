import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import require_permission
from ..schemas import Task, TaskComplete
from ..services import task_service


router = APIRouter()


@router.get("/tasks", response_model=list[Task])
def list_tasks(
    order_id: Optional[int] = Query(default=None),
    user: sqlite3.Row = Depends(require_permission("task:view")),
):
    return task_service.list_tasks(user=user, order_id=order_id)


@router.patch("/tasks/{tid}/start")
def start_task(
    tid: int,
    user: sqlite3.Row = Depends(require_permission("task:start")),
):
    return task_service.start_task(tid, user)


@router.patch("/tasks/{tid}/complete")
def complete_task(
    tid: int,
    body: TaskComplete,
    user: sqlite3.Row = Depends(require_permission("task:complete")),
):
    return task_service.complete_task(tid, body, user)
