from pathlib import Path
from app.models import Project, Scene
from app.services.ffmpeg_utils import run_ffmpeg
from app.services.projects import project_path


SAFETY_PAD = 1.0


def _clip_for_scene(project: Project, scene: Scene, safety_pad: float = SAFETY_PAD) -> Path:
    base = project_path(project.id)
    out_dir = base / "exports" / "scene_clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{scene.id}.mp4"
    duration = max(0.1, scene.duration or 4.0)
    render_duration = duration + max(0.0, safety_pad)
    scale = (
        f"scale={project.width}:{project.height}:force_original_aspect_ratio=increase,"
        f"crop={project.width}:{project.height},fps=30"
    )
    if scene.selected_asset:
        source = Path(scene.selected_asset)
        if scene.selected_asset_type == "image":
            args = [
                "-y", "-loop", "1", "-i", str(source),
                "-t", f"{render_duration:.3f}", "-vf", scale,
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target),
            ]
        else:
            args = [
                "-y", "-stream_loop", "-1", "-i", str(source),
                "-t", f"{render_duration:.3f}",
                "-vf", f"{scale},tpad=stop_mode=clone:stop_duration={max(0.0, safety_pad):.3f}",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target),
            ]
    else:
        args = [
            "-y", "-f", "lavfi", "-i",
            f"color=c=0x202020:s={project.width}x{project.height}:r=30",
            "-t", f"{render_duration:.3f}", "-an", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", str(target),
        ]
    run_ffmpeg(args)
    return target


def build_scene_clips(project: Project, safety_pad: float = SAFETY_PAD) -> list[Path]:
    return [_clip_for_scene(project, scene, safety_pad) for scene in project.scenes]


def build_preview(project: Project, burn_subtitles: bool = True) -> Path:
    base = project_path(project.id)
    clips = build_scene_clips(project, safety_pad=0.0)
    concat = base / "exports" / "clips.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips), encoding="utf-8")
    silent = base / "exports" / "silent.mp4"
    run_ffmpeg([
        "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", str(silent),
    ])
    narration = base / "audio" / "narration.mp3"
    if not narration.exists():
        raise RuntimeError("請先產生旁白")
    merged = base / "exports" / "preview_base.mp4"
    run_ffmpeg([
        "-y", "-i", str(silent), "-i", str(narration),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(merged),
    ])
    final = base / "exports" / "preview.mp4"
    if not burn_subtitles:
        final.write_bytes(merged.read_bytes())
        return final

    srt = base / "subtitles" / "narration.srt"
    if not srt.exists() or not srt.read_text(encoding="utf-8").strip():
        raise RuntimeError("字幕檔不存在，請重新產生旁白＋時間碼")
    escaped = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    style = "FontName=Microsoft JhengHei,FontSize=26,Outline=2,Shadow=0,Alignment=2,MarginV=55"
    run_ffmpeg([
        "-y", "-i", str(merged),
        "-vf", f"subtitles='{escaped}':charenc=UTF-8:force_style='{style}'",
        "-c:v", "libx264", "-c:a", "copy", str(final),
    ])
    return final
