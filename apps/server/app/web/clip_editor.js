import { api } from "./api.js"
import { state } from "./state.js"

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

function timeLabel(seconds) {
  const value = Math.max(0, Number(seconds) || 0)
  const mins = Math.floor(value / 60)
  const secs = value - mins * 60
  return `${mins}:${secs.toFixed(1).padStart(4, "0")}`
}

export function clipEditorMarkup(scene) {
  if (!scene.selected_asset) {
    return '<p class="hint">先選擇素材後即可剪輯。</p>'
  }

  const assetUrl = api.sceneAssetUrl(state.project.id, scene.id)
  const transition = `
    <label class="clip-transition">接下一幕
      <select data-field="transition">
        <option value="none" ${(scene.transition || "none") === "none" ? "selected" : ""}>直接切</option>
        <option value="fade" ${scene.transition === "fade" ? "selected" : ""}>淡化轉場</option>
      </select>
    </label>`

  if (scene.selected_asset_type === "image") {
    return `
      <details class="scene-edit">
        <summary>畫面設定</summary>
        <div class="image-edit-row">
          <img class="scene-image-preview" src="${assetUrl}" alt="已選圖片" />
          ${transition}
        </div>
      </details>`
  }

  return `
    <details class="scene-edit" data-clip-editor>
      <summary>
        影片剪輯
        <span class="clip-summary" data-clip-summary>讀取影片資訊中…</span>
      </summary>
      <div class="clip-editor-body">
        <video class="clip-preview" data-clip-video src="${assetUrl}"
          controls preload="metadata"></video>

        <div class="clip-time-row">
          <span data-clip-current>0:00.0</span>
          <span>原片長度 <strong data-clip-total>讀取中…</strong></span>
        </div>

        <div class="filmstrip-shell" data-filmstrip-shell>
          <div class="filmstrip" data-filmstrip></div>
          <div class="trim-dim trim-dim-left" data-trim-dim-left></div>
          <div class="trim-dim trim-dim-right" data-trim-dim-right></div>
          <div class="trim-window" data-trim-window>
            <button type="button" class="trim-handle trim-handle-left"
              data-trim-handle="start" aria-label="拖曳影片起點"></button>
            <button type="button" class="trim-handle trim-handle-right"
              data-trim-handle="end" aria-label="拖曳影片終點"></button>
          </div>
        </div>

        <div class="clip-selection-row">
          <span>框選 <strong data-clip-selection>讀取中…</strong></span>
          <div class="clip-buttons">
            <button type="button" class="ghost" data-clip-action="play">▶ 播放框選</button>
            <button type="button" class="ghost" data-clip-action="reset">重設</button>
          </div>
        </div>

        <input data-field="asset_in" type="hidden"
          value="${Number(scene.asset_in || 0).toFixed(3)}" />
        <input data-field="asset_out" type="hidden"
          value="${Number(scene.asset_out || 0).toFixed(3)}" />
        ${transition}
      </div>
    </details>`
}

function fillFilmstrip(details, sceneId, duration) {
  const strip = details.querySelector("[data-filmstrip]")
  if (!strip || strip.dataset.ready) return
  strip.dataset.ready = "1"
  const count = 10
  strip.innerHTML = Array.from({ length: count }, (_, index) => {
    const moment = duration * ((index + 0.5) / count)
    return `<img src="${api.sceneThumbUrl(state.project.id, sceneId, moment)}"
      alt="" loading="lazy" draggable="false" />`
  }).join("")
}

function updateSelection(details, start, end, duration) {
  const startPct = duration ? start / duration * 100 : 0
  const endPct = duration ? end / duration * 100 : 100
  details.querySelector("[data-trim-window]").style.left = `${startPct}%`
  details.querySelector("[data-trim-window]").style.width = `${Math.max(0, endPct - startPct)}%`
  details.querySelector("[data-trim-dim-left]").style.width = `${startPct}%`
  details.querySelector("[data-trim-dim-right]").style.width = `${100 - endPct}%`
  details.querySelector("[data-clip-selection]").textContent =
    `${timeLabel(start)} → ${timeLabel(end)}（${(end - start).toFixed(1)} 秒）`
}

