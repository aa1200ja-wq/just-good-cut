import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _data_dir() -> Path:
    override = os.getenv("BROLL_DATA_DIR")
    if override:
        path = Path(override)
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        path = Path(os.environ["LOCALAPPDATA"]) / "BrollWorkflow"
    else:
        path = Path.home() / ".broll-workflow"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


DATA_DIR = _data_dir()
ENV_PATH = DATA_DIR / ".env"


class Settings(BaseSettings):
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    projects_dir: str = str(DATA_DIR / "projects")
    default_voice: str = "zh-TW-YunJheNeural"
    jianying_draft_dir: str = ""
    material_library_dir: str = str(DATA_DIR)

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def projects_path(self) -> Path:
        path = Path(self.projects_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def material_library_path(self) -> Path:
        path = Path(self.material_library_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def assets_path(self) -> Path:
        path = self.material_library_path / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def library_path(self) -> Path:
        return self.material_library_path / "library.json"


settings = Settings()


def save_settings(
    pexels_api_key: str | None = None,
    pixabay_api_key: str | None = None,
    jianying_draft_dir: str | None = None,
    material_library_dir: str | None = None,
) -> Settings:
    if pexels_api_key is not None:
        settings.pexels_api_key = pexels_api_key.strip()
    if pixabay_api_key is not None:
        settings.pixabay_api_key = pixabay_api_key.strip()
    if jianying_draft_dir is not None:
        settings.jianying_draft_dir = jianying_draft_dir.strip()
    if material_library_dir is not None:
        settings.material_library_dir = material_library_dir.strip() or str(DATA_DIR)

    q = lambda value: json.dumps(str(value), ensure_ascii=False)
    lines = [
        f"PEXELS_API_KEY={q(settings.pexels_api_key)}",
        f"PIXABAY_API_KEY={q(settings.pixabay_api_key)}",
        f"PROJECTS_DIR={q(settings.projects_dir)}",
        f"DEFAULT_VOICE={q(settings.default_voice)}",
        f"JIANYING_DRAFT_DIR={q(settings.jianying_draft_dir)}",
        f"MATERIAL_LIBRARY_DIR={q(settings.material_library_dir)}",
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return settings
