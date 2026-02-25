# -*- coding: utf-8 -*-
"""
Qwen-ASR-GUI — 桌面語音辨識應用
"""
import time
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
        self.geometry("900x750")
        self.minsize(750, 650)

        # 狀態
        self._result = None        # dict: merged, raw_text, sentences
        self._running = False
        self._audio_path = None

        # 時間追蹤
        self._start_time = None
        self._last_percent = 0

        # 語者名稱對應表（原始名稱 → 自訂名稱）
        self._speaker_names = {}

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
        result_outer = ctk.CTkFrame(self)
        result_outer.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")
        result_outer.grid_columnconfigure(0, weight=1)
        result_outer.grid_rowconfigure(1, weight=1)

        # 結果標題 + 模式切換
        result_header = ctk.CTkFrame(result_outer, fg_color="transparent")
        result_header.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        result_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(result_header, text="📝 辨識結果", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=(4, 12), sticky="w"
        )

        # 檢視模式切換（語者分離 / 單句結果 / 原始ASR）
        self.view_mode_var = ctk.StringVar(value="語者分離")
        self.view_mode_btn = ctk.CTkSegmentedButton(
            result_header,
            values=["語者分離", "單句結果", "原始ASR"],
            variable=self.view_mode_var,
            command=self._on_view_mode_changed,
        )
        self.view_mode_btn.grid(row=0, column=1, sticky="e")

        # 結果內容容器
        self.result_container = ctk.CTkFrame(result_outer)
        self.result_container.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.result_container.grid_columnconfigure(0, weight=1)
        self.result_container.grid_rowconfigure(0, weight=1)

        # 預設顯示文字框
        self.result_text = ctk.CTkTextbox(self.result_container, font=ctk.CTkFont(size=13), wrap="word")
        self.result_text.grid(row=0, column=0, sticky="nsew")

        # 語者分離滾動區域（初始隱藏）
        self.speaker_scroll = None

        # ── 底部：進度 + 按鈕 ──
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        # 進度條
        progress_row = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        progress_row.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 8))
        progress_row.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_row)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(progress_row, text="就緒", font=ctk.CTkFont(size=12), width=320)
        self.status_label.grid(row=0, column=1)

        # 按鈕列
        self.run_btn = ctk.CTkButton(
            bottom_frame, text="▶ 開始辨識", width=140,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_run,
        )
        self.run_btn.grid(row=1, column=0, padx=4, sticky="e")

        # TXT 匯出下拉選單
        self.txt_export_var = ctk.StringVar(value="📄 匯出 TXT")
        ctk.CTkOptionMenu(
            bottom_frame,
            variable=self.txt_export_var,
            values=["合併結果 TXT", "原始文字 TXT", "單句字幕 TXT"],
            command=self._on_txt_export,
            width=140,
            fg_color="#2b6e3f",
            button_color="#2b6e3f",
            button_hover_color="#367d4a",
        ).grid(row=1, column=1, padx=4)

        # SRT 匯出下拉選單
        self.srt_export_var = ctk.StringVar(value="🎬 匯出 SRT")
        ctk.CTkOptionMenu(
            bottom_frame,
            variable=self.srt_export_var,
            values=["合併 SRT", "單句字幕 SRT"],
            command=self._on_srt_export,
            width=140,
            fg_color="#2b5e8e",
            button_color="#2b5e8e",
            button_hover_color="#366ea0",
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
        self._last_percent = percent

        # 計算已用時間和預估剩餘時間
        if self._start_time and 0 < percent < 100:
            elapsed = time.time() - self._start_time
            elapsed_str = self._format_duration(elapsed)

            if percent > 2:
                estimated_total = elapsed / (percent / 100.0)
                remaining = estimated_total - elapsed
                remaining_str = self._format_duration(remaining)
                time_info = f"  ⏱ 已用 {elapsed_str} / 預計剩餘 {remaining_str}"
            else:
                time_info = f"  ⏱ 已用 {elapsed_str}"

            self.status_label.configure(text=message + time_info)
        else:
            self.status_label.configure(text=message)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """格式化秒數為 M:SS"""
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def _start_run(self):
        path = self.file_entry.get().strip()
        if not path or not Path(path).exists():
            messagebox.showwarning("提示", "請先選擇有效的音訊檔案")
            return

        if self._running:
            return

        self._running = True
        self._audio_path = path
        self._start_time = time.time()
        self._last_percent = 0
        self.run_btn.configure(state="disabled", text="⏳ 處理中...")
        self._clear_result_area()
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

            result = engine.run(
                self._audio_path,
                language=language,
                enable_diarization=enable_diar,
                to_traditional=to_trad,
            )

            self._result = result

            # 建構語者名稱對應表
            self._speaker_names = {}
            for seg in result["merged"]:
                spk = seg.get("speaker", "")
                if spk and spk not in self._speaker_names:
                    self._speaker_names[spk] = spk

            self.after(0, self._display_current_view)

        except Exception as e:
            self.after(0, self._on_error, str(e))
        finally:
            self.after(0, self._on_done)

    # ============================================
    # 結果顯示
    # ============================================

    def _clear_result_area(self):
        """清除結果區域所有子元件"""
        for widget in self.result_container.winfo_children():
            widget.destroy()

    def _on_view_mode_changed(self, value):
        """切換檢視模式"""
        if self._result:
            self._display_current_view()

    def _display_current_view(self):
        """依據當前模式顯示結果"""
        if not self._result:
            return

        mode = self.view_mode_var.get()
        self._clear_result_area()

        if mode == "語者分離":
            self._display_speaker_view()
        elif mode == "單句結果":
            self._display_sentence_view()
        elif mode == "原始ASR":
            self._display_raw_view()

        merged = self._result["merged"]
        sentences = self._result["sentences"]
        self._on_progress(100, f"完成！合併 {len(merged)} 段, 分句 {len(sentences)} 句")

    def _display_speaker_view(self):
        """語者分離模式：依語者分區塊"""
        segments = self._result["merged"]

        scroll = ctk.CTkScrollableFrame(self.result_container)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._speaker_entries = {}  # 追蹤語者名稱輸入框

        for i, seg in enumerate(segments):
            speaker = seg.get("speaker", "")
            start = ASREngine.format_time(seg["start"])
            end = ASREngine.format_time(seg["end"])
            text = seg["text"]

            # 區塊框架
            block = ctk.CTkFrame(scroll, border_width=1, border_color="#444444")
            block.grid(row=i, column=0, padx=4, pady=4, sticky="ew")
            block.grid_columnconfigure(1, weight=1)

            if speaker:
                # 語者名稱（可編輯）
                display_name = self._speaker_names.get(speaker, speaker)
                spk_entry = ctk.CTkEntry(
                    block, width=140,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color="#1a3a5c",
                    border_color="#2b5e8e",
                )
                spk_entry.insert(0, display_name)
                spk_entry.grid(row=0, column=0, padx=(8, 4), pady=(8, 2), sticky="w")

                # 綁定修改事件
                original_speaker = speaker
                spk_entry.bind("<FocusOut>", lambda e, orig=original_speaker, entry=spk_entry: self._on_speaker_renamed(orig, entry))
                spk_entry.bind("<Return>", lambda e, orig=original_speaker, entry=spk_entry: self._on_speaker_renamed(orig, entry))

                if original_speaker not in self._speaker_entries:
                    self._speaker_entries[original_speaker] = []
                self._speaker_entries[original_speaker].append(spk_entry)

            # 時間段
            time_label = ctk.CTkLabel(
                block, text=f"⏱ {start} → {end}",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            )
            time_label.grid(row=0, column=1, padx=4, pady=(8, 2), sticky="w")

            # 文字內容（可編輯）
            text_box = ctk.CTkTextbox(block, font=ctk.CTkFont(size=13), wrap="word", height=60)
            text_box.grid(row=1, column=0, columnspan=2, padx=8, pady=(2, 8), sticky="ew")
            text_box.insert("1.0", text)

    def _on_speaker_renamed(self, original_speaker: str, source_entry):
        """語者名稱修改後同步更新所有同名語者"""
        new_name = source_entry.get().strip()
        if not new_name:
            return

        self._speaker_names[original_speaker] = new_name

        # 同步更新所有相同原始語者的輸入框
        if original_speaker in self._speaker_entries:
            for entry in self._speaker_entries[original_speaker]:
                if entry is not source_entry:
                    entry.delete(0, "end")
                    entry.insert(0, new_name)

    def _display_sentence_view(self):
        """單句結果模式：時間段 + 文字"""
        sentences = self._result["sentences"]

        scroll = ctk.CTkScrollableFrame(self.result_container)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, sent in enumerate(sentences):
            start = ASREngine.format_time(sent["start"])
            end = ASREngine.format_time(sent["end"])

            block = ctk.CTkFrame(scroll, fg_color="transparent")
            block.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
            block.grid_columnconfigure(1, weight=1)

            # 時間段
            time_label = ctk.CTkLabel(
                block, text=f"⏱ {start} → {end}",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
                width=180,
            )
            time_label.grid(row=0, column=0, padx=(4, 8), sticky="w")

            # 文字（可編輯）
            text_entry = ctk.CTkEntry(block, font=ctk.CTkFont(size=13))
            text_entry.insert(0, sent["text"])
            text_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))

    def _display_raw_view(self):
        """原始 ASR 模式：純文字"""
        text_box = ctk.CTkTextbox(self.result_container, font=ctk.CTkFont(size=13), wrap="word")
        text_box.grid(row=0, column=0, sticky="nsew")
        text_box.insert("1.0", self._result["raw_text"])

    # ============================================
    # 錯誤處理
    # ============================================

    def _on_error(self, error_msg: str):
        messagebox.showerror("錯誤", f"處理失敗：\n{error_msg}")
        self._on_progress(0, "發生錯誤")

    def _on_done(self):
        self._running = False
        self._start_time = None
        self.run_btn.configure(state="normal", text="▶ 開始辨識")

    # ============================================
    # 匯出
    # ============================================

    def _on_txt_export(self, choice):
        """TXT 匯出下拉選單回呼"""
        # 重置顯示文字
        self.txt_export_var.set("📄 匯出 TXT")

        if not self._result:
            messagebox.showinfo("提示", "尚無辨識結果可匯出")
            return

        if choice == "合併結果 TXT":
            self._export_merged_txt()
        elif choice == "原始文字 TXT":
            self._export_raw_txt()
        elif choice == "單句字幕 TXT":
            self._export_subtitle_txt()

    def _on_srt_export(self, choice):
        """SRT 匯出下拉選單回呼"""
        # 重置顯示文字
        self.srt_export_var.set("🎬 匯出 SRT")

        if not self._result:
            messagebox.showinfo("提示", "尚無辨識結果可匯出")
            return

        if choice == "合併 SRT":
            self._export_merged_srt()
        elif choice == "單句字幕 SRT":
            self._export_subtitle_srt()

    def _export_merged_txt(self):
        """匯出合併結果 TXT"""
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文字檔", "*.txt")],
            title="匯出合併結果 TXT",
        )
        if path:
            # 套用語者名稱修改
            segments = self._get_renamed_segments()
            ASREngine.export_txt(segments, path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _export_raw_txt(self):
        """匯出原始文字 TXT"""
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文字檔", "*.txt")],
            title="匯出原始文字 TXT",
        )
        if path:
            ASREngine.export_raw_txt(self._result["raw_text"], path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _export_subtitle_txt(self):
        """匯出單句字幕 TXT"""
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文字檔", "*.txt")],
            title="匯出單句字幕 TXT",
        )
        if path:
            ASREngine.export_subtitle_txt(self._result["sentences"], path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _export_merged_srt(self):
        """匯出合併 SRT"""
        path = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt")],
            title="匯出合併 SRT",
        )
        if path:
            segments = self._get_renamed_segments()
            ASREngine.export_srt(segments, path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _export_subtitle_srt(self):
        """匯出單句字幕 SRT"""
        path = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt")],
            title="匯出單句字幕 SRT",
        )
        if path:
            ASREngine.export_subtitle_srt(self._result["sentences"], path)
            messagebox.showinfo("成功", f"已匯出至\n{path}")

    def _get_renamed_segments(self):
        """套用語者名稱修改後的 segments"""
        segments = []
        for seg in self._result["merged"]:
            new_seg = seg.copy()
            original_speaker = seg.get("speaker", "")
            if original_speaker in self._speaker_names:
                new_seg["speaker"] = self._speaker_names[original_speaker]
            segments.append(new_seg)
        return segments


# ============================================
# 啟動
# ============================================

if __name__ == "__main__":
    app = QwenASRApp()
    app.mainloop()
