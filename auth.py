from datetime import datetime, timedelta
from jose import JWTError, jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, redirect, url_for, flash
from functools import wraps

SECRET_KEY = "metrics_secret_key_change_in_production"
ALGORITHM  = "HS256"
TOKEN_TTL  = 60 * 8


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return check_password_hash(hashed, plain)


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_TTL)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user():
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_token(token)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Для доступа к этой странице необходимо войти в систему.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Для доступа к этой странице необходимо войти в систему.", "warning")
                return redirect(url_for("auth.login"))
            if user.get("role") not in roles:
                flash("У вас недостаточно прав для доступа к этой странице.", "danger")
                return redirect(url_for("projects.index"))
            return f(*args, **kwargs)
        return decorated
    return decorator
