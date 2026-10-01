import { api } from "./api.js"
import { state, setProject, selectedSources } from "./state.js"
import { bindSceneEvents, renderScenes } from "./scenes.js"
import { bindLibrary, fillLibraryScenes, refreshLibrary } from "./library.js"
import { bindSettings, loadSettings } from "./settings.js"

const $ = selector => document.querySelector(selector)
let toastTimer = null
let pendingUploadTags = ""
let activeStep = 1
let previewProjectId = null

function notify(message, error = false) {
  const toast = $("#toast")
  toast.textContent = message
  toast.classList.remove("hidden", "error")
  if (error) toast.classList.add("error")
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => toast.classList.add("hidden"), error ? 7000 : 3500)
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach(x =>
    x.classList.toggle("active", x.dataset.tab === name))
  document.querySelectorAll(".tab-panel").forEach(x => x.classList.add("hidden"))
  $(`#${name}-panel`).classList.remove("hidden")
}

async function openLibrary(sceneId = "", query = "") {
  activateTab("library")
  $("#library-query").value = query || ""
  fillLibraryScenes()
  if (sceneId) $("#library-scene").value = sceneId
  await refreshLibrary(query)
}

function showStep(step) {
  activeStep = Math.min(5, Math.max(1, Number(step) || 1))
  document.querySelectorAll(".workflow-step").forEach(section =>
    section.classList.toggle("hidden", Number(section.dataset.step) !== activeStep))
  document.querySelectorAll(".wizard-step").forEach(button => {
    const number = Number(button.dataset.stepTarget)
    button.classList.toggle("active", number === activeStep)
    button.classList.toggle("done", number < activeStep)
  })
  activateTab("work")
  window.scrollTo({ top: 0, behavior: "smooth" })
}

function inferredStep(project) {
  if (!project?.script?.trim()) return 1
  if (!project.scenes?.length || project.scenes.every(x => x.end <= x.start)) return 2
  if (project.scenes.some(x => !x.selected_asset)) return 3
  return 4
}

function resetInlinePreview() {
  previewProjectId = null
  const video = $("#editor-preview")
  video.pause()
  video.removeAttribute("src")
  video.classList.add("hidden")
  $("#preview-placeholder").classList.remove("hidden")
  $("#open-preview").classList.add("disabled")
}

function showInlinePreview(url) {
  const video = $("#editor-preview")
  video.src = url
  video.classList.remove("hidden")
  $("#preview-placeholder").classList.add("hidden")
  $("#open-preview").href = url
  $("#open-preview").classList.remove("disabled")
  video.load()
}

function renderProjects() {
  $("#project-list").innerHTML = state.projects.map(project => `
    <button class="project-item ${state.project?.id === project.id ? "active" : ""}"
      data-project="${project.id}">${project.name}</button>`).join("")
  $("#project-manager-summary").textContent = state.project
    ? `專案管理｜${state.project.name}` : "專案管理"
}

function renderEditTimeline() {
  const root = $("#edit-timeline")
  const p = state.project
  if (!p?.scenes?.length) {
    root.innerHTML = '<p class="hint">產生旁白時間碼後，這裡會顯示成片時間條。</p>'
    return
  }
  const total = p.scenes.reduce((sum, scene) => sum + Math.max(0.1, scene.end - scene.start), 0)
  const blocks = p.scenes.map(scene => {
    const duration = Math.max(0.1, scene.end - scene.start)
    const width = Math.max(6, duration / total * 100)
    const trans = scene.transition === "fade" ? " · 淡化" : ""
    return `<div class="timeline-scene" style="flex-basis:${width}%"
      title="${scene.id} ${duration.toFixed(1)} 秒${trans}">
      <strong>${scene.id}</strong><span>${duration.toFixed(1)}s</span>
    </div>`
  }).join("")
  root.innerHTML = `
    <div class="timeline-ruler"><span>0:00</span><span>${total.toFixed(1)} 秒</span></div>
    <div class="timeline-track">${blocks}</div>
    <div class="timeline-audio ${p.bgm_path ? "has-bgm" : ""}">
      <span>旁白</span><div class="audio-line"></div>
    </div>
    <div class="timeline-audio ${p.bgm_path ? "has-bgm" : ""}">
      <span>BGM</span><div class="audio-line bgm-line">${p.bgm_path ? "已加入背景音樂" : "尚未加入"}</div>
    </div>`
}

