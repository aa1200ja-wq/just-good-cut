import { api } from "./api.js"
import { state, selectedSources } from "./state.js"
import { clipEditorMarkup, initClipEditor } from "./clip_editor.js"

let activeAudio = null
const expandedCandidates = new Set()

const sceneKey = sceneId => `${state.project?.id || ""}:${sceneId}`

const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[ch]))

function candidateCard(item, index, sceneId) {
  const shape = item.width && item.height
    ? (item.width >= item.height ? "橫式" : "直式") + ` ${item.width}×${item.height}`
    : ""
  const meta = [item.source === "local" ? "本機素材" : item.source, item.author, shape]
    .filter(Boolean).join(" · ")
  const preview = item.source === "local" && item.media_type === "video"
    ? `<video src="${esc(item.preview_url)}" muted controls preload="metadata"></video>`
    : `<img src="${esc(item.preview_url)}" alt="候選素材" loading="lazy" />`
  return `
    <article class="media-card">
      ${preview}
      <div class="media-body">
        <div class="media-meta">${esc(meta || item.media_type)}</div>
        <button class="primary" data-action="choose" data-scene="${sceneId}" data-index="${index}">
          ${item.source === "local" ? "使用素材庫素材" : "下載並使用"}
        </button>
        ${item.page_url ? `<a href="${esc(item.page_url)}" target="_blank" class="media-meta">查看來源</a>` : ""}
      </div>
    </article>`
}

function sceneCard(scene) {
  const candidates = state.results[scene.id] || []
  const time = scene.end > scene.start
    ? `${scene.start.toFixed(1)}–${scene.end.toFixed(1)}s`
    : "尚未產生時間碼"
  const resultBlock = candidates.length ? `
    <details class="candidate-wrap" data-candidates="${scene.id}" ${expandedCandidates.has(sceneKey(scene.id)) ? "open" : ""}>
      <summary>候選素材 ${candidates.length} 筆</summary>
      <div class="candidates">
        ${candidates.map((item, i) => candidateCard(item, i, scene.id)).join("")}
      </div>
    </details>` : ""
  return `
    <article class="scene" data-scene="${scene.id}">
      <div class="scene-head">
        <strong>${scene.id}</strong><span>${time}</span>
        ${scene.selected_asset ? '<span class="ok">已選素材</span>' : ""}
        <label class="scene-rhythm">節奏
          <select data-field="rhythm">
            <option value="inherit" ${(scene.rhythm || "inherit") === "inherit" ? "selected" : ""}>跟隨全局</option>
            <option value="natural" ${scene.rhythm === "natural" ? "selected" : ""}>自然</option>
            <option value="fast" ${scene.rhythm === "fast" ? "selected" : ""}>快切</option>
          </select>
        </label>
      </div>
      <textarea data-field="narration">${esc(scene.narration)}</textarea>
      <input data-field="query" value="${esc(scene.search_query)}" placeholder="素材搜尋詞" />
      <div class="scene-material-actions">
        <button data-action="external">搜尋外部素材</button>
        <button data-action="local" class="ghost">素材庫加入</button>
        <label class="button-link ghost">加入本機素材
          <input data-action="upload" type="file" accept="video/*,image/*" hidden />
        </label>
      </div>
      ${clipEditorMarkup(scene)}
      <div class="scene-actions">
        <button class="ghost" data-action="play-audio">▶ 播放旁白</button>
        <button class="ghost" data-action="split">拆分</button>
        <button class="ghost" data-action="merge">併下一幕</button>
      </div>
      ${resultBlock}
    </article>`
}

export function renderScenes() {
  const root = document.querySelector("#scene-list")
  const project = state.project
  root.innerHTML = project?.scenes?.length
    ? project.scenes.map(sceneCard).join("")
    : '<p class="hint">貼上腳本並切 Scene 後，這裡會顯示每一幕。</p>'
  document.querySelector("#scene-count").textContent =
    project ? `${project.scenes.length} 個 Scene` : ""
}

function getScene(sceneId) {
  return state.project?.scenes.find(x => x.id === sceneId)
}

async function saveScene(card) {
  const scene = getScene(card.dataset.scene)
  if (!scene) return
  scene.narration = card.querySelector('[data-field="narration"]').value
  scene.search_query = card.querySelector('[data-field="query"]').value
  scene.rhythm = card.querySelector('[data-field="rhythm"]').value
  scene.asset_in = Number(card.querySelector('[data-field="asset_in"]')?.value || 0)
  scene.asset_out = Number(card.querySelector('[data-field="asset_out"]')?.value || 0)
  scene.transition = card.querySelector('[data-field="transition"]')?.value || "none"
  await api.updateScene(state.project.id, scene)
}

