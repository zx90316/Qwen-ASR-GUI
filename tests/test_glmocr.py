import sys
import os
import base64
from pathlib import Path

# Fix path to allow importing backend
sys.path.append(str(Path(__file__).parent.parent))

from backend.ocr_engine import _call_glm_ocr

def test_glmocr():
    print("Testing _call_glm_ocr...")
    
    # Create a dummy transparent 1x1 PNG pixel for testing
    dummy_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    
    prompt = "OCR"
    
    res = _call_glm_ocr(image_base64=dummy_png_b64, prompt=prompt, raw_mode=True)
    
    print(res)
    
    if res.get("success"):
        print("Success!")
    else:
        print("Failed.")

if __name__ == "__main__":
    test_glmocr()
