import { api } from "./api.js"
import { state } from "./state.js"

const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[ch]))

export function fillLibraryScenes() {
  const select = document.querySelector("#library-scene")
  const current = select.value
  const scenes = state.project?.scenes || []
  select.innerHTML = '<option value="">選擇要套用的 Scene</option>' +
    scenes.map(s => `<option value="${s.id}">${s.id}</option>`).join("")
  if (scenes.some(s => s.id === current)) select.value = current
}

function assetCard(asset) {
  const url = api.libraryFile(asset.id)
  const preview = asset.media_type === "video"
    ? `<video src="${url}" muted controls preload="metadata"></video>`
    : `<img src="${url}" alt="本機素材" loading="lazy" />`
  const sourceTags = [...asset.search_queries, ...asset.tags]
    .filter((x, i, all) => x && all.indexOf(x) === i).slice(0, 8)
  const customTags = asset.custom_tags || []
  return `
    <article class="media-card">
      ${preview}
      <div class="media-body">
        <strong title="${esc(asset.title || asset.id)}">${esc(asset.title || asset.id)}</strong>
        <div class="media-meta">${esc(asset.source)}${asset.author ? " · " + esc(asset.author) : ""}</div>
        <div class="tag-row">
          ${customTags.map(x => `<span class="tag custom">${esc(x)}</span>`).join("")}
          ${sourceTags.map(x => `<span class="tag">${esc(x)}</span>`).join("")}
        </div>
        ${asset.used_by.length ? `<div class="media-meta">使用中：${asset.used_by.join("、")}</div>` : ""}
        <button data-action="edit-tags" data-asset="${esc(asset.id)}" class="ghost">編輯標籤</button>
        <button data-action="apply" data-asset="${esc(asset.id)}" class="primary">套用到選定 Scene</button>
      </div>
    </article>`
}

export async function refreshTags() {
  const result = await api.libraryTags()
  const tags = result.tags || []
  const filter = document.querySelector("#library-tag-filter")
  const manager = document.querySelector("#tag-manager-select")
  const oldFilter = filter.value
  const oldManager = manager.value
  filter.innerHTML = '<option value="">全部標籤</option>' +
    tags.map(tag => `<option value="${esc(tag)}">${esc(tag)}</option>`).join("")
  manager.innerHTML = '<option value="">選擇標籤</option>' +
    tags.map(tag => `<option value="${esc(tag)}">${esc(tag)}</option>`).join("")
  if (tags.includes(oldFilter)) filter.value = oldFilter
  if (tags.includes(oldManager)) manager.value = oldManager
}

export async function refreshLibrary(query = null) {
  const grid = document.querySelector("#library-grid")
  const q = query ?? document.querySelector("#library-query").value
  const tag = document.querySelector("#library-tag-filter").value
  state.library = await api.library(q, tag)
  grid.innerHTML = state.library.length
    ? state.library.map(assetCard).join("")
    : '<p class="hint">目前沒有符合的本機素材。</p>'
  fillLibraryScenes()
  await refreshTags()
}

export function bindLibrary({ notify, refreshProject }) {
  document.querySelector("#library-search").addEventListener("click", async () => {
    try { await refreshLibrary() } catch (err) { notify(err.message, true) }
  })
  document.querySelector("#library-query").addEventListener("keyup", async event => {
    if (event.key !== "Enter") return
    try { await refreshLibrary() } catch (err) { notify(err.message, true) }
  })
  document.querySelector("#library-tag-filter").addEventListener("change", async () => {
    try { await refreshLibrary() } catch (err) { notify(err.message, true) }
  })
  document.querySelector("#library-grid").addEventListener("click", async event => {
    const button = event.target.closest("button[data-asset]")
    if (!button) return
    const assetId = button.dataset.asset
    try {
      if (button.dataset.action === "edit-tags") {
        const asset = state.library.find(x => x.id === assetId)
        const current = (asset?.custom_tags || []).join(", ")
        const value = prompt("自訂標籤（用逗號分隔）", current)
        if (value === null) return
        const tags = value.split(",").map(x => x.trim()).filter(Boolean)
        await api.setAssetTags(assetId, tags)
        await refreshLibrary()
        notify("素材標籤已更新")
        return
      }
      if (!state.project) { notify("請先選擇專案", true); return }
      const sceneId = document.querySelector("#library-scene").value
      if (!sceneId) { notify("請先選擇要套用的 Scene", true); return }
      await api.useLibrary(state.project.id, sceneId, assetId)
      await refreshProject()
      await refreshLibrary()
      notify(`素材已套用到 ${sceneId}`)
    } catch (err) { notify(err.message, true) }
  })
  document.querySelector("#rename-tag").addEventListener("click", async () => {
    const oldTag = document.querySelector("#tag-manager-select").value
    const newTag = document.querySelector("#tag-rename-input").value.trim()
    if (!oldTag || !newTag) { notify("請選擇標籤並輸入新名稱", true); return }
    try {
      await api.renameTag(oldTag, newTag)
      document.querySelector("#tag-rename-input").value = ""
      await refreshLibrary()
      notify("標籤已重新命名")
    } catch (err) { notify(err.message, true) }
  })
  document.querySelector("#delete-tag").addEventListener("click", async () => {
    const tag = document.querySelector("#tag-manager-select").value
    if (!tag || !confirm(`確定從所有素材移除標籤「${tag}」？`)) return
    try {
      await api.deleteTag(tag)
      await refreshLibrary()
      notify("標籤已刪除")
    } catch (err) { notify(err.message, true) }
  })
}