async function searchExternal(card, notify) {
  await saveScene(card)
  const sceneId = card.dataset.scene
  const orientation = state.project.width >= state.project.height ? "landscape" : "portrait"
  notify(`${sceneId} 正在重新搜尋外部素材…`)
  state.results[sceneId] = await api.searchExternal(
    card.querySelector('[data-field="query"]').value,
    selectedSources(), orientation,
  )
  expandedCandidates.add(sceneKey(sceneId))
  renderScenes()
  notify(`${sceneId} 找到 ${state.results[sceneId].length} 個尚未下載的外部素材`)
}

async function searchLocal(card, notify) {
  await saveScene(card)
  const sceneId = card.dataset.scene
  const orientation = state.project.width >= state.project.height ? "landscape" : "portrait"
  state.results[sceneId] = await api.searchLocal(
    card.querySelector('[data-field="query"]').value, orientation,
  )
  expandedCandidates.add(sceneKey(sceneId))
  renderScenes()
  notify(`${sceneId} 素材庫找到 ${state.results[sceneId].length} 個符合素材`)
}

export function bindSceneEvents({ notify, refreshProject, refreshLibrary }) {
  const root = document.querySelector("#scene-list")
  root.addEventListener("change", async event => {
    const card = event.target.closest(".scene")
    if (!card || !state.project) return
    try {
      if (event.target.dataset.action === "upload") {
        const input = event.target
        const file = input.files?.[0]
        if (!file) return
        notify("正在加入本機素材…")
        await api.upload(state.project.id, card.dataset.scene, file)
        await refreshProject()
        await refreshLibrary()
        notify("素材已加入素材庫並套用；比例不同時會自動裁切")
        return
      }
      if (event.target.dataset.field) await saveScene(card)
    } catch (err) {
      notify(err.message, true)
    } finally {
      if (event.target.dataset.action === "upload") event.target.value = ""
    }
  })

  root.addEventListener("toggle", event => {
    const clipDetails = event.target.closest("details[data-clip-editor]")
    if (clipDetails?.open) {
      const card = clipDetails.closest(".scene")
      initClipEditor(clipDetails, card, saveScene, notify)
    }

    const details = event.target.closest("details[data-candidates]")
    if (!details) return
    const key = sceneKey(details.dataset.candidates)
    if (details.open) expandedCandidates.add(key)
    else expandedCandidates.delete(key)
  }, true)

  root.addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]")
    if (!button || !state.project) return
    const card = button.closest(".scene")
    const sceneId = card.dataset.scene
    const scene = getScene(sceneId)
    try {
      if (button.dataset.action === "play-audio") {
        if (activeAudio) activeAudio.pause()
        activeAudio = new Audio(api.sceneAudioUrl(state.project.id, sceneId))
        await activeAudio.play()
        notify(`${sceneId} 正在播放旁白`)
      }
      if (button.dataset.action === "external") await searchExternal(card, notify)
      if (button.dataset.action === "local") await searchLocal(card, notify)
      if (button.dataset.action === "choose") {
        const item = state.results[sceneId]?.[Number(button.dataset.index)]
        if (!item) return
        notify(item.source === "local" ? "正在套用素材庫素材…" : "正在下載並加入素材庫…")
        await api.choose(state.project.id, sceneId, item)
        if (item.source !== "local") {
          state.results[sceneId] = (state.results[sceneId] || []).filter(x => x.id !== item.id)
        }
        await refreshProject()
        await refreshLibrary()
        notify(`${sceneId} 已選用素材`)
      }
      if (button.dataset.action === "split" && scene) {
        const pos = Number(prompt("從第幾個字切開？", Math.floor(scene.narration.length / 2)))
        if (!pos) return
        state.project = await api.splitScene(state.project.id, sceneId, pos)
        state.results = {}; refreshProject(false)
        notify("Scene 已拆分，請重新產生旁白時間碼")
      }
      if (button.dataset.action === "merge") {
        state.project = await api.mergeScene(state.project.id, sceneId)
        state.results = {}; refreshProject(false)
        notify("Scene 已合併，請重新產生旁白時間碼")
      }
    } catch (err) { notify(err.message, true) }
  })
}
