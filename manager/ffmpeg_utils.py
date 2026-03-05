# -*- coding: utf-8 -*-
"""
FFmpeg 檢查與下載工具
"""
import os
import sys
import shutil
import urllib.request
import zipfile
import threading
from pathlib import Path
from typing import Callable

from manager.config import PROJECT_ROOT


def get_ffmpeg_dir() -> Path:
    """取得預期下載的 FFmpeg 目錄路徑"""
    return PROJECT_ROOT / "ffmpeg-master-latest-win64-gpl-shared"


def is_ffmpeg_installed() -> bool:
    """檢查 FFmpeg 是否已安裝（系統 PATH 或專案目錄下）"""
    # 檢查系統 PATH
    if shutil.which("ffmpeg"):
        return True

    # 檢查專案目錄
    ffmpeg_exe = get_ffmpeg_dir() / "bin" / "ffmpeg.exe"
    return ffmpeg_exe.exists()


def download_ffmpeg(on_output: Callable[[str], None] | None = None) -> bool:
    """下載並解壓縮 FFmpeg 到專案目錄"""
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"
    zip_path = PROJECT_ROOT / "ffmpeg.zip"
    target_dir = get_ffmpeg_dir()

    def out(msg: str):
        if on_output:
            on_output(msg)
        else:
            print(msg)

    try:
        if is_ffmpeg_installed():
            out("✅ FFmpeg 已經安裝。")
            return True

        out("⏳ 準備下載 FFmpeg... 這可能需要幾分鐘的時間，請稍候。")
        out(f"🔗 下載網址: {url}")

        # 下載檔案
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            # 取得檔案大小
            file_size = response.headers.get("Content-Length")
            file_size = int(file_size) if file_size else None
            
            downloaded = 0
            block_size = 8192
            last_percent = -1
            
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                
                downloaded += len(buffer)
                out_file.write(buffer)
                
                if file_size:
                    percent = int(downloaded * 100 / file_size)
                    if percent > last_percent and percent % 10 == 0:
                        out(f"📥 下載進度: {percent}%")
                        last_percent = percent
        
        out("✅ 下載完成，正在解壓縮...")
        
        # 解壓縮
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(PROJECT_ROOT)
            
        out("✅ 解壓縮完成！")
        return True
    
    except Exception as e:
        out(f"❌ 下載或解壓 FFmpeg 失敗: {e}")
        out("👉 您也可以手動下載並放入專案根目錄。")
        return False
        
    finally:
        # 清理暫存的 zip 檔
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