export function initClipEditor(details, card, saveCard, notify) {
  if (details.dataset.initialized === "1") return
  details.dataset.initialized = "1"

  const video = details.querySelector("[data-clip-video]")
  const shell = details.querySelector("[data-filmstrip-shell]")
  const startInput = details.querySelector('[data-field="asset_in"]')
  const endInput = details.querySelector('[data-field="asset_out"]')
  if (!video || !shell || !startInput || !endInput) return

  let duration = 0
  let start = Math.max(0, Number(startInput.value) || 0)
  let end = 0
  let playingSelection = false

  const syncHidden = () => {
    startInput.value = start.toFixed(3)
    endInput.value = end.toFixed(3)
  }

  const refresh = () => {
    updateSelection(details, start, end, duration)
    details.querySelector("[data-clip-summary]").textContent =
      `原片 ${timeLabel(duration)} · 使用 ${timeLabel(start)}–${timeLabel(end)}`
  }

  video.addEventListener("loadedmetadata", () => {
    duration = Number.isFinite(video.duration) ? video.duration : 0
    start = clamp(start, 0, Math.max(0, duration - 0.1))
    const savedEnd = Number(endInput.value) || 0
    const sceneDuration = Math.max(0.1, Number(
      state.project.scenes.find(x => x.id === card.dataset.scene)?.end -
      state.project.scenes.find(x => x.id === card.dataset.scene)?.start
    ) || 0.1)
    end = savedEnd > start
      ? clamp(savedEnd, start + 0.1, duration)
      : clamp(start + sceneDuration, start + 0.1, duration)

    details.querySelector("[data-clip-total]").textContent = timeLabel(duration)
    fillFilmstrip(details, card.dataset.scene, duration)
    refresh()
  })

  video.addEventListener("timeupdate", () => {
    details.querySelector("[data-clip-current]").textContent = timeLabel(video.currentTime)
    if (playingSelection && video.currentTime >= end) {
      video.pause()
      video.currentTime = start
      playingSelection = false
    }
  })

  shell.addEventListener("click", event => {
    if (event.target.closest("[data-trim-handle]") || !duration) return
    const rect = shell.getBoundingClientRect()
    video.currentTime = clamp((event.clientX - rect.left) / rect.width * duration, 0, duration)
  })

  details.querySelectorAll("[data-trim-handle]").forEach(handle => {
    handle.addEventListener("pointerdown", event => {
      event.preventDefault()
      handle.setPointerCapture(event.pointerId)
      const side = handle.dataset.trimHandle

      const move = moveEvent => {
        const rect = shell.getBoundingClientRect()
        const value = clamp(
          (moveEvent.clientX - rect.left) / rect.width * duration,
          0, duration,
        )
        if (side === "start") start = clamp(value, 0, end - 0.1)
        else end = clamp(value, start + 0.1, duration)
        video.currentTime = side === "start" ? start : end
        refresh()
      }

      const up = async upEvent => {
        handle.removeEventListener("pointermove", move)
        handle.removeEventListener("pointerup", up)
        handle.releasePointerCapture(upEvent.pointerId)
        syncHidden()
        try {
          await saveCard(card)
          notify(`${card.dataset.scene} 剪輯範圍已儲存`)
        } catch (err) {
          notify(err.message, true)
        }
      }

      handle.addEventListener("pointermove", move)
      handle.addEventListener("pointerup", up)
    })
  })

  details.querySelector('[data-clip-action="play"]').addEventListener("click", async () => {
    video.currentTime = start
    playingSelection = true
    await video.play()
  })

  details.querySelector('[data-clip-action="reset"]').addEventListener("click", async () => {
    start = 0
    const scene = state.project.scenes.find(x => x.id === card.dataset.scene)
    const sceneDuration = Math.max(0.1, (scene?.end || 0) - (scene?.start || 0))
    end = Math.min(duration, sceneDuration)
    syncHidden(); refresh(); video.currentTime = 0
    try {
      await saveCard(card)
      notify(`${card.dataset.scene} 已重設剪輯範圍`)
    } catch (err) {
      notify(err.message, true)
    }
  })
}
