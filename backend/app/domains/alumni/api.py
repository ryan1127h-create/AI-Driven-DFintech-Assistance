from fastapi import APIRouter, Depends

from app.domains.alumni import service
from app.domains.alumni.schemas import ListedUpdate, RequestCreate, RequestUpdate
from app.domains.auth.interface import get_current_user_id

router = APIRouter(prefix="/alumni")


@router.get("/matches")
def list_matches(search: str = "", expertise: str = "", user_id: str = Depends(get_current_user_id)):
    tags = [t for t in expertise.split(",") if t]
    return service.list_matches(user_id, search, tags)


@router.get("/requests")
def list_requests(user_id: str = Depends(get_current_user_id)):
    return service.list_requests(user_id)


@router.post("/requests", status_code=201)
def send_request(body: RequestCreate, user_id: str = Depends(get_current_user_id)):
    return service.send_request(user_id, body.alumni_id, body.note)


@router.patch("/requests/{request_id}")
def update_request(request_id: str, body: RequestUpdate, user_id: str = Depends(get_current_user_id)):
    if body.action == "cancel":
        return service.cancel_request(user_id, request_id)
    return service.respond(user_id, request_id, body.action, body.share, body.reply_note)


@router.get("/me")
def get_me(user_id: str = Depends(get_current_user_id)):
    role = service.viewer_kind(user_id)  # 403 for anyone who isn't a student or alumnus
    return {"role": role, "profile": service.get_my_profile(user_id) if role == "alumni" else None}


@router.patch("/me")
def set_listed(body: ListedUpdate, user_id: str = Depends(get_current_user_id)):
    return service.set_listed(user_id, body.listed)
