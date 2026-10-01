import json
import re
import shutil
import uuid
from pathlib import Path
from app.config import settings
from app.models import Project, Scene


_SPLIT_RE = re.compile(r"(?<=[。！？；!?;])|\n+")


def _project_dir(project_id: str) -> Path:
    return settings.projects_path / project_id


def save_project(project: Project) -> Project:
    folder = _project_dir(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "audio" / "scenes").mkdir(parents=True, exist_ok=True)
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    (folder / "subtitles").mkdir(parents=True, exist_ok=True)
    (folder / "exports").mkdir(parents=True, exist_ok=True)
    (folder / "script.txt").write_text(project.script, encoding="utf-8")
    (folder / "project.json").write_text(
        project.model_dump_json(indent=2), encoding="utf-8"
    )
    return project


def create_project(name: str) -> Project:
    project = Project(id=uuid.uuid4().hex[:12], name=name.strip() or "未命名專案")
    return save_project(project)


def load_project(project_id: str) -> Project:
    path = _project_dir(project_id) / "project.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    return Project.model_validate_json(path.read_text(encoding="utf-8"))


def list_projects() -> list[Project]:
    items: list[Project] = []
    for path in settings.projects_path.glob("*/project.json"):
        try:
            items.append(Project.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValueError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda p: p.name.lower())


def rename_project(project_id: str, name: str) -> Project:
    project = load_project(project_id)
    project.name = name.strip() or "未命名專案"
    return save_project(project)


def delete_project(project_id: str) -> None:
    folder = _project_dir(project_id)
    if not folder.exists():
        raise FileNotFoundError(project_id)
    shutil.rmtree(folder)


def split_script(project: Project) -> Project:
    chunks = [part.strip() for part in _SPLIT_RE.split(project.script) if part.strip()]
    scenes = []
    for index, text in enumerate(chunks, start=1):
        scenes.append(Scene(id=f"S{index:03d}", order=index, narration=text))
    project.scenes = scenes
    return save_project(project)


def renumber(project: Project) -> Project:
    for index, scene in enumerate(project.scenes, start=1):
        scene.order = index
        scene.id = f"S{index:03d}"
    return save_project(project)


def project_path(project_id: str) -> Path:
    return _project_dir(project_id)
