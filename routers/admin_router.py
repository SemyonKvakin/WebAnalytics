from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import require_auth, hash_password
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _require_admin(request: Request):
    user = require_auth(request)
    if not user or user.get("role") != "admin":
        return None
    return user


@router.get("/admin/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    user = _require_admin(request)
    if not user:
        return RedirectResponse("/projects", status_code=302)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_users.html", {"request": request, "user": user, "users": users}
    )


@router.post("/admin/users/{user_id}/role")
def change_role(
    user_id: str,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = _require_admin(request)
    if not admin:
        return RedirectResponse("/projects", status_code=302)
    target = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if target and role in ("admin", "analyst", "viewer"):
        target.role = role
        db.commit()
    return RedirectResponse("/admin/users", status_code=302)


@router.post("/admin/users/{user_id}/delete")
def delete_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    admin = _require_admin(request)
    if not admin:
        return RedirectResponse("/projects", status_code=302)
    target = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse("/admin/users", status_code=302)
