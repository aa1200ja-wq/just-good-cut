import json
import os
import tempfile
from pathlib import Path

_temp_root = tempfile.mkdtemp(prefix="broll-tests-")
os.environ["BROLL_DATA_DIR"] = _temp_root
os.environ["PROJECTS_DIR"] = str(Path(_temp_root) / "projects")

from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.models import MaterialAsset, Project, Scene, SearchResult
from app.routes import search as search_route
from app.services import final_render, jianying, library, preview, projects, tts
from app.services.ffmpeg_utils import run_ffmpeg

client = TestClient(app)


def _video(path: Path, seconds: float = 0.25):
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", f"color=c=blue:s=640x360:r=30:d={seconds}",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ])


def test_web_ui_project_admin_and_format():
    assert client.get("/api/health").status_code == 200
    home = client.get("/").text
    assert "揪好剪" in home
    assert "台灣男聲｜雲哲" in home
    assert "台灣女聲｜曉臻" in home
    assert "台灣女聲｜曉雨" in home
    project = client.post("/api/projects", json={"name": "原名"}).json()
    renamed = client.put(
        f"/api/projects/{project['id']}/name", json={"name": "新名"}
    ).json()
    assert renamed["name"] == "新名"
    updated = client.put(
        f"/api/projects/{project['id']}/format", json={"ratio": "9:16"}
    ).json()
    assert (updated["width"], updated["height"]) == (1080, 1920)
    assert client.delete(f"/api/projects/{project['id']}").status_code == 200


def test_split_script():
    project = projects.create_project("測試")
    project.script = "第一句。第二句！\n第三句？"
    project = projects.split_script(project)
    assert [x.narration for x in project.scenes] == ["第一句。", "第二句！", "第三句？"]


def test_global_library_tags_merge_and_orientation():
    if settings.library_path.exists():
        settings.library_path.unlink()
    p1 = projects.create_project("A")
    p2 = projects.create_project("B")
    a_path = settings.assets_path / "a.mp4"
    b_path = settings.assets_path / "b.mp4"
    _video(a_path); _video(b_path)
    a = MaterialAsset(
        id="land", media_type="video", local_path=str(a_path),
        source="demo", title="ocean landscape", search_queries=["ocean"],
        custom_tags=["海洋"], width=1920, height=1080,
    )
    b = MaterialAsset(
        id="port", media_type="video", local_path=str(b_path),
        source="demo", title="ocean portrait", search_queries=["ocean"],
        width=1080, height=1920,
    )
    (projects.project_path(p1.id) / "library.json").write_text(
        json.dumps([a.model_dump()], ensure_ascii=False), encoding="utf-8"
    )
    library.save_library([a])
    (projects.project_path(p2.id) / "library.json").write_text(
        json.dumps([b.model_dump()], ensure_ascii=False), encoding="utf-8"
    )
    assert {x.id for x in library.list_library()} >= {"land", "port"}
    assert [x.id for x in library.search_results("ocean", "landscape")] == ["land"]
    assert [x.id for x in library.search_results("ocean", "portrait")] == ["port"]
    assert client.get("/api/library/tags").json()["tags"] == ["海洋"]
    assert client.put("/api/library/land/tags", json={"tags": ["海浪", "空拍"]}).status_code == 200
    assert set(client.get("/api/library/tags").json()["tags"]) == {"海浪", "空拍"}
    assert client.post(
        "/api/library/tags/rename", json={"old": "海浪", "new": "浪花"}
    ).json()["changed"] == 1
    assert client.delete("/api/library/tags/%E6%B5%AA%E8%8A%B1").json()["changed"] == 1


def test_external_search_excludes_downloaded(monkeypatch):
    existing = MaterialAsset(
        id="remote-1", media_type="video",
        local_path=str(settings.assets_path / "exists.mp4"),
        width=1920, height=1080,
    )
    Path(existing.local_path).write_bytes(b"x")
    library.upsert_asset(existing)

    async def fake_search_all(query, sources, orientation=""):
        return [
            SearchResult(
                id="remote-1", source="pixabay", media_type="video",
                preview_url="https://example.com/1.jpg", download_url="https://pixabay.com/1.mp4",
            ),
            SearchResult(
                id="remote-2", source="pixabay", media_type="video",
                preview_url="https://example.com/2.jpg", download_url="https://pixabay.com/2.mp4",
            ),
        ]

    monkeypatch.setattr(search_route.search, "search_all", fake_search_all)
    items = client.get("/api/search-external?q=ocean&orientation=landscape").json()
    assert [x["id"] for x in items] == ["remote-2"]


def test_scene_clip_is_longer_than_scene_and_preview_has_subtitles():
    project = Project(
        id="preview-test", name="preview",
        scenes=[Scene(id="S001", order=1, narration="測試字幕 TEST", start=0, end=1.017)],
    )
    source = settings.assets_path / "short.mp4"
    _video(source, 0.2)
    project.scenes[0].selected_asset = str(source)
    project.scenes[0].selected_asset_type = "video"
    projects.save_project(project)
    base = projects.project_path(project.id)
    audio = base / "audio" / "narration.mp3"
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.017",
        "-q:a", "5", str(audio),
    ])
    (base / "subtitles" / "narration.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,017\n測試字幕 TEST\n",
        encoding="utf-8",
    )
    clips = preview.build_scene_clips(project)
    import pyJianYingDraft as draft
    assert draft.VideoMaterial(str(clips[0])).duration >= 1_017_000
    out = preview.build_preview(project)
    assert out.exists() and out.stat().st_size > 0

    bgm = base / "audio" / "bgm.mp3"
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1.5",
        "-q:a", "5", str(bgm),
    ])
    project.bgm_path = str(bgm)
    project.bgm_volume = 0.12
    project.bgm_ducking = True
    projects.save_project(project)
    final = final_render.build_final(project)
    assert final.exists() and final.stat().st_size > 0


