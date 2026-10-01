import json
import shutil
from pathlib import Path
from app.config import settings
from app.models import MaterialAsset
from app.services import library


def _read_index(path: Path) -> list[MaterialAsset]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [MaterialAsset.model_validate(item) for item in raw]
    except (ValueError, json.JSONDecodeError):
        return []


def _merge_items(current: list[MaterialAsset], existing: list[MaterialAsset]):
    merged = {item.id: item for item in existing}
    for item in current:
        old = merged.get(item.id)
        if old is None:
            merged[item.id] = item
            continue
        old.tags = list(dict.fromkeys([*old.tags, *item.tags]))
        old.custom_tags = list(dict.fromkeys([*old.custom_tags, *item.custom_tags]))
        old.search_queries = list(dict.fromkeys([*old.search_queries, *item.search_queries]))
        old.source_url = item.source_url or old.source_url
        old.author = item.author or old.author
        old.title = item.title or old.title
        old.width = item.width or old.width
        old.height = item.height or old.height
        old.duration = item.duration or old.duration
    return list(merged.values())


def migrate_material_library(target_dir: str) -> str:
    target_root = Path(target_dir).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    current_root = settings.material_library_path

    if target_root == current_root:
        return str(target_root)

    current = library.load_library()
    existing = _read_index(target_root / "library.json")
    items = _merge_items(current, existing)
    target_assets = target_root / "assets"
    target_assets.mkdir(parents=True, exist_ok=True)

    for item in items:
        source = Path(item.local_path)
        suffix = source.suffix.lower() or (".mp4" if item.media_type == "video" else ".jpg")
        target = target_assets / f"{item.id}{suffix}"
        if source.exists() and source.resolve() != target.resolve():
            if not target.exists():
                shutil.copy2(source, target)
            item.local_path = str(target.resolve())
        elif target.exists():
            item.local_path = str(target.resolve())

    index_path = target_root / "library.json"
    payload = [item.model_dump(exclude={"used_by"}) for item in items]
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(target_root)
