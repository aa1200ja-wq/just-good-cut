from pathlib import Path
from app.models import Project
from app.services.ffmpeg_utils import run_ffmpeg
from app.services.preview import _clip_for_scene
from app.services.projects import project_path


TRANSITION_SECONDS = 0.35


def _escaped_subtitle_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _build_visual_track(project: Project) -> Path:
    base = project_path(project.id)
    export_dir = base / "exports"
    clips = [_clip_for_scene(project, scene, safety_pad=0.0) for scene in project.scenes]

    if not clips:
        raise RuntimeError("沒有可輸出的 Scene")

    silent = export_dir / "final_silent.mp4"
    if not any(scene.transition == "fade" for scene in project.scenes[:-1]):
        concat = export_dir / "final_clips.txt"
        concat.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in clips),
            encoding="utf-8",
        )
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-c", "copy", str(silent),
        ])
        return silent

    inputs = []
    for clip in clips:
        inputs.extend(["-i", str(clip)])

    filters = []
    labels = []
    last_index = len(project.scenes) - 1
    for index, scene in enumerate(project.scenes):
        duration = max(0.1, scene.duration)
        fade_duration = min(TRANSITION_SECONDS, max(0.05, duration / 2))
        chain = f"[{index}:v]fps=30,settb=1/30,setpts=N"
        if index > 0 and project.scenes[index - 1].transition == "fade":
            chain += f",fade=t=in:st=0:d={fade_duration:.3f}"
        if index < last_index and scene.transition == "fade":
            fade_start = max(0.0, duration - fade_duration)
            chain += (
                f",fade=t=out:st={fade_start:.3f}:"
                f"d={fade_duration:.3f}"
            )
        label = f"v{index}"
        filters.append(f"{chain}[{label}]")
        labels.append(f"[{label}]")

    filters.append(
        "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]"
    )
    run_ffmpeg([
        "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
        "-an", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(silent),
    ])
    return silent


def _mix_audio(project: Project, silent: Path) -> Path:
    base = project_path(project.id)
    narration = base / "audio" / "narration.mp3"
    if not narration.exists():
        raise RuntimeError("請先產生旁白")

    total = max(0.1, sum(scene.duration for scene in project.scenes))
    merged = base / "exports" / "final_base.mp4"
    bgm = Path(project.bgm_path) if project.bgm_path else None

    if not bgm or not bgm.exists():
        run_ffmpeg([
            "-y", "-i", str(silent), "-i", str(narration),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-t", f"{total:.3f}", str(merged),
        ])
        return merged

    volume = min(1.0, max(0.0, float(project.bgm_volume)))
    fade = min(1.0, total / 2)
    fade_out_start = max(0.0, total - fade)
    bgm_filter = (
        f"volume={volume:.3f},"
        f"afade=t=in:st=0:d={fade:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade:.3f}"
    )

    if project.bgm_ducking:
        audio_filter = (
            "[1:a]aresample=async=1:first_pts=0,asplit=2[narrmix][side];"
            f"[2:a]{bgm_filter}[bgmbase];"
            "[bgmbase][side]sidechaincompress="
            "threshold=0.03:ratio=8:attack=20:release=250[bgmduck];"
            "[narrmix][bgmduck]amix=inputs=2:duration=first:"
            "dropout_transition=0[aout]"
        )
    else:
        audio_filter = (
            "[1:a]aresample=async=1:first_pts=0[narr];"
            f"[2:a]{bgm_filter}[bgm];"
            "[narr][bgm]amix=inputs=2:duration=first:"
            "dropout_transition=0[aout]"
        )

    run_ffmpeg([
        "-y", "-i", str(silent), "-i", str(narration),
        "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex", audio_filter,
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-t", f"{total:.3f}", str(merged),
    ])
    return merged


def build_final(project: Project, burn_subtitles: bool = True) -> Path:
    base = project_path(project.id)
    silent = _build_visual_track(project)
    merged = _mix_audio(project, silent)
    final = base / "exports" / "final.mp4"

    if not burn_subtitles:
        final.write_bytes(merged.read_bytes())
        return final

    srt = base / "subtitles" / "narration.srt"
    if not srt.exists() or not srt.read_text(encoding="utf-8").strip():
        raise RuntimeError("字幕檔不存在，請重新產生旁白＋時間碼")

    style = (
        "FontName=Microsoft JhengHei,FontSize=26,"
        "Outline=2,Shadow=0,Alignment=2,MarginV=55"
    )
    run_ffmpeg([
        "-y", "-i", str(merged),
        "-vf",
        f"subtitles='{_escaped_subtitle_path(srt)}':"
        f"charenc=UTF-8:force_style='{style}'",
        "-c:v", "libx264", "-c:a", "copy",
        str(final),
    ])
    return final
