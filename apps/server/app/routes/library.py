from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.models import AssetTagsRequest, TagRenameRequest
from app.services import library, media

router = APIRouter(prefix="/api")


@router.get("/library")
def list_library(q: str = "", tag: str = ""):
    return library.list_library(q, tag)


@router.get("/library/tags")
def list_tags():
    return {"tags": library.custom_tags()}


@router.put("/library/{asset_id}/tags")
def set_asset_tags(asset_id: str, body: AssetTagsRequest):
    try:
        return library.set_custom_tags(asset_id, body.tags)
    except FileNotFoundError as exc:
        raise HTTPException(404, "找不到素材") from exc


@router.post("/library/tags/rename")
def rename_tag(body: TagRenameRequest):
    try:
        return {"changed": library.rename_custom_tag(body.old, body.new)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/library/tags/{tag}")
def delete_tag(tag: str):
    return {"changed": library.delete_custom_tag(tag)}


@router.get("/library/{asset_id}/file")
def material_file(asset_id: str):
    asset = library.find_asset(asset_id)
    if not asset or not Path(asset.local_path).exists():
        raise HTTPException(404, "找不到素材檔案")
    return FileResponse(asset.local_path)


@router.post("/library/upload")
async def upload_to_library(file: UploadFile = File(...), tags: str = ""):
    custom_tags = [x.strip() for x in tags.split(",") if x.strip()]
    try:
        return await media.upload_library_asset(file, custom_tags)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
