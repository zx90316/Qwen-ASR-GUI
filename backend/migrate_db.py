# -*- coding: utf-8 -*-
"""
資料庫遷移腳本
新增 chars 欄位到 tasks 與 youtube_tasks 表格
"""
import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent
DB_PATH = DB_DIR / "qwen_asr.db"

def migrate():
    if not DB_PATH.exists():
        print(f"資料庫不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check and add to tasks
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'chars' not in columns:
            print("Adding 'chars' column to 'tasks' table...")
            cursor.execute("ALTER TABLE tasks ADD COLUMN chars TEXT")
        else:
            print("'chars' column already exists in 'tasks' table.")

        # Check and add to youtube_tasks
        cursor.execute("PRAGMA table_info(youtube_tasks)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'chars' not in columns:
            print("Adding 'chars' column to 'youtube_tasks' table...")
            cursor.execute("ALTER TABLE youtube_tasks ADD COLUMN chars TEXT")
        else:
            print("'chars' column already exists in 'youtube_tasks' table.")

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
