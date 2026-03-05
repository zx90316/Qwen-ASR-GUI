# -*- coding: utf-8 -*-
"""
Qwen-ASR-GUI Manager — 啟動入口

使用系統 Python 執行，不需要 .venv。
會自動安裝缺少的管理 GUI 依賴（ttkbootstrap, psutil）。

使用方式:
    python launch.py
    或直接雙擊執行
"""
import sys
import subprocess
import importlib


def ensure_dependencies():
    """確保管理 GUI 的依賴已安裝"""
    deps = {
        "ttkbootstrap": "ttkbootstrap>=1.10.0",
    }

    missing = []
    for module_name, pip_name in deps.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print("=" * 60)
        print("  Qwen-ASR-GUI Manager")
        print("  正在安裝必要的依賴套件...")
        print("=" * 60)
        for dep in missing:
            print(f"  📦 安裝 {dep}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", dep],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print("  ✅ 依賴安裝完成！")
        print("=" * 60)


def main():
    # 確保依賴
    ensure_dependencies()

    # 啟動管理面板
    from manager.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
