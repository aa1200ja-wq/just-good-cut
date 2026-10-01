from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.services import preflight, projects

router = APIRouter(prefix="/api/projects")


def _project(project_id: str):
    try:
        return projects.load_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "找不到專案") from exc


@router.get("/{project_id}/preflight")
def inspect(project_id: str):
    return preflight.inspect_project(_project(project_id))


@router.get("/{project_id}/scenes/{scene_id}/audio")
def scene_audio(project_id: str, scene_id: str):
    project = _project(project_id)
    if not any(scene.id == scene_id for scene in project.scenes):
        raise HTTPException(404, "找不到 Scene")
    path = projects.project_path(project_id) / "audio" / "scenes" / f"{scene_id}.mp3"
    if not path.exists() or path.stat().st_size == 0:
        raise HTTPException(404, "這一幕還沒有旁白，請先產生旁白＋時間碼")
    return FileResponse(path, media_type="audio/mpeg", filename=f"{scene_id}.mp3")
