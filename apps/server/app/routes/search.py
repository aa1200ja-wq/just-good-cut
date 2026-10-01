from fastapi import APIRouter, HTTPException
from app.services import library, search

router = APIRouter(prefix="/api")


@router.get("/search-external")
async def search_external(q: str, sources: str = "pexels,pixabay,wikimedia", orientation: str = ""):
    if not q.strip():
        return []
    try:
        downloaded = library.asset_ids()
        items = await search.search_all(
            q.strip(), [x for x in sources.split(",") if x], orientation
        )
        return [item for item in items if item.id not in downloaded]
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/search-local")
def search_local(q: str = "", orientation: str = ""):
    if not q.strip():
        return []
    return library.search_results(q.strip(), orientation)
