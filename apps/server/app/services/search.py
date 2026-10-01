import asyncio
import re
from urllib.parse import urlencode
import httpx
from app.config import settings
from app.models import SearchResult


def _split_tags(value: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,|]", value or "") if x.strip()]


def _orientation_ok(width: int, height: int, orientation: str) -> bool:
    if not orientation or not width or not height:
        return True
    return (width >= height) == (orientation == "landscape")


async def search_pexels(query: str, orientation: str = "", limit: int = 12) -> list[SearchResult]:
    if not settings.pexels_api_key:
        return []
    headers = {"Authorization": settings.pexels_api_key}
    params = {"query": query, "per_page": limit}
    if orientation:
        params["orientation"] = orientation
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://api.pexels.com/videos/search", params=params, headers=headers)
        r.raise_for_status()
    results = []
    for item in r.json().get("videos", []):
        files = sorted(item.get("video_files", []), key=lambda x: x.get("width", 0), reverse=True)
        chosen = next((f for f in files if 1280 <= f.get("width", 0) <= 3840), files[0] if files else None)
        if not chosen or not _orientation_ok(chosen.get("width", 0), chosen.get("height", 0), orientation):
            continue
        pictures = item.get("video_pictures", [])
        preview = pictures[0].get("picture", "") if pictures else ""
        user = item.get("user") or {}
        results.append(SearchResult(
            id=f"pexels-{item['id']}", source="pexels", media_type="video",
            preview_url=preview, download_url=chosen.get("link", ""),
            page_url=item.get("url", ""), author=user.get("name", ""),
            width=chosen.get("width", 0), height=chosen.get("height", 0),
            duration=float(item.get("duration", 0)),
        ))
    return results


async def search_pixabay(query: str, orientation: str = "", limit: int = 12) -> list[SearchResult]:
    if not settings.pixabay_api_key:
        return []
    params = {"key": settings.pixabay_api_key, "q": query, "per_page": limit, "safesearch": "true"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://pixabay.com/api/videos/", params=params)
        r.raise_for_status()
    results = []
    for item in r.json().get("hits", []):
        variants = item.get("videos", {})
        chosen = variants.get("large") or variants.get("medium") or variants.get("small") or {}
        width, height = chosen.get("width", 0), chosen.get("height", 0)
        url = chosen.get("url", "")
        if not url or not _orientation_ok(width, height, orientation):
            continue
        results.append(SearchResult(
            id=f"pixabay-{item['id']}", source="pixabay", media_type="video",
            preview_url=chosen.get("thumbnail", ""),
            download_url=url, page_url=item.get("pageURL", ""), author=item.get("user", ""),
            tags=_split_tags(item.get("tags", "")),
            width=width, height=height, duration=float(item.get("duration", 0)),
        ))
    return results


async def search_wikimedia(query: str, orientation: str = "", limit: int = 12) -> list[SearchResult]:
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|mime|mediatype|extmetadata|size",
        "iiurlwidth": 640, "origin": "*",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urlencode(params)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
    results = []
    for page in (r.json().get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if not (mime.startswith("video/") or mime.startswith("image/")):
            continue
        width = int(info.get("width", 0) or info.get("thumbwidth", 0) or 0)
        height = int(info.get("height", 0) or info.get("thumbheight", 0) or 0)
        if not _orientation_ok(width, height, orientation):
            continue
        metadata = info.get("extmetadata", {}) or {}
        results.append(SearchResult(
            id=f"wikimedia-{page['pageid']}", source="wikimedia",
            media_type="video" if mime.startswith("video/") else "image",
            preview_url=info.get("thumburl") or info.get("url", ""),
            download_url=info.get("url", ""), page_url=info.get("descriptionurl", ""),
            author=(metadata.get("Artist") or {}).get("value", ""),
            title=page.get("title", "").removeprefix("File:"),
            tags=_split_tags((metadata.get("Categories") or {}).get("value", "")),
            width=width, height=height,
        ))
    return results


async def search_all(query: str, sources: list[str], orientation: str = "") -> list[SearchResult]:
    tasks = []
    if "pexels" in sources:
        tasks.append(search_pexels(query, orientation))
    if "pixabay" in sources:
        tasks.append(search_pixabay(query, orientation))
    if "wikimedia" in sources:
        tasks.append(search_wikimedia(query, orientation))
    if not tasks:
        return []
    groups = await asyncio.gather(*tasks, return_exceptions=True)
    results: list[SearchResult] = []
    for group in groups:
        if isinstance(group, list):
            results.extend(group)
    return results