function renderProject() {
  const p = state.project
  $("#project-title").textContent = p?.name || "請建立專案"
  $("#project-meta").textContent = p ? `${p.scenes.length} 個 Scene · ${p.width}×${p.height}` : ""
  if (p) $("#project-format").value = p.width >= p.height ? "16:9" : "9:16"
  $("#script").value = p?.script || ""
  $("#voice").value = p?.voice || "zh-TW-YunJheNeural"
  $("#rate").value = p?.rate || "+0%"
  $("#pitch").value = p?.pitch || "+0Hz"
  $("#rhythm").value = p?.rhythm || "natural"
  const volume = Math.round((p?.bgm_volume ?? 0.18) * 100)
  $("#bgm-volume").value = volume
  $("#bgm-volume-value").textContent = `${volume}%`
  $("#bgm-ducking").checked = p?.bgm_ducking ?? true
  $("#bgm-status").textContent = p?.bgm_path ? "BGM 已加入，可直接預聽" : "尚未加入 BGM"
  $("#remove-bgm").disabled = !p?.bgm_path
  const player = $("#bgm-player")
  if (p?.bgm_path) {
    player.src = api.bgmUrl(p.id)
    player.classList.remove("hidden")
  } else {
    player.removeAttribute("src")
    player.classList.add("hidden")
  }
  renderProjects(); renderScenes(); fillLibraryScenes(); renderEditTimeline()
}

async function loadProjects(selectFirst = true) {
  state.projects = await api.projects()
  if (selectFirst && !state.project && state.projects.length) {
    await selectProject(state.projects[0].id); return
  }
  renderProject()
}

async function selectProject(id) {
  setProject(await api.project(id))
  resetInlinePreview()
  activeStep = inferredStep(state.project)
  renderProject()
  showStep(activeStep)
}

async function refreshProject(fetch = true) {
  if (!state.project) return
  if (fetch) state.project = await api.project(state.project.id)
  state.projects = state.projects.map(p => p.id === state.project.id ? state.project : p)
  renderProject()
}

function needProject() {
  if (state.project) return true
  notify("請先建立或選擇專案", true); return false
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", async () => {
    activateTab(button.dataset.tab)
    if (button.dataset.tab === "library") await refreshLibrary()
  }))
}

function bindWizard() {
  document.querySelectorAll("[data-step-target], [data-go-step]").forEach(button => {
    button.addEventListener("click", () =>
      showStep(button.dataset.stepTarget || button.dataset.goStep))
  })
}


function bindProjectActions() {
  $("#create-project").addEventListener("click", async () => {
    const name = $("#new-project-name").value.trim() || "未命名專案"
    try {
      const project = await api.createProject(name)
      state.projects.push(project); setProject(project)
      $("#new-project-name").value = ""
      resetInlinePreview(); activeStep = 1; renderProject(); showStep(1)
      notify("專案已建立")
    } catch (err) { notify(err.message, true) }
  })
  $("#project-list").addEventListener("click", async event => {
    const button = event.target.closest("[data-project]")
    if (!button) return
    try { await selectProject(button.dataset.project); activateTab("work") }
    catch (err) { notify(err.message, true) }
  })
  $("#rename-project").addEventListener("click", async () => {
    if (!needProject()) return
    const name = prompt("新的專案名稱", state.project.name)
    if (!name?.trim()) return
    try {
      state.project = await api.renameProject(state.project.id, name.trim())
      await loadProjects(false); renderProject(); notify("專案已重新命名")
    } catch (err) { notify(err.message, true) }
  })
  $("#delete-project").addEventListener("click", async () => {
    if (!needProject()) return
    if (!confirm(`確定刪除專案「${state.project.name}」？全域素材庫不會刪除。`)) return
    try {
      await api.deleteProject(state.project.id)
      setProject(null); await loadProjects(true)
      notify("專案已刪除")
    } catch (err) { notify(err.message, true) }
  })
}

