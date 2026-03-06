#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_coding_to_inf_brain_flowchart.png"


def font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def draw_box(draw: ImageDraw.ImageDraw, rect, title, lines):
    x1, y1, x2, y2 = rect
    draw.rounded_rectangle(rect, radius=12, fill=(246, 248, 250), outline=(31, 41, 55), width=2)
    draw.text((x1 + 10, y1 + 8), title, fill=(17, 24, 39), font=font(20))
    y = y1 + 42
    for ln in lines:
        draw.text((x1 + 10, y), ln, fill=(31, 41, 55), font=font(15))
        y += 20


def arrow(draw: ImageDraw.ImageDraw, p1, p2, label=""):
    draw.line([p1, p2], fill=(17, 24, 39), width=3)
    # arrow head
    x2, y2 = p2
    draw.polygon([(x2, y2), (x2 - 12, y2 - 6), (x2 - 12, y2 + 6)], fill=(17, 24, 39))
    if label:
        mx = (p1[0] + p2[0]) // 2
        my = (p1[1] + p2[1]) // 2 - 14
        draw.text((mx, my), label, fill=(55, 65, 81), font=font(14))


def main() -> int:
    W, H = 2200, 1500
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    boxes = {
        "A": (60, 80, 700, 320),
        "B": (780, 80, 1420, 320),
        "C": (1500, 80, 2140, 320),
        "D": (60, 430, 700, 730),
        "E": (780, 430, 1420, 730),
        "F": (1500, 430, 2140, 730),
        "G": (60, 860, 700, 1240),
        "H": (780, 860, 1420, 1240),
        "I": (1500, 860, 2140, 1240),
    }

    draw_box(d, boxes["A"], "A. inf-Coding Entry", ["guard.sh", "katala-exec.sh", "assist scripts", "start tasks only via inf-Coding"])
    draw_box(d, boxes["B"], "B. KQ Runtime", ["formal normalization", "kq symbolic/solver path", "unified output", "no reverse contamination"])
    draw_box(d, boxes["C"], "C. Router (ksi1-router)", ["SAT/SMT/symbolic dispatch", "strict on schema violation", "collect formal + unified outputs"])
    draw_box(d, boxes["D"], "D. inf-Brain", ["run_inf_brain_layer()", "sub_layers: theory/model/memory", "KQ -> inf_brain: full-access", "inf_brain -> KQ: no-access"])
    draw_box(d, boxes["E"], "E. inf-Theory", ["UGT1..UGT5", "unification model", "sanitize/validate", "reverse-flow CI guard"])
    draw_box(d, boxes["F"], "F. inf-Model", ["katala_universe_model", "axiom sandbox", "status lifecycle", "observation fit linkage"])
    draw_box(d, boxes["G"], "G. inf-Memory", ["peer-reviewed only", "openalex/crossref/pubmed", "binary raw + metadata-json", "sha256 integrity"])
    draw_box(d, boxes["H"], "H. Observation Pipeline", ["manifest dedup guard", "observation_vector build", "chi2 20-track reevaluation", "variant-axiom rerun"])
    draw_box(d, boxes["I"], "I. CI Gates", ["inf-theory guard", "inf-model guard", "inf-memory guard", "inf-brain + obs-manifest guard"])

    arrow(d, (700, 200), (780, 200), "entry")
    arrow(d, (1420, 200), (1500, 200), "route")
    arrow(d, (1820, 320), (380, 430), "dispatch")
    arrow(d, (700, 580), (780, 580), "sub-layer")
    arrow(d, (1420, 580), (1500, 580), "sub-layer")
    arrow(d, (380, 730), (380, 860), "sub-layer")
    arrow(d, (700, 1050), (780, 1050), "obs-fit")
    arrow(d, (1420, 1050), (1500, 1050), "policy+ci")

    d.text((W // 2 - 680, 1380),
           "Katala Flow (Detailed): inf-Coding -> KQ -> Router -> inf-Brain {inf-Theory, inf-Model, inf-Memory} -> Observation/CI",
           fill=(17, 24, 39), font=font(17))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG")
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
