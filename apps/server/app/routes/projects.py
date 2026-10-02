import asyncio
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.config import settings
from app.models import (
    BGMSettingsRequest, BulkQueriesRequest, BulkSearchRequest, CreateProjectRequest,
    ProjectFormatRequest, DownloadAssetRequest, FinalRenderRequest,
    JianyingExportRequest, PreviewRequest,
    SceneUpdateRequest, ScriptRequest, SplitSceneRequest, TTSRequest,
)
from app.services import final_render, jianying, library, media, preflight, preview, projects, search, tts
from app.services.ffmpeg_utils import run_ffmpeg

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
    if body.asset_in is not None:
        scene.asset_in = max(0.0, body.asset_in)
    if body.asset_out is not None:
        scene.asset_out = max(0.0, body.asset_out)
    if body.transition is not None:
        scene.transition = body.transition
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


@router.post("/projects/{project_id}/bgm")
async def upload_bgm(project_id: str, file: UploadFile = File(...)):
    project = _load(project_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
        raise HTTPException(400, "BGM 請使用 MP3、WAV、M4A、AAC、FLAC 或 OGG")
    data = await file.read()
    if not data:
        raise HTTPException(400, "BGM 檔案是空的")
    audio_dir = projects.project_path(project_id) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for old in audio_dir.glob("bgm.*"):
        old.unlink(missing_ok=True)
    target = audio_dir / f"bgm{ext}"
    target.write_bytes(data)
    project.bgm_path = str(target)
    return projects.save_project(project)


@router.put("/projects/{project_id}/bgm-settings")
def update_bgm_settings(project_id: str, body: BGMSettingsRequest):
    project = _load(project_id)
    project.bgm_volume = min(1.0, max(0.0, body.volume))
    project.bgm_ducking = body.ducking
    return projects.save_project(project)


@router.delete("/projects/{project_id}/bgm")
def remove_bgm(project_id: str):
    project = _load(project_id)
    if project.bgm_path:
        Path(project.bgm_path).unlink(missing_ok=True)
    project.bgm_path = None
    return projects.save_project(project)


@router.get("/projects/{project_id}/bgm-file")
def bgm_file(project_id: str):
    project = _load(project_id)
    path = Path(project.bgm_path) if project.bgm_path else None
    if not path or not path.exists():
        raise HTTPException(404, "尚未加入 BGM")
    return FileResponse(path, filename=path.name)


@router.post("/projects/{project_id}/render-final")
def render_final(project_id: str, body: FinalRenderRequest):
    project = _load(project_id)
    report = preflight.inspect_project(project)
    if not report["ready"]:
        raise HTTPException(
            400, "輸出前檢查未通過：" + preflight.missing_summary(report)
        )
    try:
        path = final_render.build_final(project, body.burn_subtitles)
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/projects/{project_id}/final-file")
def final_file(project_id: str):
    path = projects.project_path(project_id) / "exports" / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "尚未產生正式成片")
    return FileResponse(path, media_type="video/mp4", filename="揪好剪-成片.mp4")


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


@router.get("/projects/{project_id}/scenes/{scene_id}/asset-file")
def scene_asset_file(project_id: str, scene_id: str):
    project = _load(project_id)
    scene = _scene(project, scene_id)
    path = Path(scene.selected_asset) if scene.selected_asset else None
    if not path or not path.exists():
        raise HTTPException(404, "這一幕尚未選擇素材")
    return FileResponse(path)


@router.get("/projects/{project_id}/scenes/{scene_id}/asset-thumbnail")
def scene_asset_thumbnail(project_id: str, scene_id: str, time: float = 0.0):
    project = _load(project_id)
    scene = _scene(project, scene_id)
    path = Path(scene.selected_asset) if scene.selected_asset else None
    if not path or not path.exists():
        raise HTTPException(404, "這一幕尚未選擇素材")
    if scene.selected_asset_type != "video":
        return FileResponse(path)

    moment = max(0.0, float(time))
    thumb_dir = projects.project_path(project_id) / "exports" / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    target = thumb_dir / f"{scene_id}-{round(moment * 1000):08d}.jpg"
    if not target.exists():
        try:
            run_ffmpeg([
                "-y", "-ss", f"{moment:.3f}", "-i", str(path),
                "-frames:v", "1", "-vf", "scale=240:-2",
                "-q:v", "3", str(target),
            ])
        except Exception as exc:
            raise HTTPException(500, f"縮圖產生失敗：{exc}") from exc
    return FileResponse(target, media_type="image/jpeg")


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
