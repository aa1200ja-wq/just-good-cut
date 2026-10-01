from typing import Literal
from pydantic import BaseModel, Field


class Scene(BaseModel):
    id: str
    order: int
    narration: str
    start: float = 0
    end: float = 0
    search_query: str = ""
    rhythm: Literal["inherit", "natural", "fast"] = "inherit"
    selected_asset: str | None = None
    selected_asset_type: Literal["video", "image"] | None = None
    source_name: str | None = None
    source_url: str | None = None
    status: str = "waiting"
    asset_in: float = 0.0
    asset_out: float = 0.0
    transition: Literal["none", "fade"] = "none"

    @property
    def duration(self) -> float:
        return max(0.1, self.end - self.start)


class Project(BaseModel):
    id: str
    name: str
    script: str = ""
    voice: str = "zh-TW-YunJheNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    rhythm: Literal["natural", "fast"] = "natural"
    bgm_path: str | None = None
    bgm_volume: float = 0.18
    bgm_ducking: bool = True
    width: int = 1920
    height: int = 1080
    scenes: list[Scene] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    name: str


class ProjectNameRequest(BaseModel):
    name: str


class ProjectFormatRequest(BaseModel):
    ratio: Literal["16:9", "9:16"]


class ScriptRequest(BaseModel):
    script: str


class SceneUpdateRequest(BaseModel):
    narration: str | None = None
    search_query: str | None = None
    rhythm: Literal["inherit", "natural", "fast"] | None = None
    asset_in: float | None = None
    asset_out: float | None = None
    transition: Literal["none", "fade"] | None = None


class BulkQueriesRequest(BaseModel):
    queries: list[str]


class BulkSearchRequest(BaseModel):
    sources: list[str] = ["pexels", "pixabay", "wikimedia"]


class SplitSceneRequest(BaseModel):
    position: int


class TTSRequest(BaseModel):
    voice: str | None = None
    rate: str = "+0%"
    pitch: str = "+0Hz"
    rhythm: Literal["natural", "fast"] = "natural"


class BGMSettingsRequest(BaseModel):
    volume: float = 0.18
    ducking: bool = True


class FinalRenderRequest(BaseModel):
    burn_subtitles: bool = True


class SearchResult(BaseModel):
    id: str
    source: str
    media_type: Literal["video", "image"]
    preview_url: str
    download_url: str
    page_url: str = ""
    author: str = ""
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    width: int = 0
    height: int = 0
    duration: float = 0


class MaterialAsset(BaseModel):
    id: str
    media_type: Literal["video", "image"]
    local_path: str
    source: str = "manual"
    source_url: str = ""
    author: str = ""
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    custom_tags: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    width: int = 0
    height: int = 0
    duration: float = 0
    used_by: list[str] = Field(default_factory=list)


class AssetTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class TagRenameRequest(BaseModel):
    old: str
    new: str


class DownloadAssetRequest(BaseModel):
    result: SearchResult


class PreviewRequest(BaseModel):
    burn_subtitles: bool = True


class JianyingExportRequest(BaseModel):
    draft_folder: str = ""
    draft_name: str | None = None


class SettingsUpdateRequest(BaseModel):
    pexels_api_key: str | None = None
    pixabay_api_key: str | None = None
    jianying_draft_dir: str | None = None
    material_library_dir: str | None = None