function bindSideMenu() {
  $("#side-search-external").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      notify("正在搜尋所有 Scene 的新外部素材…")
      state.results = await api.searchExternalAll(state.project.id, selectedSources())
      renderScenes(); showStep(3)
      const count = Object.values(state.results).reduce((sum, x) => sum + x.length, 0)
      notify(`外部搜尋完成：${count} 個尚未下載的候選素材`)
    } catch (err) { notify(err.message, true) }
  })
  $("#global-upload").addEventListener("change", async event => {
    const files = [...(event.target.files || [])]
    if (!files.length) return
    try {
      pendingUploadTags = prompt("自訂標籤（可留空，多個用逗號分隔）", "") ?? ""
      notify(`正在加入 ${files.length} 個本機素材…`)
      for (const file of files) await api.uploadLibrary(file, pendingUploadTags)
      event.target.value = ""; await refreshLibrary()
      notify("本機素材已加入全域素材庫")
    } catch (err) { notify(err.message, true) }
  })
}

function renderPreflight(report) {
  const box = $("#preflight-result")
  box.classList.remove("hidden", "preflight-ok", "preflight-bad")
  if (report.ready) {
    box.classList.add("preflight-ok")
    box.innerHTML = `<strong>✓ 可以輸出</strong><span> ${report.scene_count} 幕的素材、時間碼、旁白都完整。</span>`
    return
  }
  box.classList.add("preflight-bad")
  const rows = report.issues.map(item =>
    `<li><strong>${item.scene_id}</strong>：缺 ${item.missing.join("、")}</li>`
  ).join("")
  const projectRows = report.project_issues.map(item => `<li>${item}</li>`).join("")
  box.innerHTML = `
    <strong>輸出前還有缺漏</strong>
    <div class="preflight-counts">
      沒素材 ${report.counts["素材"]} 幕 ·
      沒時間碼 ${report.counts["時間碼"]} 幕 ·
      沒旁白 ${report.counts["旁白"]} 幕
    </div>
    <ul>${rows}${projectRows}</ul>`
}

async function runPreflight() {
  if (!needProject()) return null
  const report = await api.preflight(state.project.id)
  renderPreflight(report)
  return report
}

