"""ضغط ومعالجة الصور قبل الرفع."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps

from app.config import DEFAULT_JPEG_QUALITY, MAX_IMAGE_BYTES


def compress_image_bytes(
    data: bytes,
    filename: str = "scan.jpg",
    max_bytes: int = MAX_IMAGE_BYTES,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> Tuple[bytes, str, str]:
    """
    يضغط الصورة إلى JPEG مع الحفاظ على الاتجاه.
    يعيد (bytes, mime, filename).
    """
    stem = Path(filename).stem or "scan"
    out_name = f"{stem}.jpg"

    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        current_quality = quality
        result = _encode_jpeg(img, current_quality)

        # تصغير تدريجي إن بقي الحجم كبيراً
        while len(result) > max_bytes and current_quality > 40:
            current_quality -= 10
            result = _encode_jpeg(img, current_quality)

        width, height = img.size
        scale = 0.85
        while len(result) > max_bytes and min(width, height) > 800:
            width = int(width * scale)
            height = int(height * scale)
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            result = _encode_jpeg(resized, max(current_quality, 55))

    return result, "image/jpeg", out_name


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def load_and_prepare_file(path: Path) -> Tuple[bytes, str, str]:
    """يقرأ ملفاً من القرص ويجهّزه للرفع (صورة مضغوطة أو PDF كما هو)."""
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return data, "application/pdf", path.name
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}:
        return compress_image_bytes(data, path.name)
    raise ValueError(f"نوع الملف غير مدعوم: {path.name}")
