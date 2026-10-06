from fastapi import APIRouter

from ..schemas import LoginReq, LoginResp
from ..services import auth_service


router = APIRouter()


@router.post("/auth/login", response_model=LoginResp)
def login_route(req: LoginReq):
    return auth_service.login(req)
