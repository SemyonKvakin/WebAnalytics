from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import SessionLocal, User
from auth import roles_required, get_current_user
from datetime import datetime

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@roles_required("admin")
def users():
    user = get_current_user()
    db = SessionLocal()
    try:
        users_list = db.query(User).order_by(User.created_at.desc()).all()
        return render_template("admin/users.html", users=users_list, user=user)
    finally:
        db.close()


@admin_bp.route("/users/<user_id>/role", methods=["POST"])
@roles_required("admin")
def change_role(user_id):
    role = request.form.get("role", "")
    if role not in ("admin", "analyst", "viewer"):
        flash("Недопустимая роль.", "danger")
        return redirect(url_for("admin.users"))
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target:
            target.role = role
            db.commit()
            flash("Роль обновлена.", "success")
        else:
            flash("Пользователь не найден.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Ошибка: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_user(user_id):
    current = get_current_user()
    if user_id == current["sub"]:
        flash("Нельзя удалить собственный аккаунт.", "danger")
        return redirect(url_for("admin.users"))
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if target:
            db.delete(target)
            db.commit()
            flash("Пользователь удалён.", "success")
        else:
            flash("Пользователь не найден.", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Ошибка при удалении: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin.users"))