function bindWorkflow() {
  $("#project-format").addEventListener("change", async () => {
    if (!needProject()) return
    try {
      state.project = await api.setFormat(state.project.id, $("#project-format").value)
      state.results = {}; await refreshProject(false)
      notify("畫面比例已更新；素材方向會自動匹配")
    } catch (err) { notify(err.message, true) }
  })
  $("#split-script").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      setProject(await api.setScript(state.project.id, $("#script").value))
      renderProject(); showStep(2)
      notify(`已切成 ${state.project.scenes.length} 個 Scene`)
    } catch (err) { notify(err.message, true) }
  })
  $("#make-tts").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      notify("正在產生旁白與時間碼…")
      state.project = await api.tts(
        state.project.id, $("#voice").value, $("#rate").value,
        $("#pitch").value, $("#rhythm").value
      )
      await refreshProject(false); showStep(3); notify("旁白與時間碼完成")
    } catch (err) { notify(err.message, true) }
  })
  $("#bgm-upload").addEventListener("change", async event => {
    if (!needProject()) return
    const file = event.target.files?.[0]
    if (!file) return
    try {
      notify("正在加入 BGM…")
      state.project = await api.uploadBgm(state.project.id, file)
      event.target.value = ""
      await refreshProject(false)
      notify("BGM 已加入")
    } catch (err) { notify(err.message, true) }
  })
  $("#bgm-volume").addEventListener("input", event => {
    $("#bgm-volume-value").textContent = `${event.target.value}%`
  })
  $("#bgm-volume").addEventListener("change", async () => {
    if (!needProject()) return
    try {
      state.project = await api.saveBgm(
        state.project.id,
        Number($("#bgm-volume").value) / 100,
        $("#bgm-ducking").checked,
      )
      await refreshProject(false)
      notify("BGM 音量已更新")
    } catch (err) { notify(err.message, true) }
  })
  $("#bgm-ducking").addEventListener("change", async () => {
    if (!needProject()) return
    try {
      state.project = await api.saveBgm(
        state.project.id,
        Number($("#bgm-volume").value) / 100,
        $("#bgm-ducking").checked,
      )
      await refreshProject(false)
      notify("BGM 自動壓低設定已更新")
    } catch (err) { notify(err.message, true) }
  })
  $("#remove-bgm").addEventListener("click", async () => {
    if (!needProject() || !state.project.bgm_path) return
    try {
      state.project = await api.removeBgm(state.project.id)
      await refreshProject(false)
      notify("BGM 已移除")
    } catch (err) { notify(err.message, true) }
  })
  $("#search-all").addEventListener("click", async () => {
    if (!needProject()) return
    const queries = $("#bulk-queries").value.split(/\r?\n/).map(x => x.trim()).filter(Boolean)
    if (!queries.length) { notify("請貼入素材搜尋詞", true); return }
    try {
      notify("正在套用搜尋詞…")
      state.project = await api.setQueries(state.project.id, queries)
      state.results = await api.searchAll(state.project.id, selectedSources())
      renderProject()
      notify("搜尋完成；每幕候選素材已收合，可自行展開")
    } catch (err) { notify(err.message, true) }
  })
  $("#preflight-check").addEventListener("click", async () => {
    try {
      const report = await runPreflight()
      if (report) notify(report.ready ? "輸出前檢查通過" : "已列出缺漏 Scene", !report.ready)
    } catch (err) { notify(err.message, true) }
  })
  $("#make-preview").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      const report = await runPreflight()
      if (!report?.ready) {
        notify("還有 Scene 缺素材，請先回到第 3 步補齊", true)
        return
      }
      notify("正在更新成片預覽…")
      await api.renderFinal(state.project.id)
      const url = api.finalUrl(state.project.id)
      previewProjectId = state.project.id
      showInlinePreview(url)
      $("#download-final").href = url
      $("#download-final").classList.remove("disabled")
      notify("預覽已更新")
    } catch (err) { notify(err.message, true) }
  })
  $("#export-final").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      const report = await runPreflight()
      if (!report?.ready) {
        notify("輸出前檢查未通過，請先補齊上方列出的 Scene", true)
        return
      }
      notify("正在導出正式成片…")
      await api.renderFinal(state.project.id)
      $("#download-final").href = api.finalUrl(state.project.id)
      $("#download-final").classList.remove("disabled")
      notify("正式成片完成，可以下載")
    } catch (err) { notify(err.message, true) }
  })
  $("#export-jianying").addEventListener("click", async () => {
    if (!needProject()) return
    try {
      const report = await runPreflight()
      if (!report?.ready) {
        notify("輸出前檢查未通過，請先補齊上方列出的 Scene", true)
        return
      }
      notify("正在建立剪映草稿…")
      const result = await api.exportJianying(state.project.id, state.project.name)
      notify(`剪映草稿「${result.draft_name}」已建立`)
    } catch (err) { notify(err.message, true) }
  })
}

async function start() {
  bindTabs(); bindWizard(); bindProjectActions(); bindSideMenu(); bindWorkflow()
  bindSceneEvents({ notify, refreshProject, refreshLibrary, openLibrary })
  bindLibrary({ notify, refreshProject })
  bindSettings({ notify })
  try { await Promise.all([loadSettings(), loadProjects()]) }
  catch (err) { notify(err.message, true) }
}

start()
