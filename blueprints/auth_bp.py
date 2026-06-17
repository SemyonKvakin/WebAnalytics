from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from database import SessionLocal, User
from auth import hash_password, verify_password, create_token, get_current_user
from datetime import datetime, timezone

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("projects.index"))
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password  = request.form.get("password", "")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.login == login_val).first()
            if user and verify_password(password, user.password_hash):
                token = create_token({
                    "sub":   user.id,
                    "login": user.login,
                    "role":  user.role,
                    "name":  user.first_name,
                })
                response = make_response(redirect(url_for("projects.index")))
                response.set_cookie("access_token", token, httponly=True, max_age=60*60*8)
                flash("Вы успешно вошли в систему.", "success")
                return response
            flash("Неверный логин или пароль.", "danger")
        except Exception as e:
            flash(f"Ошибка при входе: {e}", "danger")
        finally:
            db.close()
    return render_template("login.html", error=None)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("projects.index"))
    if request.method == "POST":
        login_val  = request.form.get("login", "").strip()
        password   = request.form.get("password", "")
        first_name = request.form.get("first_name", "").strip() or login_val
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.login == login_val).first()
            if existing:
                flash("Пользователь с таким логином уже существует.", "danger")
                return render_template("register.html")
            user = User(
                login=login_val,
                password_hash=hash_password(password),
                first_name=first_name,
                role="viewer",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(user)
            db.commit()
            flash("Регистрация успешна. Войдите в систему.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.rollback()
            flash(f"Ошибка при регистрации: {e}", "danger")
        finally:
            db.close()
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    response = make_response(redirect(url_for("auth.login")))
    response.delete_cookie("access_token")
    flash("Вы вышли из системы.", "info")
    return response