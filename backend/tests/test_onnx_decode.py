"""Unit tests for the torch-free ONNX decoding path (no model file needed)."""
import numpy as np
from PIL import Image

from app.ml.onnx_runtime import decode_output, letterbox, nms


def _fake_output(rows):
    """rows: list of (cx, cy, w, h, class_id, score) -> (1, 4+nc, N) like YOLOv8."""
    nc = 6
    arr = np.zeros((4 + nc, 8400), dtype=np.float32)  # real YOLOv8n has 8400 anchors
    for i, (cx, cy, w, h, c, s) in enumerate(rows):
        arr[:4, i] = (cx, cy, w, h)
        arr[4 + c, i] = s
    return arr[None]


def test_letterbox_shape_and_scale():
    img = Image.new("RGB", (1280, 640))
    tensor, scale, pad_x, pad_y = letterbox(img, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert scale == 0.5 and pad_x == 0 and pad_y == 160


def test_decode_maps_back_to_original_image_and_applies_nms():
    # Original 1280x640 -> scale 0.5, pad_y 160. Box centred at (320, 320) in
    # letterboxed space, 100x100 => original box x 440..840? compute directly.
    out = _fake_output([
        (320, 320, 100, 100, 0, 0.9),
        (322, 322, 100, 100, 0, 0.6),   # duplicate, must be suppressed
        (100, 300, 40, 40, 2, 0.5),     # different class, kept
        (500, 500, 30, 30, 1, 0.05),    # below threshold, dropped
    ])
    boxes = decode_output(out, scale=0.5, pad_x=0, pad_y=160, orig_w=1280, orig_h=640,
                          conf_thr=0.1, iou_thr=0.45, max_det=10)
    assert [b.class_id for b in boxes] == [0, 2]
    b = boxes[0]
    assert abs(b.x_min - (270 / 0.5) / 1280) < 1e-6
    assert abs(b.x_max - (370 / 0.5) / 1280) < 1e-6
    assert abs(b.y_min - ((270 - 160) / 0.5) / 640) < 1e-6
    assert 0 <= b.x_min < b.x_max <= 1 and 0 <= b.y_min < b.y_max <= 1


def test_decode_handles_transposed_output_and_empty():
    out = _fake_output([(320, 320, 100, 100, 3, 0.8)]).transpose(0, 2, 1)  # (1, N, 4+nc)
    boxes = decode_output(out, scale=1, pad_x=0, pad_y=0, orig_w=640, orig_h=640,
                          conf_thr=0.1, iou_thr=0.45, max_det=10)
    assert len(boxes) == 1 and boxes[0].class_id == 3
    empty = decode_output(_fake_output([(1, 1, 1, 1, 0, 0.01)]), scale=1, pad_x=0, pad_y=0,
                          orig_w=640, orig_h=640, conf_thr=0.1, iou_thr=0.45, max_det=10)
    assert empty == []


def test_nms_keeps_highest_score():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    assert nms(boxes, np.array([0.5, 0.9, 0.7]), 0.45) == [1, 2]
