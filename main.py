# -*- coding: utf-8 -*-
"""
Qwen-ASR-GUI — 桌面語音辨識應用
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

from config import MODELS, DEFAULT_MODEL, LANGUAGES, DEFAULT_LANGUAGE, RESULT_DIR
from asr_engine import ASREngine, detect_device


# ============================================
# 主題設定
# ============================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class QwenASRApp(ctk.CTk):
    """主應用視窗"""

    def __init__(self):
        super().__init__()

        self.title("Qwen ASR — 語音辨識工具")
        self.geometry("900x700")
        self.minsize(750, 600)

        # 狀態
        self._segments = []
        self._running = False
        self._audio_path = None

        self._build_ui()

    # ============================================
    # UI 建構
    # ============================================

    def _build_ui(self):
        # 主框架
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── 頂部：檔案選擇 ──
        file_frame = ctk.CTkFrame(self, fg_color="transparent")
        file_frame.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        file_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(file_frame, text="🎵 音訊檔案", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=(0, 8)
        )

        self.file_entry = ctk.CTkEntry(file_frame, placeholder_text="選擇或拖放音訊檔案...")
        self.file_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(file_frame, text="瀏覽", width=80, command=self._browse_file).grid(
            row=0, column=2
        )

        # ── 設定面板 ──
        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        settings_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 模型選擇
        ctk.CTkLabel(settings_frame, text="模型").grid(row=0, column=0, padx=8, pady=(8, 0))
        self.model_var = ctk.StringVar(value=DEFAULT_MODEL)
        ctk.CTkOptionMenu(
            settings_frame, variable=self.model_var, values=list(MODELS.keys()), width=160
        ).grid(row=1, column=0, padx=8, pady=(4, 8))

        # 運算裝置
        device_info = detect_device()
        ctk.CTkLabel(settings_frame, text="裝置").grid(row=0, column=1, padx=8, pady=(8, 0))
        device_options = ["自動偵測"]
        if "cuda" in device_info["device"]:
            device_options.append("CUDA GPU")
        device_options.append("CPU")
        self.device_var = ctk.StringVar(value="自動偵測")
        ctk.CTkOptionMenu(
            settings_frame, variable=self.device_var, values=device_options, width=140
        ).grid(row=1, column=1, padx=8, pady=(4, 8))

        # 語言
        ctk.CTkLabel(settings_frame, text="語言").grid(row=0, column=2, padx=8, pady=(8, 0))
        self.lang_var = ctk.StringVar(value=DEFAULT_LANGUAGE)
        ctk.CTkOptionMenu(
            settings_frame, variable=self.lang_var, values=list(LANGUAGES.keys()), width=120
        ).grid(row=1, column=2, padx=8, pady=(4, 8))

        # 選項
        opts_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        opts_frame.grid(row=0, column=3, rowspan=2, padx=8, pady=8)

        self.diarize_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_frame, text="語者分離", variable=self.diarize_var).pack(anchor="w", pady=2)

        self.traditional_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_frame, text="繁體中文", variable=self.traditional_var).pack(anchor="w", pady=2)

        # ── 結果區域 ──
        result_frame = ctk.CTkFrame(self)
        result_frame.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(result_frame, text="📝 辨識結果", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(8, 4), sticky="w"
        )

        self.result_text = ctk.CTkTextbox(result_frame, font=ctk.CTkFont(size=13), wrap="word")
        self.result_text.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")

        # ── 底部：進度 + 按鈕 ──
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        # 進度條
        progress_row = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        progress_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        progress_row.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_row)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(progress_row, text="就緒", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=1, minsize=200)

        # 按鈕
        self.run_btn = ctk.CTkButton(
            bottom_frame, text="▶ 開始辨識", width=140,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_run,
        )
        self.run_btn.grid(row=1, column=0, padx=4, sticky="e")

        ctk.CTkButton(
            bottom_frame, text="📄 匯出 TXT", width=110, command=self._export_txt,
            fg_color="#2b6e3f", hover_color="#367d4a",
        ).grid(row=1, column=1, padx=4)

        ctk.CTkButton(
            bottom_frame, text="🎬 匯出 SRT", width=110, command=self._export_srt,
            fg_color="#2b5e8e", hover_color="#366ea0",
        ).grid(row=1, column=2, padx=4)

    # ============================================
    # 操作
    # ============================================

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="選擇音訊檔案",
            filetypes=[
                ("音訊檔案", "*.mp3 *.wav *.m4a *.flac *.ogg *.wma *.aac *.mp4"),
                ("所有檔案", "*.*"),
            ],
        )
        if path:
            self._audio_path = path
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _get_device(self) -> str:
        val = self.device_var.get()
        if val == "CPU":
            return "cpu"
        elif val == "CUDA GPU":
            return "cuda:0"
        return "auto"

    def _on_progress(self, percent: float, message: str):
        """從背景執行緒更新 GUI（thread-safe）"""
        self.after(0, self._update_progress, percent, message)

    def _update_progress(self, percent: float, message: str):
        self.progress_bar.set(percent / 100.0)
        self.status_label.configure(text=message)

    def _start_run(self):
        path = self.file_entry.get().strip()
        if not path or not Path(path).exists():
            messagebox.showwarning("提示", "請先選擇有效的音訊檔案")
            return

        if self._running:
            return

        self._running = True
        self._audio_path = path
        self.run_btn.configure(state="disabled", text="⏳ 處理中...")
        self.result_text.delete("1.0", "end")
        self.progress_bar.set(0)

        threading.Thread(target=self._run_asr, daemon=True).start()

    def _run_asr(self):
        """背景執行 ASR"""
        try:
            model_key = self.model_var.get()
            model_name = MODELS[model_key]
            device = self._get_device()
            language = LANGUAGES[self.lang_var.get()]
            enable_diar = self.diarize_var.get()
            to_trad = self.traditional_var.get()

            engine = ASREngine(
                model_name=model_name,
                device=device,
                on_progress=self._on_progress,
            )

            segments = engine.run(
                self._audio_path,
                language=language,
                enable_diarization=enable_diar,
                to_traditional=to_trad,
            )

            self._segments = segments
            self.after(0, self._display_results, segments)

        except Exception as e:
            self.after(0, self._on_error, str(e))
        finally:
            self.after(0, self._on_done)

    def _display_results(self, segments):
        """顯示結果到文字框"""
        self.result_text.delete("1.0", "end")
        for seg in segments:
            start = ASREngine.format_time(seg["start"])
            end = ASREngine.format_time(seg["end"])
            speaker = seg.get("speaker", "")
            text = seg["text"]
            if speaker:
                line = f"[{start} → {end}] {speaker}: {text}\n\n"
            else:
                line = f"[{start} → {end}] {text}\n\n"
            self.result_text.insert("end", line)

        self._on_progress(100, f"完成！共 {len(segments)} 個片段")

    def _on_error(self, error_msg: str):
        messagebox.showerror("錯誤", f"處理失敗：\n{error_msg}")
        self._on_progress(0, "發生錯誤")

    def _on_done(self):
        self._running = False
        self.run_btn.configure(state="normal", text="▶ 開始辨識")

    # ============================================
    # 匯出
    # ============================================

    def _export_txt(self):
        if not self._segments:
            messagebox.showinfo("提示", "尚無辨識結果可匯出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文字檔", "*.txt")],
            title="匯出 TXT",
        )
        if path:
            ASREngine.export_txt(self._segments, path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _export_srt(self):
        if not self._segments:
            messagebox.showinfo("提示", "尚無辨識結果可匯出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt")],
            title="匯出 SRT",
        )
        if path:
            ASREngine.export_srt(self._segments, path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")


# ============================================
# 啟動
# ============================================

if __name__ == "__main__":
    app = QwenASRApp()
    app.mainloop()
