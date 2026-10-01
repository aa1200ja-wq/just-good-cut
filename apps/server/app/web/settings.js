import { api } from "./api.js"
import { state } from "./state.js"

function renderStatus() {
  const s = state.settings
  if (!s) return
  document.querySelector("#api-status").textContent =
    `Pexels：${s.pexels_configured ? "已設定" : "未設定"} ｜ Pixabay：${s.pixabay_configured ? "已設定" : "未設定"}`
  document.querySelector("#jianying-dir").value = s.jianying_draft_dir || ""
  document.querySelector("#material-library-dir").value = s.material_library_dir || ""
  document.querySelector("#material-library-status").textContent =
    `素材檔：${s.assets_dir || ""}`
}

export async function loadSettings() {
  state.settings = await api.settings()
  renderStatus()
}

export function bindSettings({ notify }) {
  document.querySelector("#save-api-keys").addEventListener("click", async () => {
    const pexels = document.querySelector("#pexels-key").value.trim()
    const pixabay = document.querySelector("#pixabay-key").value.trim()
    const body = {}
    if (pexels) body.pexels_api_key = pexels
    if (pixabay) body.pixabay_api_key = pixabay
    try {
      state.settings = await api.saveSettings(body)
      document.querySelector("#pexels-key").value = ""
      document.querySelector("#pixabay-key").value = ""
      renderStatus(); notify("API Key 已儲存在這台電腦")
    } catch (err) { notify(err.message, true) }
  })

  document.querySelector("#detect-jianying").addEventListener("click", async () => {
    try {
      const result = await api.detectJianying()
      if (!result.paths.length) {
        notify("沒有自動找到草稿位置，請從剪映全域設定複製路徑", true); return
      }
      document.querySelector("#jianying-dir").value = result.paths[0]
      notify("已找到剪映草稿資料夾")
    } catch (err) { notify(err.message, true) }
  })

  document.querySelector("#save-jianying").addEventListener("click", async () => {
    const path = document.querySelector("#jianying-dir").value.trim()
    try {
      state.settings = await api.saveSettings({ jianying_draft_dir: path })
      renderStatus(); notify("剪映草稿位置已儲存")
    } catch (err) { notify(err.message, true) }
  })

  document.querySelector("#save-material-library").addEventListener("click", async () => {
    const path = document.querySelector("#material-library-dir").value.trim()
    if (!path) { notify("請輸入素材庫資料夾", true); return }
    try {
      notify("正在搬移素材庫，請不要關閉程式…")
      state.settings = await api.saveSettings({ material_library_dir: path })
      renderStatus()
      notify("素材庫位置已更新，之後所有專案共用這個位置")
    } catch (err) { notify(err.message, true) }
  })
}
