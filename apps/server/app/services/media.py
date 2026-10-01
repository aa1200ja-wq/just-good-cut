from pathlib import Path
from urllib.parse import urlparse
import uuid
import httpx
from fastapi import UploadFile
from PIL import Image
from app.config import settings
from app.models import MaterialAsset, Project, Scene, SearchResult
from app.services import library


_ALLOWED_HOST_BITS = ("pexels.com", "pixabay.com", "wikimedia.org", "wikimediausercontent.com")
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def _safe_suffix(url: str, media_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    return ".mp4" if media_type == "video" else ".jpg"


def _validate_remote(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not any(bit in host for bit in _ALLOWED_HOST_BITS):
        raise ValueError(f"不允許下載此網域：{host}")


def _classify(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _IMAGE_EXT:
        return "image"
    if suffix in _VIDEO_EXT:
        return "video"
    raise ValueError("不支援此素材格式，請使用 JPG、PNG、WEBP、MP4、MOV、WEBM 等常用格式")


def _probe(path: Path, media_type: str):
    try:
        if media_type == "image":
            with Image.open(path) as image:
                return int(image.width), int(image.height), 0.0
        import pyJianYingDraft as draft
        material = draft.VideoMaterial(str(path))
        if not material.width or not material.height:
            raise ValueError("無法讀取影片尺寸")
        return material.width, material.height, material.duration / 1_000_000
    except Exception as exc:
        raise ValueError(f"無法讀取素材：{path.name}") from exc


async def download_asset(project: Project, scene: Scene, result: SearchResult) -> Project:
    query = scene.search_query.strip()
    if result.source == "local" or result.download_url.startswith("local://"):
        asset = library.find_asset(result.id)
        if not asset:
            raise FileNotFoundError("本機素材不存在")
        if query:
            asset.search_queries = [*asset.search_queries, query]
            library.upsert_asset(asset)
        return library.assign_asset(project, scene, asset)

    _validate_remote(result.download_url)
    existing = library.find_asset(result.id)
    if existing and Path(existing.local_path).exists():
        if query:
            existing.search_queries = [*existing.search_queries, query]
        existing.tags = [*existing.tags, *result.tags]
        library.upsert_asset(existing)
        return library.assign_asset(project, scene, existing)

    target = settings.assets_path / f"{result.id}{_safe_suffix(result.download_url, result.media_type)}"
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async with client.stream("GET", result.download_url) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    handle.write(chunk)

    width, height, duration = result.width, result.height, result.duration
    if not width or not height:
        width, height, probed_duration = _probe(target, result.media_type)
        duration = duration or probed_duration

    asset = MaterialAsset(
        id=result.id, media_type=result.media_type,
        local_path=str(target.resolve()), source=result.source,
        source_url=result.page_url, author=result.author, title=result.title,
        tags=result.tags, search_queries=[query] if query else [],
        width=width, height=height, duration=duration,
    )
    library.upsert_asset(asset)
    return library.assign_asset(project, scene, asset)


async def _save_upload(upload: UploadFile, custom_tags: list[str] | None = None) -> MaterialAsset:
    original = Path(upload.filename or "asset")
    media_type = _classify(original)
    asset_id = f"manual-{uuid.uuid4().hex[:10]}"
    target = settings.assets_path / f"{asset_id}{original.suffix.lower()}"
    target.write_bytes(await upload.read())
    try:
        width, height, duration = _probe(target, media_type)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    asset = MaterialAsset(
        id=asset_id, media_type=media_type, local_path=str(target.resolve()),
        source="manual", title=upload.filename or asset_id,
        custom_tags=custom_tags or [], width=width, height=height, duration=duration,
    )
    return library.upsert_asset(asset)


async def upload_library_asset(
    upload: UploadFile, custom_tags: list[str] | None = None
) -> MaterialAsset:
    return await _save_upload(upload, custom_tags)


async def upload_asset(project: Project, scene: Scene, upload: UploadFile) -> Project:
    asset = await _save_upload(upload)
    if scene.search_query.strip():
        asset.search_queries = [*asset.search_queries, scene.search_query.strip()]
        library.upsert_asset(asset)
    return library.assign_asset(project, scene, asset, enforce_orientation=False)
