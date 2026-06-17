"""Helper functions for local PDF parsing."""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image


def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """Convert PDF pages to PIL Images using PyMuPDF."""
    import fitz

    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)

    doc.close()
    return images


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64-encoded PNG string."""
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
