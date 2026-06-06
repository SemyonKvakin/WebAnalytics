import uuid
import json
import csv
import io
import pandas as pd
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Dataset, Project, Report
from auth import require_auth
from metrics import METRICS_MAP

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _check_auth(request: Request):
    user = require_auth(request)
    if not user:
        return None
    return user


@router.post("/projects/{project_id}/datasets/{dataset_id}/calculate")
async def calculate(
    project_id: str,
    dataset_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    selected = form.getlist("metrics")

    dataset = db.query(Dataset).filter(Dataset.id == uuid.UUID(dataset_id)).first()

    try:
        if dataset.filename.endswith(".csv"):
            df = pd.read_csv(dataset.file_path)
        else:
            df = pd.read_json(dataset.file_path)
    except Exception as e:
        df = pd.DataFrame()

    results = {}
    for metric in selected:
        if metric in METRICS_MAP:
            results[metric] = METRICS_MAP[metric](df)

    report = Report(
        dataset_id=uuid.UUID(dataset_id),
        project_id=uuid.UUID(project_id),
        metrics=selected,
        result_json=results,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return RedirectResponse(
        f"/projects/{project_id}/reports/{report.id}",
        status_code=302,
    )


@router.get("/projects/{project_id}/reports/{report_id}", response_class=HTMLResponse)
def report_view(project_id: str, report_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    report = db.query(Report).filter(Report.id == uuid.UUID(report_id)).first()
    dataset = db.query(Dataset).filter(Dataset.id == report.dataset_id).first()

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "report": report,
            "dataset": dataset,
            "results": report.result_json,
            "results_json": json.dumps(report.result_json, ensure_ascii=False),
        },
    )


@router.get("/projects/{project_id}/reports/{report_id}/export/csv")
def export_csv(project_id: str, report_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    report = db.query(Report).filter(Report.id == uuid.UUID(report_id)).first()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Метрика", "Значение"])
    for metric, data in report.result_json.items():
        if isinstance(data, dict):
            for k, v in data.items():
                if not isinstance(v, dict):
                    writer.writerow([f"{metric} / {k}", v])
        else:
            writer.writerow([metric, data])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id[:8]}.csv"},
    )


@router.get("/projects/{project_id}/reports", response_class=HTMLResponse)
def reports_list(project_id: str, request: Request, db: Session = Depends(get_db)):
    user = _check_auth(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    reports = (
        db.query(Report)
        .filter(Report.project_id == uuid.UUID(project_id))
        .order_by(Report.created_at.desc())
        .all()
    )
    datasets = {str(d.id): d for d in db.query(Dataset).filter(Dataset.project_id == uuid.UUID(project_id)).all()}
    return templates.TemplateResponse(
        "reports_list.html",
        {"request": request, "user": user, "project": project, "reports": reports, "datasets": datasets},
    )
