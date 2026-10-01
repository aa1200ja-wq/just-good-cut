import subprocess


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("內建 FFmpeg 無法載入，請重新執行 START_HERE.cmd") from exc


def run_ffmpeg(args: list[str]) -> None:
    cmd = [ffmpeg_exe(), *args]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="ignore")[-1200:]
        raise RuntimeError(f"FFmpeg 處理失敗：{detail}") from exc
