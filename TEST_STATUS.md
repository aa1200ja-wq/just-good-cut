# V1 測試狀態

## 已完成

- 腳本依標點切 Scene。
- 手動拆分／合併 Scene。
- Edge-TTS 逐 Scene 配音架構。
- MP3 時長改為 Python 直接讀取，不再依賴系統 ffprobe。
- FFmpeg 改為程式內建 runtime，不要求使用者自行設定 PATH。
- 批次搜尋詞一次貼上並平行搜尋全部 Scene。
- Pexels / Pixabay / Wikimedia Commons 搜尋整合。
- 人工選素材與自行上傳素材。
- 專案素材庫、標籤／搜尋詞索引、跨 Scene 重複使用。
- FFmpeg 粗剪預覽。
- pyJianYingDraft 三軌草稿輸出。
- API Key 與剪映草稿路徑改成網頁內設定。
- Vue / Vite / Node.js 已從正式前端移除。
- 前端改成原生 HTML / CSS / JavaScript，由 FastAPI 同一個網址直接提供。
- 桌機與窄螢幕自適應版面。
- Windows PyInstaller 自動打包工作流程。
- GitHub Actions 會產生 `BrollWorkflow-Windows.zip`。

## 自動測試

- Python compileall。
- Scene 切分。
- 專案 JSON 保存／讀取。
- 素材庫搜尋與跨 Scene 重複使用。
- FFmpeg 缺素材佔位粗剪。
- FastAPI health。
- 最終 HTML 首頁可載入。

## 最後仍需要 Windows 實機總驗收

一次測完整流程，不再逐按鈕驗收：

1. 啟動 Windows 版。
2. 貼完整稿並切 Scene。
3. Edge-TTS 配音與時間碼。
4. 真實 Pexels / Pixabay / Wikimedia 搜尋與下載。
5. 素材庫跨 Scene 套用。
6. 粗剪 MP4。
7. 剪映專業版 6.0.1 開啟新草稿。

只有 Windows 實際剪映開啟結果無法在 GitHub Linux 測試環境代替。
