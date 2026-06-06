from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import hash_password, verify_password, create_access_token

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse("/projects", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Неверный email или пароль", "tab": "login"}
        )
    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    response = RedirectResponse("/projects", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 8)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "tab": "register"})


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Пользователь с таким email уже существует", "tab": "register"},
        )
    user = User(email=email, password_hash=hash_password(password), role="analyst")
    db.add(user)
    db.commit()
    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    response = RedirectResponse("/projects", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 8)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response
