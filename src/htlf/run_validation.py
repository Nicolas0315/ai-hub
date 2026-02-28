"""Real-data HTLF validation pipeline (10-case dataset + timing benchmark)."""

from __future__ import annotations

import argparse
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import rust_bridge as rb
from .pipeline import LossVector, run_pipeline
from .validate import MANUAL_QUALIA_MAP

DATASET_PATH = Path("/Users/nicolas/work/katala/docs/research/htlf-validation-dataset.md")
RESULT_PATH = Path("/Users/nicolas/work/katala/docs/research/htlf-realdata-validation.md")


@dataclass(slots=True)
class DatasetCase:
    case_id: int
    title: str
    paper_url: str | None
    news_url: str | None
    paper_claim: str
    news_claim: str
    manual_r_struct: float
    manual_r_context: float
    manual_r_qualia: float


@dataclass(slots=True)
class EvalRow:
    case: DatasetCase
    result: LossVector
    source_origin: str
    target_origin: str


def _parse_cases(md: str) -> list[DatasetCase]:
    chunks = re.split(r"\n## Case\s+(\d+):\s+", md)
    out: list[DatasetCase] = []
    for i in range(1, len(chunks), 2):
        case_id = int(chunks[i])
        body = chunks[i + 1]
        title = body.split("\n", 1)[0].strip()

        paper_url_match = re.search(r"- \*\*DOI\*\*:\s*\[[^\]]+\]\(([^)]+)\)", body)
        if not paper_url_match:
            paper_url_match = re.search(r"- \*\*URL\*\*:\s*\[[^\]]+\]\(([^)]+)\)", body)
        news_url_match = re.search(r"- \*\*URL\*\*:\s*<([^>]+)>", body)

        paper_claim_match = re.search(r"- \*\*主要主張\*\*:\s*(.+)", body)
        news_claim_match = re.search(r"- \*\*ニュース主張\*\*:\s*(.+)", body)

        table_match = re.search(r"\| R_struct \|\s*([0-9.]+)\s*\|.*\n\| R_context \|\s*([0-9.]+)\s*\|", body)
        if not table_match:
            continue

        out.append(
            DatasetCase(
                case_id=case_id,
                title=title,
                paper_url=paper_url_match.group(1) if paper_url_match else None,
                news_url=news_url_match.group(1) if news_url_match else None,
                paper_claim=paper_claim_match.group(1).strip() if paper_claim_match else "",
                news_claim=news_claim_match.group(1).strip() if news_claim_match else "",
                manual_r_struct=float(table_match.group(1)),
                manual_r_context=float(table_match.group(2)),
                manual_r_qualia=MANUAL_QUALIA_MAP.get(case_id, 0.2),
            )
        )
    return out


def _fetch_text(url: str, timeout: int = 15) -> str | None:
    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore

        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code >= 400:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:20000] if text else None
    except Exception:
        return None


def _build_texts(case: DatasetCase) -> tuple[str, str, str, str]:
    src = _fetch_text(case.paper_url) if case.paper_url else None
    tgt = _fetch_text(case.news_url) if case.news_url else None
    src_origin = "url" if src else "fallback"
    tgt_origin = "url" if tgt else "fallback"
    if not src:
        src = f"{case.title} (paper summary): {case.paper_claim}"
    if not tgt:
        tgt = f"{case.title} (news summary): {case.news_claim}"
    return src, tgt, src_origin, tgt_origin


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else float("nan")


def _fmt(v: float) -> str:
    return "nan" if math.isnan(v) else f"{v:.4f}"


def run(use_mock_parser: bool = True, threshold: float = 0.7) -> list[EvalRow]:
    cases = _parse_cases(DATASET_PATH.read_text(encoding="utf-8"))
    rows: list[EvalRow] = []
    for c in cases:
        src, tgt, so, to = _build_texts(c)
        res = run_pipeline(source_text=src, target_text=tgt, threshold=threshold, use_mock_parser=use_mock_parser)
        rows.append(EvalRow(case=c, result=res, source_origin=so, target_origin=to))
    return rows


