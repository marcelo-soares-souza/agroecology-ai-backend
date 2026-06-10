from __future__ import annotations

import io

from PIL import Image


def process_avatar(image_bytes: bytes, max_size: int = 256) -> bytes:
    pil_img: Image.Image = Image.open(io.BytesIO(image_bytes))
    pil_img = pil_img.convert("RGB")
    pil_img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    width, height = pil_img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    pil_img = pil_img.crop((left, top, left + size, top + size))
    pil_img = pil_img.resize((max_size, max_size), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    pil_img.save(output, format="WEBP", quality=80)
    return output.getvalue()
