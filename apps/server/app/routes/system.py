import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.config import DATA_DIR, save_settings, settings
from app.models import SettingsUpdateRequest
from app.services import storage

router = APIRouter(prefix="/api")


def _draft_candidates() -> list[str]:
    paths: list[Path] = []
    if settings.jianying_draft_dir:
        paths.append(Path(settings.jianying_draft_dir))
    local = os.getenv("LOCALAPPDATA")
    home = Path.home()
    if local:
        paths.append(Path(local) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft")
    paths.extend([
        home / "Documents" / "JianyingPro Drafts",
        home / "Videos" / "JianyingPro Drafts",
    ])
    result: list[str] = []
    seen = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen and path.exists():
            seen.add(key)
            result.append(str(path.resolve()))
    return result


@router.get("/settings")
def get_settings():
    return {
        "pexels_configured": bool(settings.pexels_api_key),
        "pixabay_configured": bool(settings.pixabay_api_key),
        "jianying_draft_dir": settings.jianying_draft_dir,
        "material_library_dir": str(settings.material_library_path),
        "assets_dir": str(settings.assets_path),
        "data_dir": str(DATA_DIR),
    }


@router.put("/settings")
def update_settings(body: SettingsUpdateRequest):
    material_dir = body.material_library_dir
    try:
        if material_dir is not None:
            material_dir = storage.migrate_material_library(material_dir)
        save_settings(
            pexels_api_key=body.pexels_api_key,
            pixabay_api_key=body.pixabay_api_key,
            jianying_draft_dir=body.jianying_draft_dir,
            material_library_dir=material_dir,
        )
        return get_settings()
    except (OSError, ValueError) as exc:
        raise HTTPException(400, f"素材庫搬移失敗：{exc}") from exc


@router.get("/system/jianying-dirs")
def jianying_dirs():
    return {"paths": _draft_candidates()}
