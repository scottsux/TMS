from typing import Any, Dict

from pydantic import BaseModel

from ..models.enums import UserRole

class LoginReq(BaseModel):
    email: str
    password: str


class LoginResp(BaseModel):
    token: str
    role: UserRole
    user: Dict[str, Any]


