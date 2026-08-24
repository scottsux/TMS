from typing import Optional

from pydantic import BaseModel, Field

from ..models.enums import TaskStatus

class Task(BaseModel):
    id: int
    order_id: int
    status: TaskStatus
    actual_weight: Optional[float] = None


class TaskComplete(BaseModel):
    actual_weight: Optional[float] = Field(default=None, ge=0)


