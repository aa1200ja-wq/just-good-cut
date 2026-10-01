from fastapi import APIRouter, HTTPException
from app.models import ProjectNameRequest
from app.services import projects

router = APIRouter(prefix="/api")


@router.put("/projects/{project_id}/name")
def rename_project(project_id: str, body: ProjectNameRequest):
    try:
        return projects.rename_project(project_id, body.name)
    except FileNotFoundError as exc:
        raise HTTPException(404, "找不到專案") from exc


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    try:
        projects.delete_project(project_id)
        return {"ok": True}
    except FileNotFoundError as exc:
        raise HTTPException(404, "找不到專案") from exc
