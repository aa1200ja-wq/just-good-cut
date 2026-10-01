# 揪好剪 JustGoodCut

本機執行的 B-roll 自動剪輯工具。從旁白腳本切 Scene、產生配音與時間碼、搜尋或加入素材，到最後直接輸出 MP4。

## MVP 功能

- 旁白腳本自動切 Scene
- Edge-TTS 台灣中文 3 個聲音
  - 台灣男聲｜雲哲
  - 台灣女聲｜曉臻
  - 台灣女聲｜曉雨
- Scene 素材搜尋、素材庫與本機素材
- 每幕素材開始／結束時間
- 直接切／淡化轉場
- BGM 上傳、音量調整
- 旁白出現時自動降低 BGM
- 粗剪預覽 MP4
- 正式成片 MP4
- 保留剪映草稿輸出作為備用

## Windows 免安裝版

GitHub Actions 成功後會產生：

`JustGoodCut-Windows.zip`

解壓縮後直接執行：

`JustGoodCut.exe`

Python、FFmpeg 與必要依賴會一起打包，不需要另外安裝。

## 本機資料

Windows 預設資料位置：

`%LOCALAPPDATA%\JustGoodCut`

因此不會與原本的 BrollWorkflow 共用專案或素材資料。

可使用環境變數 `JUST_GOOD_CUT_DATA_DIR` 指定其他位置；舊的 `BROLL_DATA_DIR` 仍保留相容。

## 開發模式

```bash
pip install -r apps/server/requirements.txt
python run_local.py
```

預設會啟動本機網頁介面。