def benchmark(rows: list[EvalRow], threshold: float, use_mock_parser: bool) -> tuple[float, float] | None:
    if not rb.RUST_AVAILABLE:
        return None

    pairs = [(r.case, _build_texts(r.case)[:2]) for r in rows]

    t0 = time.perf_counter()
    for _case, (src, tgt) in pairs:
        run_pipeline(source_text=src, target_text=tgt, threshold=threshold, use_mock_parser=use_mock_parser)
    rust_sec = time.perf_counter() - t0

    old = rb.RUST_AVAILABLE
    rb.RUST_AVAILABLE = False
    try:
        t1 = time.perf_counter()
        for _case, (src, tgt) in pairs:
            run_pipeline(source_text=src, target_text=tgt, threshold=threshold, use_mock_parser=use_mock_parser)
        py_sec = time.perf_counter() - t1
    finally:
        rb.RUST_AVAILABLE = old

    return rust_sec, py_sec


def write_report(rows: list[EvalRow], timing: tuple[float, float] | None) -> None:
    manual_struct = [r.case.manual_r_struct for r in rows]
    manual_context = [r.case.manual_r_context for r in rows]
    manual_qualia = [r.case.manual_r_qualia for r in rows]

    auto_struct = [r.result.r_struct for r in rows]
    auto_context = [r.result.r_context for r in rows]
    auto_qualia = [r.result.r_qualia or 0.0 for r in rows]

    corr_struct = _pearson(manual_struct, auto_struct)
    corr_context = _pearson(manual_context, auto_context)
    corr_qualia = _pearson(manual_qualia, auto_qualia)

    lines: list[str] = []
    lines.append("# HTLF Real-data Validation")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Correlation (manual vs auto)")
    lines.append(f"- Pearson R_struct: **{_fmt(corr_struct)}**")
    lines.append(f"- Pearson R_context: **{_fmt(corr_context)}**")
    lines.append(f"- Pearson R_qualia: **{_fmt(corr_qualia)}**")
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")
    lines.append("| Case | Title | Source | Target | Manual R_struct | Auto R_struct | Manual R_context | Auto R_context | Manual R_qualia | Auto R_qualia | Profile | Total Loss |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|")
    for r in rows:
        lines.append(
            "| {id} | {title} | {so} | {to} | {ms:.2f} | {as_:.2f} | {mc:.2f} | {ac:.2f} | {mq:.2f} | {aq:.2f} | {pf} | {loss:.2f} |".format(
                id=r.case.case_id,
                title=r.case.title.replace("|", " "),
                so=r.source_origin,
                to=r.target_origin,
                ms=r.case.manual_r_struct,
                as_=r.result.r_struct,
                mc=r.case.manual_r_context,
                ac=r.result.r_context,
                mq=r.case.manual_r_qualia,
                aq=r.result.r_qualia or 0.0,
                pf=r.result.profile_type,
                loss=r.result.total_loss,
            )
        )

    lines.append("")
    lines.append("## Runtime benchmark")
    if timing is None:
        lines.append("- Rust module not available; skipped Rust vs Python benchmark.")
    else:
        rust_sec, py_sec = timing
        speedup = (py_sec / rust_sec) if rust_sec > 1e-9 else float("nan")
        lines.append(f"- Rust total: {rust_sec:.3f}s")
        lines.append(f"- Python total: {py_sec:.3f}s")
        lines.append(f"- Speedup: {speedup:.2f}x")

    RESULT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run HTLF real-data validation")
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--no-mock-parser", action="store_true")
    args = ap.parse_args()

    rows = run(use_mock_parser=not args.no_mock_parser, threshold=args.threshold)
    timing = benchmark(rows, threshold=args.threshold, use_mock_parser=not args.no_mock_parser)
    write_report(rows, timing)
    print(f"Wrote: {RESULT_PATH}")


if __name__ == "__main__":
    main()
