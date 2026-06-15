from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import SessionLocal, Project, Dataset, Report
from auth import login_required, roles_required, get_current_user
from datetime import datetime

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/")
@login_required
def index():
    user = get_current_user()
    db = SessionLocal()
    try:
        projects = (
            db.query(Project)
            .order_by(Project.created_at.desc())
            .all()
        )
        stats = {}
        for p in projects:
            stats[p.id] = {
                "datasets": db.query(Dataset).filter(Dataset.project_id == p.id).count(),
                "reports":  db.query(Report).filter(Report.project_id  == p.id).count(),
            }
    finally:
        db.close()
    return render_template("projects/index.html", projects=projects, stats=stats, user=user)


@projects_bp.route("/create", methods=["GET", "POST"])
@roles_required("admin", "analyst")
def create():
    user = get_current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Название проекта обязательно.", "danger")
            return render_template("projects/create.html", user=user)
        db = SessionLocal()
        try:
            project = Project(
                user_id=user["sub"],
                name=name,
                description=description or None,
                created_at=datetime.utcnow(),
            )
            db.add(project)
            db.commit()
            flash(f"Проект «{name}» успешно создан.", "success")
            return redirect(url_for("projects.index"))
        except Exception as e:
            db.rollback()
            flash(f"Ошибка при создании проекта: {e}", "danger")
        finally:
            db.close()
    return render_template("projects/create.html", user=user)


@projects_bp.route("/<project_id>/delete", methods=["GET", "POST"])
@roles_required("admin", "analyst")
def delete(project_id):
    user = get_current_user()
    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user["sub"]
        ).first()
        if project:
            db.delete(project)
            db.commit()
            flash("Проект удалён.", "success")
        else:
            flash("Проект не найден.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Ошибка при удалении: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("projects.index"))
