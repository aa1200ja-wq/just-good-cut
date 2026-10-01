import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


PREFERRED_PORT = 8765


def _root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _available_port() -> int:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if probe.connect_ex(("127.0.0.1", PREFERRED_PORT)) != 0:
            return PREFERRED_PORT
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _open_browser(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def _show_error(message: str) -> None:
    log = _root() / "JustGoodCut-error.log"
    log.write_text(message, encoding="utf-8")
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "揪好剪", 0x10)
    else:
        print(message)


def main() -> None:
    root = _root()
    os.chdir(root)
    port = _available_port()
    url = f"http://127.0.0.1:{port}"
    sys.path.insert(0, str(root / "apps" / "server"))
    from app.main import app
    import uvicorn
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", log_config=None)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _show_error(f"啟動失敗：{type(exc).__name__}: {exc}")
