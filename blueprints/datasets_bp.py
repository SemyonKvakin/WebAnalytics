import os
import uuid
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import SessionLocal, Project, Dataset
from auth import roles_required, get_current_user
from datetime import datetime

datasets_bp = Blueprint("datasets", __name__, url_prefix="/projects")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@datasets_bp.route("/<project_id>/upload", methods=["GET", "POST"])
@roles_required("admin", "analyst")
def upload(project_id):
    user = get_current_user()
    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user["sub"]
        ).first()
        if not project:
            flash("Проект не найден.", "warning")
            return redirect(url_for("projects.index"))

        datasets = (
            db.query(Dataset)
            .filter(Dataset.project_id == project_id)
            .order_by(Dataset.uploaded_at.desc())
            .all()
        )

        if request.method == "POST":
            file = request.files.get("file")
            if not file or file.filename == "":
                flash("Файл не выбран.", "danger")
                return render_template("datasets/upload.html",
                                       project=project, datasets=datasets, user=user)

            filename = file.filename
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".csv", ".json"):
                flash("Допускаются только файлы CSV и JSON.", "danger")
                return render_template("datasets/upload.html",
                                       project=project, datasets=datasets, user=user)

            file_id   = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            file.save(file_path)

            try:
                df = pd.read_csv(file_path) if ext == ".csv" else pd.read_json(file_path)
                row_count = len(df)
                columns   = ",".join(df.columns.tolist())
            except Exception as e:
                os.remove(file_path)
                flash(f"Ошибка чтения файла: {e}", "danger")
                return render_template("datasets/upload.html",
                                       project=project, datasets=datasets, user=user)

            dataset = Dataset(
                project_id=project_id,
                user_id=user["sub"],
                filename=filename,
                file_path=file_path,
                row_count=row_count,
                columns=columns,
                uploaded_at=datetime.utcnow(),
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            flash(f"Файл «{filename}» загружен. Строк: {row_count}.", "success")
            return redirect(url_for("metrics.select",
                                    project_id=project_id,
                                    dataset_id=dataset.id))

        return render_template("datasets/upload.html",
                               project=project, datasets=datasets, user=user)
    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
        return redirect(url_for("projects.index"))
    finally:
        db.close()