def test_jianying_three_tracks_with_short_source():
    project = projects.load_project("preview-test")
    draft_root = Path(tempfile.mkdtemp(prefix="jianying-drafts-"))
    existing = draft_root / "ci-draft"
    existing.mkdir()
    (existing / ".locked").write_text("busy", encoding="utf-8")
    name = jianying.export_jianying(project, str(draft_root), "ci-draft")
    assert name == "ci-draft_Broll"
    content = (draft_root / name / "draft_content.json").read_text(encoding="utf-8")
    data = json.loads(content)
    tracks = {track.get("name"): track for track in data["tracks"]}
    assert len(tracks["main_video"]["segments"]) == 1
    assert len(tracks["narration"]["segments"]) == 1
    assert len(tracks["caption"]["segments"]) == 1
    assert "測試字幕" in content



def test_search_local_returns_only_library_assets():
    items = client.get("/api/search-local?q=ocean&orientation=landscape").json()
    assert all(item["source"] == "local" for item in items)


def test_explicit_local_upload_accepts_opposite_orientation():
    project = projects.create_project("upload-orientation")
    project.script = "測試。"
    project = projects.split_script(project)
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (300, 600), "white").save(buffer, format="PNG")
    response = client.post(
        f"/api/projects/{project.id}/scenes/S001/upload",
        files={"file": ("portrait.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["scenes"][0]["selected_asset_type"] == "image"


def test_fast_rhythm_trims_leading_and_trailing_silence():
    base = Path(tempfile.mkdtemp(prefix="rhythm-test-"))
    source = base / "source.mp3"
    target = base / "tight.mp3"
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.4",
        "-af", "adelay=500|500,apad=pad_dur=0.5",
        "-c:a", "libmp3lame", "-q:a", "2", str(source),
    ])
    before = tts._duration(source)
    tts._tighten_audio(source, target)
    after = tts._duration(target)
    assert after < before - 0.3


def test_scene_rhythm_override_and_split_persistence():
    project = projects.create_project("rhythm-scenes")
    project.script = "短句。這是一個比較長的句子。"
    project = projects.split_script(project)

    response = client.put(
        f"/api/projects/{project.id}/scenes/S001",
        json={"narration": project.scenes[0].narration, "search_query": "", "rhythm": "fast"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["scenes"][0]["rhythm"] == "fast"

    split = client.post(
        f"/api/projects/{project.id}/scenes/S001/split",
        json={"position": 1},
    )
    assert split.status_code == 200
    assert split.json()["scenes"][0]["rhythm"] == "fast"
    assert split.json()["scenes"][1]["rhythm"] == "fast"

    fast_scene = Scene(id="x", order=1, narration="x", rhythm="fast")
    natural_scene = Scene(id="y", order=2, narration="y", rhythm="natural")
    inherit_scene = Scene(id="z", order=3, narration="z", rhythm="inherit")
    assert tts._effective_rhythm(fast_scene, "natural") == "fast"
    assert tts._effective_rhythm(natural_scene, "fast") == "natural"
    assert tts._effective_rhythm(inherit_scene, "fast") == "fast"



def test_preflight_lists_missing_items_and_blocks_export():
    project = projects.create_project("preflight-missing")
    project.script = "第一幕。第二幕。"
    project = projects.split_script(project)
    report = client.get(f"/api/projects/{project.id}/preflight")
    assert report.status_code == 200
    data = report.json()
    assert data["ready"] is False
    assert data["counts"] == {"素材": 2, "時間碼": 2, "旁白": 2}
    assert data["issues"][0]["scene_id"] == "S001"
    blocked = client.post(
        f"/api/projects/{project.id}/export/jianying",
        json={"draft_folder": "", "draft_name": "blocked"},
    )
    assert blocked.status_code == 400
    assert "S001" in blocked.json()["detail"]


def test_scene_audio_endpoint_and_ready_preflight():
    project = Project(
        id="preflight-ready", name="ready",
        scenes=[Scene(id="S001", order=1, narration="測試", start=0, end=1.0)],
    )
    asset = settings.assets_path / "ready.mp4"
    _video(asset, 1.2)
    project.scenes[0].selected_asset = str(asset)
    project.scenes[0].selected_asset_type = "video"
    projects.save_project(project)
    base = projects.project_path(project.id)
    scene_audio = base / "audio" / "scenes" / "S001.mp3"
    run_ffmpeg([
        "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-q:a", "5", str(scene_audio),
    ])
    (base / "audio" / "narration.mp3").write_bytes(scene_audio.read_bytes())

    audio_response = client.get(f"/api/projects/{project.id}/scenes/S001/audio")
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/mpeg")

    report = client.get(f"/api/projects/{project.id}/preflight").json()
    assert report["ready"] is True
    assert report["issues"] == []
