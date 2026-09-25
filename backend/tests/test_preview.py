import base64
import io

import numpy as np
from PIL import Image

from app.verify.preview import render_preview


def test_changed_tile_box_has_red_outer_and_white_inner_strokes():
    encoded = render_preview(np.zeros((64, 64), dtype=np.uint8), [(16, 16)], 16)
    image = np.asarray(Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB"))
    red = np.all(image == (230, 30, 30), axis=2).sum()
    white = np.all(image == (255, 255, 255), axis=2).sum()
    assert red > 0 and white > 0
