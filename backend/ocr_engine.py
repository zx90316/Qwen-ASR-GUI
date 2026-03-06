# -*- coding: utf-8 -*-
"""
OCR 引擎 — 透過 Ollama glm-ocr 模型進行圖片/PDF OCR 辨識
支援 PDF 自動分頁、重試機制、結構化 JSON 輸出
"""
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
import base64
import io
from PIL import Image

import requests

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


# ── 工具函式 ──
def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[Image.Image]:
    """
    將 PDF 每頁轉為 PIL Image 列表。
    需要 PyMuPDF (fitz) 和 Pillow。
    """
    if fitz is None:
        raise ImportError("PyMuPDF 未安裝，請執行 pip install PyMuPDF")
    if Image is None:
        raise ImportError("Pillow 未安裝，請執行 pip install Pillow")

    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img.convert("RGB"))
    finally:
        doc.close()
    return images

def _pil_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """將 PIL Image 轉為 base64 字串"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def _detect_mime(filename: str) -> str:
    """依據副檔名回傳 MIME type"""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/png")


def build_ocr_prompt(fields: Dict[str, str]) -> str:
    """
    根據使用者提供的欄位名稱 + 預設值，建立 OCR 提示詞。
    fields 範例: {"製作日期": "YYYYMMDD", "報告編號": "", ...}
    如果 fields 為空，則回傳純文字萃取的提示詞。
    """
    if not fields:
        return "OCR"
        
    json_template = json.dumps(fields, ensure_ascii=False, indent=2)
    prompt = f"请按下列JSON格式输出图中信息:\n{json_template}"
    return prompt


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """
    嘗試從模型回覆中解析 JSON。
    支援回覆中包含 markdown code block 的情況。
    """
    # 嘗試直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 嘗試從 ```json ... ``` 中提取
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 嘗試找到第一個 { ... } 區塊
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _call_ollama_ocr(
    image_base64: str,
    prompt: str,
    ollama_host: str,
    model: str = "glm-ocr",
    max_retries: int = 3,
    raw_mode: bool = False,
) -> Dict[str, Any]:
    """
    呼叫 Ollama 視覺模型進行 OCR。
    若 raw_mode 為 True，則不嘗試解析 JSON，直接回傳 raw text。
    若為 JSON 模式，含重試機制 (指數退避: 1s, 2s, 4s)。
    回傳 {"success": bool, "data": dict|None, "raw": str, "error": str|None}
    """
    url = f"{ollama_host}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 2048,
        },
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data.get("message", {}).get("content", "").strip()

            if raw_mode:
                return {"success": True, "data": None, "raw": raw_text, "error": None}

            parsed = _parse_json_response(raw_text)
            if parsed is not None:
                return {"success": True, "data": parsed, "raw": raw_text, "error": None}
            else:
                # 解析失敗但有回覆 → 再試一次
                last_error = f"JSON 解析失敗 (嘗試 {attempt + 1}/{max_retries})"
                print(f"[OCR] {last_error}, 原始回覆: {raw_text[:200]}")
        except requests.exceptions.RequestException as e:
            last_error = f"Ollama 請求失敗: {e}"
            print(f"[OCR] {last_error} (嘗試 {attempt + 1}/{max_retries})")
            
            # 若為 raw_mode 且為請求錯誤，仍需重試；若是 parsing 失敗則不會發生因為 raw_mode 會直接 return

        if attempt < max_retries - 1:
            wait = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait)

    return {"success": False, "data": None, "raw": "", "error": last_error}


# ── PDF 處理 ──

def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """
    將 PDF 每頁轉為 PIL Image 列表。
    需要 PyMuPDF (fitz) 和 Pillow。
    """
    if fitz is None:
        raise ImportError("PyMuPDF 未安裝，請執行 pip install PyMuPDF")

    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            # 以指定 DPI 渲染
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img.convert("RGB"))
    finally:
        doc.close()
    return images


# ── 主要處理函式 (Generator，供 SSE 使用) ──

def process_file_stream(
    file_bytes: bytes,
    filename: str,
    fields: Dict[str, str],
    ollama_host: str,
    model: str = "glm-ocr",
    max_retries: int = 3,
) -> Generator[Dict[str, Any], None, None]:
    """
    處理上傳的檔案 (圖片或 PDF)，以 generator 逐頁回傳結果。
    每次 yield 一個 dict:
      {"page": int, "total": int, "percent": float, "result": {...}, "done": bool}
    """
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"

    prompt = build_ocr_prompt(fields)
    raw_mode = len(fields) == 0

    if is_pdf:
        # PDF → 分頁處理
        try:
            pages = pdf_pages_to_images(file_bytes)
        except ImportError as e:
            yield {"page": 0, "total": 0, "percent": 0, "result": None,
                   "done": True, "error": str(e)}
            return
        except Exception as e:
            yield {"page": 0, "total": 0, "percent": 0, "result": None,
                   "done": True, "error": f"PDF 解析失敗: {e}"}
            return

        total = len(pages)
        if total == 0:
            yield {"page": 0, "total": 0, "percent": 100, "result": None,
                   "done": True, "error": "PDF 無頁面"}
            return

        for i, page_img in enumerate(pages):
            # 保持原尺寸高品質進行 OCR 辨識
            b64 = _pil_to_base64(page_img, "PNG")
            
            result = _call_ollama_ocr(b64, prompt, ollama_host, model, max_retries, raw_mode=raw_mode)
            percent = ((i + 1) / total) * 100
            yield {
                "page": i + 1,
                "total": total,
                "percent": percent,
                "result": result,
                "done": (i + 1) == total,
            }
    else:
        # 單張圖片
        try:
            page_img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            # 保持原尺寸高品質進行 OCR 辨識
            b64 = _pil_to_base64(page_img, "PNG")
        except Exception as e:
            yield {"page": 1, "total": 1, "percent": 100, "result": None, "done": True, "error": f"圖片解析失敗: {e}"}
            return

        result = _call_ollama_ocr(b64, prompt, ollama_host, model, max_retries, raw_mode=raw_mode)
        yield {
            "page": 1,
            "total": 1,
            "percent": 100,
            "result": result,
            "done": True,
        }
