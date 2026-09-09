from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import pytesseract
import pymupdf as fitz

from app.config import settings


class TesseractProvider:
    def __init__(self) -> None:
        os.environ["OMP_THREAD_LIMIT"] = str(settings.OMP_THREAD_LIMIT)

    def extract_page_data(
        self,
        doc: fitz.Document,
        page_idx: int,
        lang: str = "deu+eng",
        dpi: int = 250,
    ) -> Tuple[str, str, Optional[float], List[Dict[str, Any]], float, float]:
        """
        Extract text and word boxes from a PDF page using PyMuPDF direct text and/or Tesseract OCR.
        Returns: (extracted_text, method, confidence, word_boxes, page_width, page_height)
        """
        page = doc.load_page(page_idx)
        rect = page.rect
        width, height = float(rect.width), float(rect.height)

        # 1. Try direct text extraction first
        direct_text = page.get_text("text").strip()
        word_list = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)

        # Check if page has images
        image_list = page.get_images()

        # Decision logic per Section 10:
        # If direct text is substantial and no large scanned image covers the page, direct extraction suffices.
        # But if text is very short (< 50 chars) or there is an embedded image on the page, run OCR.
        needs_ocr = len(direct_text) < 40 or (len(image_list) > 0 and len(direct_text) < 150)

        if not needs_ocr:
            word_boxes = []
            for w in word_list:
                word_boxes.append({
                    "text": w[4],
                    "x0": float(w[0]),
                    "y0": float(w[1]),
                    "x1": float(w[2]),
                    "y1": float(w[3]),
                })
            return direct_text, "direct", 1.0, word_boxes, width, height

        # 2. Render page to image at specified DPI and run Tesseract OCR
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        ocr_text, ocr_conf, ocr_boxes = self._run_tesseract(img, lang=lang, scale=zoom)

        # If page had some direct text as well, combine without duplicating
        if direct_text and direct_text not in ocr_text:
            combined_text = f"{direct_text}\n{ocr_text}"
            method = "mixed"
        else:
            combined_text = ocr_text or direct_text
            method = "ocr" if ocr_text else "direct"

        return combined_text, method, ocr_conf, ocr_boxes, width, height

    def extract_image_data(
        self,
        image_path: str,
        lang: str = "deu+eng",
    ) -> Tuple[str, str, Optional[float], List[Dict[str, Any]], float, float]:
        """Run OCR directly on an image file (JPG, PNG, WebP)."""
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            width, height = float(img.width), float(img.height)
            text, conf, boxes = self._run_tesseract(img, lang=lang, scale=1.0)
            return text, "ocr", conf, boxes, width, height

    def _run_tesseract(
        self,
        img: Image.Image,
        lang: str,
        scale: float,
    ) -> Tuple[str, Optional[float], List[Dict[str, Any]]]:
        """Run pytesseract data extraction returning text, average confidence, and scaled boxes."""
        try:
            data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
            words = []
            confidences = []
            boxes = []

            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text_piece = data["text"][i].strip()
                conf = float(data["conf"][i])
                if text_piece and conf > 0:
                    words.append(text_piece)
                    confidences.append(conf)
                    # Scale coordinates back to 72 DPI PDF point space
                    x = float(data["left"][i]) / scale
                    y = float(data["top"][i]) / scale
                    w = float(data["width"][i]) / scale
                    h = float(data["height"][i]) / scale
                    boxes.append({
                        "text": text_piece,
                        "x0": x,
                        "y0": y,
                        "x1": x + w,
                        "y1": y + h,
                    })

            full_text = " ".join(words)
            avg_conf = (sum(confidences) / len(confidences)) / 100.0 if confidences else None
            return full_text, avg_conf, boxes
        except Exception:
            # Fallback if tesseract CLI errors
            return "", None, []


tesseract_provider = TesseractProvider()
