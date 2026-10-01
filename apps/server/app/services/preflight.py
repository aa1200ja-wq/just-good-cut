from pathlib import Path
from app.models import Project
from app.services.projects import project_path


def inspect_project(project: Project) -> dict:
    base = project_path(project.id)
    issues = []
    counts = {"素材": 0, "時間碼": 0, "旁白": 0}

    for scene in project.scenes:
        missing = []
        asset = Path(scene.selected_asset) if scene.selected_asset else None
        audio = base / "audio" / "scenes" / f"{scene.id}.mp3"

        if not asset or not asset.exists():
            missing.append("素材")
        if scene.end <= scene.start:
            missing.append("時間碼")
        if not audio.exists() or audio.stat().st_size == 0:
            missing.append("旁白")

        if missing:
            for key in missing:
                counts[key] += 1
            issues.append({
                "scene_id": scene.id,
                "narration": scene.narration,
                "missing": missing,
            })

    combined = base / "audio" / "narration.mp3"
    project_issues = []
    if not project.scenes:
        project_issues.append("沒有 Scene")
    elif not combined.exists() or combined.stat().st_size == 0:
        project_issues.append("整體旁白檔不存在")

    return {
        "ready": not issues and not project_issues and bool(project.scenes),
        "scene_count": len(project.scenes),
        "issues": issues,
        "project_issues": project_issues,
        "counts": counts,
    }


def missing_summary(report: dict) -> str:
    parts = []
    for item in report["issues"][:8]:
        parts.append(f"{item['scene_id']}：{'、'.join(item['missing'])}")
    if len(report["issues"]) > 8:
        parts.append(f"另有 {len(report['issues']) - 8} 幕")
    parts.extend(report["project_issues"])
    return "；".join(parts) or "輸出前檢查未通過"
