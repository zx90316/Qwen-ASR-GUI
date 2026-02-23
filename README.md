# Qwen-ASR-GUI

基於 [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) 的桌面語音辨識工具，支援語者分離與繁體中文轉換。

## ✨ 功能

- 🎙️ **語音辨識** — Qwen3 ASR 1.7B / 0.6B 模型
- 👥 **語者分離** — pyannote.audio 自動識別多位說話者
- 🔤 **繁體中文** — 自動轉換為臺灣用語
- 📊 **長音訊分段** — 靜音偵測自動切分，支援任意長度音訊
- 💻 **CPU 支援** — 0.6B 模型可在無 GPU 環境運行
- 📄 **匯出** — TXT 文字檔 / SRT 字幕檔

## 📋 安裝

```bash
# 建立虛擬環境
python -m venv .venv
.venv\Scripts\activate

# 安裝依賴（GPU 版本）
pip install -r requirements.txt

# CPU 版本請修改 requirements.txt 中的 --extra-index-url
```

## 🚀 使用

```bash
python main.py
```

## 🖥️ 系統需求

| 模式 | 模型 | VRAM / RAM |
|------|------|-----------|
| GPU | 1.7B (高品質) | 6 GB VRAM |
| GPU | 0.6B (輕量) | 3 GB VRAM |
| CPU | 0.6B (輕量) | 8 GB RAM |

## 📁 專案結構

```
├── main.py           # GUI 入口
├── asr_engine.py     # ASR 核心引擎
├── audio_utils.py    # 音訊處理工具
├── config.py         # 配置
└── requirements.txt  # 依賴
```

## 授權

MIT License
