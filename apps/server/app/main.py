from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes.projects import router as projects_router
from app.routes.library import router as library_router
from app.routes.project_admin import router as project_admin_router
from app.routes.search import router as search_router
from app.routes.review import router as review_router
from app.routes.system import router as system_router

app = FastAPI(title="B-roll Workflow", version="1.0.0")
app.include_router(projects_router)
app.include_router(library_router)
app.include_router(project_admin_router)
app.include_router(search_router)
app.include_router(review_router)
app.include_router(system_router)

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
