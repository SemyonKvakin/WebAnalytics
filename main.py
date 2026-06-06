from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import engine, Base
from routers import auth_router, projects_router, datasets_router, reports_router, admin_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MetricsApp")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router.router)
app.include_router(projects_router.router)
app.include_router(datasets_router.router)
app.include_router(reports_router.router)
app.include_router(admin_router.router)


@app.get("/")
def root():
    return RedirectResponse("/projects", status_code=302)
