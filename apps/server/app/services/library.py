import json
from pathlib import Path
from app.config import settings
from app.models import MaterialAsset, Project, Scene, SearchResult
from app.services.projects import list_projects, save_project


def load_library() -> list[MaterialAsset]:
    items, changed = _load_global()
    items, merged = _merge_legacy(items)
    changed = changed or merged
    for item in items:
        if _hydrate(item):
            changed = True
    if changed:
        save_library(items)
    return items


def save_library(items: list[MaterialAsset]) -> list[MaterialAsset]:
    path = settings.library_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [item.model_dump(exclude={"used_by"}) for item in items]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


def find_asset(asset_id: str) -> MaterialAsset | None:
    return next((x for x in load_library() if x.id == asset_id), None)


def asset_ids() -> set[str]:
    return {item.id for item in load_library()}


def custom_tags() -> list[str]:
    values = {tag for item in load_library() for tag in item.custom_tags if tag.strip()}
    return sorted(values, key=str.lower)


def set_custom_tags(asset_id: str, tags: list[str]) -> MaterialAsset:
    items = load_library()
    asset = next((x for x in items if x.id == asset_id), None)
    if not asset:
        raise FileNotFoundError(asset_id)
    asset.custom_tags = _merge([], tags)
    save_library(items)
    return asset


def rename_custom_tag(old: str, new: str) -> int:
    old_key, new_value = old.strip().lower(), new.strip()
    if not old_key or not new_value:
        raise ValueError("標籤名稱不能是空白")
    items, changed = load_library(), 0
    for item in items:
        if any(tag.lower() == old_key for tag in item.custom_tags):
            item.custom_tags = _merge(
                [], [new_value if tag.lower() == old_key else tag for tag in item.custom_tags]
            )
            changed += 1
    if changed:
        save_library(items)
    return changed


def delete_custom_tag(tag: str) -> int:
    key, items, changed = tag.strip().lower(), load_library(), 0
    for item in items:
        kept = [value for value in item.custom_tags if value.lower() != key]
        if len(kept) != len(item.custom_tags):
            item.custom_tags, changed = kept, changed + 1
    if changed:
        save_library(items)
    return changed


def upsert_asset(asset: MaterialAsset) -> MaterialAsset:
    items = load_library()
    old = next((x for x in items if x.id == asset.id), None)
    if old:
        _merge_asset(old, asset, include_custom=True)
        asset = old
    else:
        items.append(asset)
    _hydrate(asset)
    save_library(items)
    return asset


def list_library(query: str = "", tag: str = "") -> list[MaterialAsset]:
    items = load_library()
    usage = _usage_map()
    for item in items:
        item.used_by = usage.get(str(Path(item.local_path)), [])
    if tag.strip():
        key = tag.strip().lower()
        items = [item for item in items if key in {x.lower() for x in item.custom_tags}]
    if not query.strip():
        return items
    return [item for _, item in _ranked(items, query)]


def search_results(query: str, orientation: str = "", limit: int = 12) -> list[SearchResult]:
    ranked = _ranked(load_library(), query)
    output = []
    for _, item in ranked:
        if not Path(item.local_path).exists() or not _orientation_ok(item, orientation):
            continue
        output.append(SearchResult(
            id=item.id, source="local", media_type=item.media_type,
            preview_url=f"/api/library/{item.id}/file",
            download_url=f"local://{item.id}", page_url=item.source_url,
            author=item.author, title=item.title, tags=item.tags,
            width=item.width, height=item.height, duration=item.duration,
        ))
        if len(output) >= limit:
            break
    return output


def assign_asset(
    project: Project, scene: Scene, asset: MaterialAsset, enforce_orientation: bool = True
) -> Project:
    if not Path(asset.local_path).exists():
        raise FileNotFoundError("素材檔案不存在")
    expected = "landscape" if project.width >= project.height else "portrait"
    if enforce_orientation and not _orientation_ok(asset, expected):
        actual = "橫式" if asset.width >= asset.height else "直式"
        wanted = "橫式" if expected == "landscape" else "直式"
        raise ValueError(f"素材是{actual}，目前專案設定為{wanted}，請換素材或切換專案比例")
    scene.selected_asset = asset.local_path
    scene.selected_asset_type = asset.media_type
    scene.source_name = asset.source
    scene.source_url = asset.source_url or None
    scene.status = "asset_selected"
    return save_project(project)


def _load_global():
    path = settings.library_path
    if not path.exists():
        return [], False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [MaterialAsset.model_validate(item) for item in raw], False
    except (ValueError, json.JSONDecodeError):
        return [], True


def _merge_legacy(items: list[MaterialAsset]):
    by_id = {item.id: item for item in items}
    changed = False
    for path in settings.projects_path.glob("*/library.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError):
            continue
        for row in raw:
            try:
                incoming = MaterialAsset.model_validate(row)
            except ValueError:
                continue
            if incoming.id in by_id:
                before = by_id[incoming.id].model_dump()
                _merge_asset(by_id[incoming.id], incoming, include_custom=False)
                changed |= before != by_id[incoming.id].model_dump()
            else:
                by_id[incoming.id] = incoming
                changed = True
    return list(by_id.values()), changed


def _merge_asset(old: MaterialAsset, new: MaterialAsset, include_custom: bool = True):
    if (not old.local_path or not Path(old.local_path).exists()) and new.local_path and Path(new.local_path).exists():
        old.local_path = new.local_path
    old.source_url = new.source_url or old.source_url
    old.author = new.author or old.author
    old.title = new.title or old.title
    old.tags = _merge(old.tags, new.tags)
    if include_custom:
        old.custom_tags = _merge(old.custom_tags, new.custom_tags)
    old.search_queries = _merge(old.search_queries, new.search_queries)
    old.width = new.width or old.width
    old.height = new.height or old.height
    old.duration = new.duration or old.duration


def _hydrate(item: MaterialAsset) -> bool:
    if item.width and item.height:
        return False
    path = Path(item.local_path)
    if not path.exists():
        return False
    try:
        import pyJianYingDraft as draft
        material = draft.VideoMaterial(str(path))
        item.width, item.height = material.width, material.height
        item.duration = material.duration / 1_000_000
        return True
    except Exception:
        return False


def _orientation_ok(item, orientation: str) -> bool:
    if not orientation or not item.width or not item.height:
        return True
    return (item.width >= item.height) == (orientation == "landscape")


def _ranked(items: list[MaterialAsset], query: str):
    words = [x for x in query.lower().replace(",", " ").split() if x]
    phrase = query.strip().lower()
    ranked = []
    for item in items:
        text = _search_text(item)
        score = (100 if phrase and phrase in text else 0)
        score += sum(10 for word in words if word in text)
        if score:
            ranked.append((score, item))
    return sorted(ranked, key=lambda pair: pair[0], reverse=True)


def _usage_map() -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for project in list_projects():
        for scene in project.scenes:
            if scene.selected_asset:
                key = str(Path(scene.selected_asset))
                usage.setdefault(key, []).append(f"{project.name} / {scene.id}")
    return usage


def _search_text(asset: MaterialAsset) -> str:
    parts = [
        asset.id, asset.source, asset.author, asset.title,
        *asset.tags, *asset.custom_tags, *asset.search_queries,
    ]
    return " ".join(parts).lower()


def _merge(left: list[str], right: list[str]) -> list[str]:
    result, seen = [], set()
    for value in [*left, *right]:
        clean = value.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result
