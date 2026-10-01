import asyncio
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.config import settings
from app.models import (
    BulkQueriesRequest, BulkSearchRequest, CreateProjectRequest, ProjectFormatRequest,
    DownloadAssetRequest, JianyingExportRequest, PreviewRequest,
    SceneUpdateRequest, ScriptRequest, SplitSceneRequest, TTSRequest,
)
from app.services import jianying, library, media, preflight, preview, projects, search, tts

router = APIRouter(prefix="/api")


def _load(project_id: str):
    try:
        return projects.load_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "找不到專案") from exc


def _scene(project, scene_id: str):
    scene = next((x for x in project.scenes if x.id == scene_id), None)
    if not scene:
        raise HTTPException(404, "找不到 Scene")
    return scene


def _prefer_local(local_items, remote_items):
    seen = set()
    output = []
    for item in [*local_items, *remote_items]:
        if item.id in seen:
            continue
        seen.add(item.id)
        output.append(item)
    return output


@router.get("/health")
def health():
    return {
        "ok": True,
        "pexels": bool(settings.pexels_api_key),
        "pixabay": bool(settings.pixabay_api_key),
    }


@router.get("/projects")
def list_projects():
    return projects.list_projects()


@router.post("/projects")
def create_project(body: CreateProjectRequest):
    return projects.create_project(body.name)


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    return _load(project_id)


@router.put("/projects/{project_id}/format")
def set_format(project_id: str, body: ProjectFormatRequest):
    project = _load(project_id)
    project.width, project.height = ((1920, 1080) if body.ratio == "16:9" else (1080, 1920))
    return projects.save_project(project)


@router.post("/projects/{project_id}/scenes/{scene_id}/use-library/{asset_id}")
def use_library_asset(project_id: str, scene_id: str, asset_id: str):
    project = _load(project_id)
    asset = library.find_asset(asset_id)
    if not asset:
        raise HTTPException(404, "找不到素材")
    try:
        return library.assign_asset(project, _scene(project, scene_id), asset)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/projects/{project_id}/script")
def set_script(project_id: str, body: ScriptRequest):
    project = _load(project_id)
    project.script = body.script
    projects.save_project(project)
    return projects.split_script(project)


@router.put("/projects/{project_id}/scenes/{scene_id}")
def update_scene(project_id: str, scene_id: str, body: SceneUpdateRequest):
    project = _load(project_id)
    scene = _scene(project, scene_id)
    if body.narration is not None:
        scene.narration = body.narration.strip()
    if body.search_query is not None:
        scene.search_query = body.search_query.strip()
    if body.rhythm is not None:
        scene.rhythm = body.rhythm
    return projects.save_project(project)


@router.put("/projects/{project_id}/scene-queries")
def set_scene_queries(project_id: str, body: BulkQueriesRequest):
    project = _load(project_id)
    queries = [q.strip() for q in body.queries]
    for index, scene in enumerate(project.scenes):
        scene.search_query = queries[index] if index < len(queries) else ""
    return projects.save_project(project)


@router.post("/projects/{project_id}/search-all")
async def search_all_scenes(project_id: str, body: BulkSearchRequest):
    project = _load(project_id)

    async def search_scene(scene):
        query = scene.search_query.strip()
        if not query:
            return scene.id, []
        orientation = "landscape" if project.width >= project.height else "portrait"
        local_items = library.search_results(query, orientation)
        remote_items = await search.search_all(query, body.sources, orientation)
        return scene.id, _prefer_local(local_items, remote_items)

    pairs = await asyncio.gather(*(search_scene(scene) for scene in project.scenes))
    return {scene_id: results for scene_id, results in pairs}


