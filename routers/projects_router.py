from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Project
from auth import require_auth
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _check_auth(request: Request):
    user = require_auth(request)
    if not user:
        return None
    return user


@router.get("/projects", response_class=HTMLResponse)
def projects_list(request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    projects = (
        db.query(Project)
        .filter(Project.user_id == uuid.UUID(user["sub"]))
        .order_by(Project.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "projects.html", {"request": request, "user": user, "projects": projects}
    )


@router.post("/projects/create")
def create_project(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = Project(
        user_id=uuid.UUID(user["sub"]),
        name=name,
        description=description or None,
    )
    db.add(project)
    db.commit()
    return RedirectResponse("/projects", status_code=302)


@router.post("/projects/{project_id}/delete")
def delete_project(project_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = db.query(Project).filter(
        Project.id == uuid.UUID(project_id),
        Project.user_id == uuid.UUID(user["sub"]),
    ).first()
    if project:
        db.delete(project)
        db.commit()
    return RedirectResponse("/projects", status_code=302)
