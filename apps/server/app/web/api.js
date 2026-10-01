async function request(url, options = {}) {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || res.statusText)
  }
  const type = res.headers.get("content-type") || ""
  return type.includes("application/json") ? res.json() : res.text()
}

const json = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

export const api = {
  projects: () => request("/api/projects"),
  createProject: name => request("/api/projects", json({ name })),
  renameProject: (id, name) => request(`/api/projects/${id}/name`, json({ name }, "PUT")),
  deleteProject: id => request(`/api/projects/${id}`, { method: "DELETE" }),
  project: id => request(`/api/projects/${id}`),
  setFormat: (id, ratio) => request(`/api/projects/${id}/format`, json({ ratio }, "PUT")),
  setScript: (id, script) => request(`/api/projects/${id}/script`, json({ script }, "PUT")),
  updateScene: (id, scene) => request(
    `/api/projects/${id}/scenes/${scene.id}`,
    json({
      narration: scene.narration,
      search_query: scene.search_query,
      rhythm: scene.rhythm || "inherit",
      asset_in: Number(scene.asset_in || 0),
      asset_out: Number(scene.asset_out || 0),
      transition: scene.transition || "none",
    }, "PUT")),
  splitScene: (id, sceneId, position) => request(
    `/api/projects/${id}/scenes/${sceneId}/split`, json({ position })),
  mergeScene: (id, sceneId) => request(
    `/api/projects/${id}/scenes/${sceneId}/merge-next`, json({})),
  tts: (id, voice, rate, pitch, rhythm) => request(
    `/api/projects/${id}/tts`, json({ voice, rate, pitch, rhythm })),
  setQueries: (id, queries) => request(
    `/api/projects/${id}/scene-queries`, json({ queries }, "PUT")),
  searchAll: (id, sources) => request(
    `/api/projects/${id}/search-all`, json({ sources })),
  searchExternalAll: (id, sources) => request(
    `/api/projects/${id}/search-external`, json({ sources })),
  search: (q, sources, orientation) => request(
    `/api/search?q=${encodeURIComponent(q)}&sources=${sources.join(",")}&orientation=${orientation}`),
  searchExternal: (q, sources, orientation) => request(
    `/api/search-external?q=${encodeURIComponent(q)}&sources=${sources.join(",")}&orientation=${orientation}`),
  searchLocal: (q, orientation) => request(
    `/api/search-local?q=${encodeURIComponent(q)}&orientation=${orientation}`),
  choose: (id, sceneId, result) => request(
    `/api/projects/${id}/scenes/${sceneId}/download`, json({ result })),
  upload: async (id, sceneId, file) => {
    const form = new FormData(); form.append("file", file)
    return request(`/api/projects/${id}/scenes/${sceneId}/upload`, { method: "POST", body: form })
  },
  uploadLibrary: async (file, tags = "") => {
    const form = new FormData(); form.append("file", file)
    return request(`/api/library/upload?tags=${encodeURIComponent(tags)}`, { method: "POST", body: form })
  },
  preview: id => request(`/api/projects/${id}/preview`, json({ burn_subtitles: true })),
  previewUrl: id => `/api/projects/${id}/preview-file?t=${Date.now()}`,
  uploadBgm: async (id, file) => {
    const form = new FormData(); form.append("file", file)
    return request(`/api/projects/${id}/bgm`, { method: "POST", body: form })
  },
  saveBgm: (id, volume, ducking) => request(
    `/api/projects/${id}/bgm-settings`, json({ volume, ducking }, "PUT")),
  removeBgm: id => request(`/api/projects/${id}/bgm`, { method: "DELETE" }),
  bgmUrl: id => `/api/projects/${id}/bgm-file?t=${Date.now()}`,
  renderFinal: id => request(`/api/projects/${id}/render-final`, json({ burn_subtitles: true })),
  finalUrl: id => `/api/projects/${id}/final-file?t=${Date.now()}`,
  sceneAudioUrl: (id, sceneId) =>
    `/api/projects/${id}/scenes/${sceneId}/audio?t=${Date.now()}`,
  preflight: id => request(`/api/projects/${id}/preflight`),
  exportJianying: (id, name) => request(
    `/api/projects/${id}/export/jianying`, json({ draft_folder: "", draft_name: name })),
  library: (q = "", tag = "") => request(
    `/api/library?q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}`),
  libraryFile: assetId => `/api/library/${encodeURIComponent(assetId)}/file`,
  libraryTags: () => request("/api/library/tags"),
  setAssetTags: (assetId, tags) => request(
    `/api/library/${encodeURIComponent(assetId)}/tags`, json({ tags }, "PUT")),
  renameTag: (oldTag, newTag) => request(
    "/api/library/tags/rename", json({ old: oldTag, new: newTag })),
  deleteTag: tag => request(
    `/api/library/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
  useLibrary: (id, sceneId, assetId) => request(
    `/api/projects/${id}/scenes/${sceneId}/use-library/${encodeURIComponent(assetId)}`, json({})),
  settings: () => request("/api/settings"),
  saveSettings: body => request("/api/settings", json(body, "PUT")),
  detectJianying: () => request("/api/system/jianying-dirs"),
}
