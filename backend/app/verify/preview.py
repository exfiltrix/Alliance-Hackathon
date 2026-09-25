"""PNG preview of an image with red boxes on changed tiles."""
import base64
import io

import numpy as np
from PIL import Image, ImageDraw

MAX_SIDE = 1024
RED = (230, 30, 30)
WHITE = (255, 255, 255)


def to_uint8(px: np.ndarray) -> np.ndarray:
    """Window to the 1st-99th percentile so CT/16-bit images are visible."""
    if px.dtype == np.uint8:
        return px
    lo, hi = np.percentile(px, [1, 99])
    if hi <= lo:
        hi = lo + 1
    return np.clip((px.astype(np.float64) - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)


def render_preview(px: np.ndarray, changed: list[tuple[int, int]] = (), tile: int = 0) -> str:
    """Base64 PNG, longest side at most MAX_SIDE px."""
    img = Image.fromarray(to_uint8(px), "L").convert("RGB")
    scale = min(1.0, MAX_SIDE / max(img.size))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    if changed:
        draw = ImageDraw.Draw(img)
        width = max(2, round(max(img.size) / 256))
        inner = max(1, width // 2)
        for y, x in changed:
            box = [x * scale, y * scale, (x + tile) * scale - 1, (y + tile) * scale - 1]
            draw.rectangle(box, outline=RED, width=width)
            # White inner stroke keeps the boundary visible on bright and grayscale views.
            draw.rectangle(
                [box[0] + width, box[1] + width, box[2] - width, box[3] - width],
                outline=WHITE,
                width=inner,
            )
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()