@router.post("/projects/{project_id}/search-external")
async def search_external_scenes(project_id: str, body: BulkSearchRequest):
    project = _load(project_id)
    downloaded = library.asset_ids()
    orientation = "landscape" if project.width >= project.height else "portrait"

    async def search_scene(scene):
        query = scene.search_query.strip()
        if not query:
            return scene.id, []
        results = await search.search_all(query, body.sources, orientation)
        return scene.id, [item for item in results if item.id not in downloaded]

    pairs = await asyncio.gather(*(search_scene(scene) for scene in project.scenes))
    return {scene_id: results for scene_id, results in pairs}


@router.post("/projects/{project_id}/scenes/{scene_id}/split")
def split_scene(project_id: str, scene_id: str, body: SplitSceneRequest):
    project = _load(project_id)
    idx = next((i for i, x in enumerate(project.scenes) if x.id == scene_id), None)
    if idx is None:
        raise HTTPException(404, "找不到 Scene")
    scene = project.scenes[idx]
    pos = body.position
    if pos <= 0 or pos >= len(scene.narration):
        raise HTTPException(400, "切分位置無效")
    left, right = scene.narration[:pos].strip(), scene.narration[pos:].strip()
    scene.narration = left
    from app.models import Scene
    project.scenes.insert(
        idx + 1,
        Scene(id="new", order=idx + 2, narration=right, rhythm=scene.rhythm),
    )
    return projects.renumber(project)


@router.post("/projects/{project_id}/scenes/{scene_id}/merge-next")
def merge_next(project_id: str, scene_id: str):
    project = _load(project_id)
    idx = next((i for i, x in enumerate(project.scenes) if x.id == scene_id), None)
    if idx is None or idx >= len(project.scenes) - 1:
        raise HTTPException(400, "沒有下一個 Scene 可合併")
    project.scenes[idx].narration += project.scenes[idx + 1].narration
    del project.scenes[idx + 1]
    return projects.renumber(project)


@router.post("/projects/{project_id}/tts")
async def generate_tts(project_id: str, body: TTSRequest):
    project = _load(project_id)
    if not project.scenes:
        raise HTTPException(400, "請先輸入腳本")
    voice = body.voice or settings.default_voice
    try:
        return await tts.synthesize(project, voice, body.rate, body.pitch, body.rhythm)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/search")
async def asset_search(q: str, sources: str = "pexels,pixabay,wikimedia", orientation: str = ""):
    if not q.strip():
        return []
    try:
        local_items = library.search_results(q.strip(), orientation)
        remote_items = await search.search_all(
            q.strip(), [x for x in sources.split(",") if x], orientation
        )
        return _prefer_local(local_items, remote_items)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/download")
async def download(project_id: str, scene_id: str, body: DownloadAssetRequest):
    project = _load(project_id)
    try:
        return await media.download_asset(project, _scene(project, scene_id), body.result)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/projects/{project_id}/scenes/{scene_id}/upload")
async def upload(project_id: str, scene_id: str, file: UploadFile = File(...)):
    project = _load(project_id)
    try:
        return await media.upload_asset(project, _scene(project, scene_id), file)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"加入本機素材失敗：{exc}") from exc


@router.post("/projects/{project_id}/preview")
def make_preview(project_id: str, body: PreviewRequest):
    try:
        path = preview.build_preview(_load(project_id), body.burn_subtitles)
        return {"path": str(path)}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/projects/{project_id}/preview-file")
def preview_file(project_id: str):
    path = projects.project_path(project_id) / "exports" / "preview.mp4"
    if not path.exists():
        raise HTTPException(404, "尚未產生預覽")
    return FileResponse(path, media_type="video/mp4", filename="preview.mp4")


@router.post("/projects/{project_id}/export/jianying")
def export_jy(project_id: str, body: JianyingExportRequest):
    project = _load(project_id)
    report = preflight.inspect_project(project)
    if not report["ready"]:
        raise HTTPException(
            400, "輸出前檢查未通過：" + preflight.missing_summary(report)
        )
    try:
        name = jianying.export_jianying(project, body.draft_folder, body.draft_name)
        return {"ok": True, "draft_name": name}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
