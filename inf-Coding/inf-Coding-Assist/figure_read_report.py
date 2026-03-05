#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from PIL import Image


def detect_axes(img: Image.Image) -> dict:
    g = img.convert("L")
    w, h = g.size
    px = g.load()

    # very light heuristic: darkest dense row/col in lower/left area
    row_scores = []
    for y in range(int(h * 0.55), h):
        s = 0
        for x in range(w):
            if px[x, y] < 70:
                s += 1
        row_scores.append((s, y))
    col_scores = []
    for x in range(0, int(w * 0.45)):
        s = 0
        for y in range(h):
            if px[x, y] < 70:
                s += 1
        col_scores.append((s, x))

    x_axis_y = max(row_scores)[1] if row_scores else int(h * 0.9)
    y_axis_x = max(col_scores)[1] if col_scores else int(w * 0.1)

    return {
        "x_axis": {"x1": 0, "y1": x_axis_y, "x2": w - 1, "y2": x_axis_y},
        "y_axis": {"x1": y_axis_x, "y1": 0, "x2": y_axis_x, "y2": h - 1},
    }


def sample_series_points(img: Image.Image, axes: dict, n: int = 24) -> list[dict]:
    g = img.convert("RGB")
    w, h = g.size
    x0 = axes["y_axis"]["x1"] + 5
    y0 = axes["x_axis"]["y1"]
    pts = []
    if x0 >= w:
        return pts
    step = max(1, (w - x0 - 1) // n)
    px = g.load()
    for x in range(x0, w, step):
        best_y = None
        best_dark = 10**9
        for y in range(max(0, y0 - int(h * 0.8)), min(h, y0 + 1)):
            r, gg, b = px[x, y]
            d = r + gg + b
            if d < best_dark:
                best_dark = d
                best_y = y
        if best_y is not None:
            pts.append({"x_px": int(x), "y_px": int(best_y)})
    return pts[:n]


def build_report(path: Path) -> dict:
    img = Image.open(path)
    axes = detect_axes(img)
    pts = sample_series_points(img, axes)
    conf = 0.35 + min(0.45, len(pts) / 80.0)
    return {
        "schema": "figure-read-report-v1",
        "image": str(path),
        "chart_type": "line_or_scatter_lite",
        "axes": axes,
        "series_count": 1 if pts else 0,
        "digitize_confidence": round(conf, 4),
        "extracted_points_sample": pts,
        "limits": [
            "OCR labels/ticks not yet integrated",
            "single-series assumption in lite mode",
            "pixel coordinate only (no physical unit calibration)",
        ],
    }


def main():
    if len(sys.argv) < 2:
        print("usage: figure_read_report.py <image_path>")
        sys.exit(1)
    p = Path(sys.argv[1])
    report = build_report(p)
    out = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/figure_read_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
