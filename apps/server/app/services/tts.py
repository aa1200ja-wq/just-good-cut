import asyncio
from pathlib import Path
from app.models import Project
from app.services.ffmpeg_utils import run_ffmpeg
from app.services.projects import project_path, save_project


SUPPORTED_VOICES = {
    "zh-TW-YunJheNeural": "台灣男聲｜雲哲",
    "zh-TW-HsiaoChenNeural": "台灣女聲｜曉臻",
    "zh-TW-HsiaoYuNeural": "台灣女聲｜曉雨",
}


def _duration(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3
        return max(0.1, float(MP3(path).info.length))
    except Exception as exc:
        raise RuntimeError(f"無法讀取旁白長度：{path.name}") from exc


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def _effective_rhythm(scene, default: str) -> str:
    return scene.rhythm if scene.rhythm != "inherit" else default


def _tighten_audio(source: Path, target: Path) -> None:
    run_ffmpeg([
        "-y", "-i", str(source),
        "-af",
        "silenceremove=start_periods=1:start_duration=0.03:start_threshold=-50dB:"
        "stop_periods=1:stop_duration=0.05:stop_threshold=-50dB",
        "-c:a", "libmp3lame", "-q:a", "2", str(target),
    ])


async def synthesize(
    project: Project, voice: str, rate: str, pitch: str, rhythm: str = "natural"
) -> Project:
    if voice not in SUPPORTED_VOICES:
        raise ValueError("目前只支援揪好剪內建的 3 個台灣中文聲音")
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("尚未安裝 edge-tts，請重新啟動工具") from exc

    base = project_path(project.id)
    scene_dir = base / "audio" / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    cursor = 0.0

    for scene in project.scenes:
        target = scene_dir / f"{scene.id}.mp3"
        raw = scene_dir / f"{scene.id}.raw.mp3"
        comm = edge_tts.Communicate(
            scene.narration, voice=voice, rate=rate, pitch=pitch
        )
        await comm.save(str(raw))
        try:
            effective_rhythm = _effective_rhythm(scene, rhythm)
            if effective_rhythm == "fast":
                _tighten_audio(raw, target)
            else:
                target.write_bytes(raw.read_bytes())
        finally:
            raw.unlink(missing_ok=True)

        duration = _duration(target)
        scene.start = cursor
        scene.end = cursor + duration
        scene.status = "ready_for_asset"
        cursor = scene.end
        clips.append(target)

    concat_file = base / "audio" / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8"
    )
    narration = base / "audio" / "narration.mp3"
    run_ffmpeg([
        "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:a", "libmp3lame", "-q:a", "2", str(narration),
    ])

    lines: list[str] = []
    for i, scene in enumerate(project.scenes, start=1):
        lines.extend([
            str(i), f"{_srt_time(scene.start)} --> {_srt_time(scene.end)}",
            scene.narration, "",
        ])
    (base / "subtitles" / "narration.srt").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    project.voice = voice
    project.rate = rate
    project.pitch = pitch
    project.rhythm = "fast" if rhythm == "fast" else "natural"
    return save_project(project)


def synthesize_sync(
    project: Project, voice: str, rate: str, pitch: str, rhythm: str = "natural"
) -> Project:
    return asyncio.run(synthesize(project, voice, rate, pitch, rhythm))
