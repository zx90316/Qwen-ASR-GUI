# -*- coding: utf-8 -*-
"""
OCR 引擎 — 透過 Ollama glm-ocr 模型進行圖片/PDF OCR 辨識
支援 PDF 自動分頁、重試機制、結構化 JSON 輸出、簡繁轉換與形近字修正
"""
import json
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
import base64
import io
import os

from PIL import Image
from opencc import OpenCC

try:
    from glmocr import GlmOcr
except ImportError:
    GlmOcr = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


# ── 後處理：簡繁轉換 + 形近字修正 ──

_cc = OpenCC('s2t')

_CORRECTION_MAP_PATH = Path(__file__).parent / "ocr_correction_map.json"


def load_correction_map() -> Dict[str, str]:
    """從 JSON 檔載入形近字修正字典，若檔案不存在則回傳空字典"""
    if _CORRECTION_MAP_PATH.exists():
        with open(_CORRECTION_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_correction_map(mapping: Dict[str, str]) -> None:
    """將形近字修正字典寫回 JSON 檔"""
    with open(_CORRECTION_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


_correction_map: Dict[str, str] = load_correction_map()


def get_correction_map() -> Dict[str, str]:
    return dict(_correction_map)


def update_correction_map(new_map: Dict[str, str]) -> None:
    """更新記憶體中與磁碟上的修正字典"""
    global _correction_map
    _correction_map = dict(new_map)
    save_correction_map(_correction_map)


def postprocess_value(text: str) -> str:
    """對單一字串執行：簡體→繁體 → 形近字修正"""
    if not text or not text.strip():
        return ""
    text = _cc.convert(text.strip())
    for wrong, right in _correction_map.items():
        text = text.replace(wrong, right)
    return text


def postprocess_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """對整份 OCR 結果 dict 的 key 與 value 都套用後處理"""
    if not isinstance(data, dict):
        return data
    corrected: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = postprocess_value(key)
        new_value = postprocess_value(str(value)) if isinstance(value, str) else value
        corrected[new_key] = new_value
    return corrected


def merge_page_results(all_page_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合併多頁 OCR 結果（已經過後處理）。
    規則：
      - 忽略空值
      - 所有非空值一致 → 取該值
      - 出現不同非空值 → 清除為空字串
      - 全部空值 → 空字串
    """
    field_values: Dict[str, List[str]] = OrderedDict()

    for page_data in all_page_data:
        if not isinstance(page_data, dict):
            continue
        for key, value in page_data.items():
            if key not in field_values:
                field_values[key] = []
            v = str(value).strip() if value else ""
            if v:
                field_values[key].append(v)

    merged: Dict[str, str] = OrderedDict()
    for key, values in field_values.items():
        if not values:
            merged[key] = ""
        else:
            unique = set(values)
            merged[key] = values[0] if len(unique) == 1 else ""
    return merged


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


def _call_glm_ocr(
    image_base64: str,
    prompt: str,
    raw_mode: bool = False,
) -> Dict[str, Any]:
    """
    呼叫本地 glmocr 進行 OCR 辨識。
    回傳 {"success": bool, "data": dict|None, "raw": str, "error": str|None}
    """
    if GlmOcr is None:
        return {"success": False, "data": None, "raw": "", "error": "glmocr module not found. 請先執行安裝。"}
    
    # 建構 data URI 格式
    data_uri = f"data:image/png;base64,{image_base64}"
    
    # 建立 Config 並覆寫 model 為 glm-ocr:latest 
    # 初始化 GlmOcr 
    config_path = str(Path(__file__).parent / "config.yaml")

    try:
        # 強制在此環境中將提示詞附加進去 (MaaS mode disabled, OCR via local config)
        parser = GlmOcr(config_path=config_path)
        
        # Override default prompt in runtime
        parser._pipeline.page_loader.default_prompt = prompt
        
        # 進行解析
        results = parser.parse(data_uri)
        
        # 提取結果
        json_res = results.json_result
        md_res = results.markdown_result
        
        # 若需要 JSON 格式
        if not raw_mode:
            # 嘗試直接從 markdown 或 config 的結構提取出 JSON
            # GlmOCR 返回的 json_result 並非我們的 `fields` 結構，所以我們還是以 markdown 解析為主，
            # 若 model 回應了 markdown 內的 json block
            parsed = _parse_json_response(md_res)
            if parsed is not None:
                parsed = postprocess_result(parsed)
                return {"success": True, "data": parsed, "raw": md_res, "error": None}
            else:
                return {"success": True, "data": None, "raw": md_res, "error": "JSON 解析失敗"}
        else:
            return {"success": True, "data": None, "raw": postprocess_value(md_res), "error": None}

    except Exception as e:
        return {"success": False, "data": None, "raw": "", "error": f"glmocr 解析失敗: {e}"}



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
            
            result = _call_glm_ocr(b64, prompt, raw_mode=raw_mode)
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
        result = _call_glm_ocr(b64, prompt, raw_mode=raw_mode)
        yield {
            "page": 1,
            "total": 1,
            "percent": 100,
            "result": result,
            "done": True,
        }
