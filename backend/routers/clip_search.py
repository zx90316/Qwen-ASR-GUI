# -*- coding: utf-8 -*-
"""
以圖搜頁 Router — 上傳 PDF + 參考圖片，使用 CLIP 找出最相似頁面
"""
import json
import asyncio
import pathlib
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from backend.auth_utils import get_current_user
from backend.clip_engine import search_similar_pages

router = APIRouter(prefix="/api/clip-search", tags=["clip-search"])

ALLOWED_PDF_EXT = {".pdf"}
ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
MAX_PDF_SIZE = 100 * 1024 * 1024   # 100 MB
MAX_IMG_SIZE = 20 * 1024 * 1024    # 20 MB per image


@router.post("/analyze")
async def clip_search_analyze(
    pdf_file: UploadFile = File(...),
    ref_images: List[UploadFile] = File(...),
    must_include: str = Form(""),
    must_exclude: str = Form(""),
    threshold: float = Form(0.5),
    top_k: int = Form(5),
    current_user: dict = Depends(get_current_user),
):
    """
    以圖搜頁 — 上傳 PDF 與一或多張參考圖片，使用 CLIP 模型找出最相似的頁面。

    - pdf_file: PDF 檔案
    - ref_images: 一或多張參考圖片
    - must_include: 必要包含詞（逗號分隔）
    - must_exclude: 不可包含詞（逗號分隔）
    - threshold: 相似度閾值 (0~1)
    - top_k: 取前幾頁
    """
    # 驗證 PDF
    pdf_ext = pathlib.Path(pdf_file.filename or "").suffix.lower()
    if pdf_ext not in ALLOWED_PDF_EXT:
        raise HTTPException(status_code=400, detail=f"僅支援 PDF 檔案，收到: {pdf_ext}")

    pdf_bytes = await pdf_file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail="PDF 檔案大小超過 100 MB 限制")

    # 驗證參考圖片
    ref_images_bytes = []
    for img_file in ref_images:
        img_ext = pathlib.Path(img_file.filename or "").suffix.lower()
        if img_ext not in ALLOWED_IMG_EXT:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的圖片格式: {img_ext}，支援: {', '.join(sorted(ALLOWED_IMG_EXT))}"
            )
        img_bytes = await img_file.read()
        if len(img_bytes) > MAX_IMG_SIZE:
            raise HTTPException(status_code=400, detail=f"圖片 {img_file.filename} 大小超過 20 MB 限制")
        ref_images_bytes.append(img_bytes)

    if len(ref_images_bytes) == 0:
        raise HTTPException(status_code=400, detail="至少需要上傳一張參考圖片")

    # 參數驗證
    threshold = max(0.0, min(1.0, threshold))
    top_k = max(1, min(50, top_k))

    # SSE Generator
    async def event_generator():
        gen = search_similar_pages(
            pdf_bytes=pdf_bytes,
            ref_images_bytes=ref_images_bytes,
            must_include=must_include,
            must_exclude=must_exclude,
            threshold=threshold,
            top_k=top_k,
        )
        for item in gen:
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
