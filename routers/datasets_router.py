import os
import uuid
import pandas as pd
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Dataset, Project
from auth import require_auth
from metrics import METRICS_GROUPS, METRICS_LABELS

router = APIRouter()
templates = Jinja2Templates(directory="templates")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _check_auth(request: Request):
    user = require_auth(request)
    if not user:
        return None
    return user


@router.get("/projects/{project_id}/upload", response_class=HTMLResponse)
def upload_page(project_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    datasets = (
        db.query(Dataset)
        .filter(Dataset.project_id == uuid.UUID(project_id))
        .order_by(Dataset.uploaded_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "user": user, "project": project, "datasets": datasets},
    )


@router.post("/projects/{project_id}/upload")
async def upload_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    contents = await file.read()
    filename = file.filename
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")

    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_json(file_path)
        row_count = len(df)
    except Exception:
        row_count = 0

    dataset = Dataset(
        user_id=uuid.UUID(user["sub"]),
        project_id=uuid.UUID(project_id),
        filename=filename,
        file_path=file_path,
        row_count=row_count,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return RedirectResponse(
        f"/projects/{project_id}/datasets/{dataset.id}/metrics",
        status_code=302,
    )


@router.get("/projects/{project_id}/datasets/{dataset_id}/metrics", response_class=HTMLResponse)
def metrics_page(project_id: str, dataset_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    dataset = db.query(Dataset).filter(Dataset.id == uuid.UUID(dataset_id)).first()
    return templates.TemplateResponse(
        "metrics.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "dataset": dataset,
            "metrics_groups": METRICS_GROUPS,
            "metrics_labels": METRICS_LABELS,
        },
    )
