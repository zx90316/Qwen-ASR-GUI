# -*- coding: utf-8 -*-
"""
SQLAlchemy 資料庫模型與連線設定
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, DateTime
)
from sqlalchemy.orm import sessionmaker, declarative_base

# ── 資料庫路徑 ──
DB_DIR = Path(__file__).resolve().parent.parent
DB_PATH = DB_DIR / "qwen_asr.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """使用者模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    verification_code = Column(String(6), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    """ASR 任務模型"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(String(255), index=True, nullable=False, default="guest") # email or guest UUID
    task_type = Column(String(20), default="local") # "local", "youtube", or "subsync_upload"
    video_id = Column(String(50), nullable=True) # for youtube or subsync uploads
    filename = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")  # pending / processing / completed / failed
    model = Column(String(100), nullable=False)
    language = Column(String(50), nullable=False)
    enable_diarization = Column(Boolean, default=True)
    to_traditional = Column(Boolean, default=True)
    progress = Column(Float, default=0.0)
    progress_message = Column(String(255), default="等待中")
    raw_text = Column(Text, nullable=True)
    chars = Column(Text, nullable=True)             # JSON string of raw character timestamps
    sentences = Column(Text, nullable=True)         # JSON string
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


    def set_chars(self, data):
        self.chars = json.dumps(data, ensure_ascii=False) if data else None

    def get_chars(self):
        return json.loads(self.chars) if self.chars else []

    def set_sentences(self, data):
        self.sentences = json.dumps(data, ensure_ascii=False) if data else None

    def get_sentences(self):
        return json.loads(self.sentences) if self.sentences else []



def get_db():
    """FastAPI dependency — 取得 DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化資料庫（建立資料表）"""
    Base.metadata.create_all(bind=engine)
