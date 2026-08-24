from pydantic import BaseModel, Field

from ..models.enums import ExceptionType

class OrderExceptionCreate(BaseModel):
    type: ExceptionType
    reason: str = Field(min_length=1, max_length=1000)


class OrderExceptionResolve(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=1000)


