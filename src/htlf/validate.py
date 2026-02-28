"""Validation runner against Phase 0 manual annotation dataset (Phase 2)."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .pipeline import LossVector, run_pipeline

DATASET_PATH = Path("/Users/nicolas/work/katala/docs/research/htlf-validation-dataset.md")
RESULT_PATH = Path("/Users/nicolas/work/katala/docs/research/htlf-phase2-results.md")

# Phase 1 and 1.5 references (from existing reports)
PHASE1_CORR_STRUCT = 0.2181
PHASE1_CORR_CONTEXT = -0.2010
PHASE15_CORR_STRUCT = 0.3522
PHASE15_CORR_CONTEXT = -0.2245

# Phase 2 supplemental manual qualia annotations (tone-fidelity proxy; 0-1)
MANUAL_QUALIA_MAP: dict[int, float] = {
    1: 0.25,
    2: 0.20,
    3: 0.25,
    4: 0.15,
    5: 0.20,
    6: 0.15,
    7: 0.20,
    8: 0.30,
    9: 0.25,
    10: 0.20,
}


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
class CaseEvaluation:
    case: DatasetCase
    auto: LossVector


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def _fmt(v: float) -> str:
    if math.isnan(v):
        return "nan"
    return f"{v:.4f}"


def _parse_cases(dataset_markdown: str) -> list[DatasetCase]:
    chunks = re.split(r"\n## Case\s+(\d+):\s+", dataset_markdown)
    cases: list[DatasetCase] = []

    for idx in range(1, len(chunks), 2):
        case_id = int(chunks[idx])
        body = chunks[idx + 1]
        title = body.split("\n", 1)[0].strip()

        paper_url_match = re.search(r"- \*\*DOI\*\*:\s*\[[^\]]+\]\(([^)]+)\)", body)
        if not paper_url_match:
            paper_url_match = re.search(r"- \*\*URL\*\*:\s*\[([^\]]+)\]\(([^)]+)\)", body)
        news_url_match = re.search(r"- \*\*URL\*\*:\s*<([^>]+)>", body)

        paper_claim_match = re.search(r"- \*\*主要主張\*\*:\s*(.+)", body)
        news_claim_match = re.search(r"- \*\*ニュース主張\*\*:\s*(.+)", body)

        table_match = re.search(r"\| R_struct \|\s*([0-9.]+)\s*\|.*\n\| R_context \|\s*([0-9.]+)\s*\|", body)
        if not table_match:
            continue

        cases.append(
            DatasetCase(
                case_id=case_id,
                title=title,
                paper_url=paper_url_match.group(1) if paper_url_match and paper_url_match.lastindex == 1 else (paper_url_match.group(2) if paper_url_match else None),
                news_url=news_url_match.group(1) if news_url_match else None,
                paper_claim=paper_claim_match.group(1).strip() if paper_claim_match else "",
                news_claim=news_claim_match.group(1).strip() if news_claim_match else "",
                manual_r_struct=float(table_match.group(1)),
                manual_r_context=float(table_match.group(2)),
                manual_r_qualia=MANUAL_QUALIA_MAP.get(case_id, 0.2),
            )
        )

    return cases


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


def _build_source_target_text(case: DatasetCase) -> tuple[str, str, str]:
    source_text = _fetch_text(case.paper_url) if case.paper_url else None
    target_text = _fetch_text(case.news_url) if case.news_url else None
    source_origin = "url" if source_text else "fallback"
    target_origin = "url" if target_text else "fallback"

    if not source_text:
        source_text = f"{case.title} (paper summary): {case.paper_claim}"
    if not target_text:
        target_text = f"{case.title} (news summary): {case.news_claim}"

    return source_text, target_text, f"source={source_origin}, target={target_origin}"


def run_validation(use_mock_parser: bool = True, threshold: float = 0.7) -> list[CaseEvaluation]:
    dataset_markdown = DATASET_PATH.read_text(encoding="utf-8")
    cases = _parse_cases(dataset_markdown)

    evaluations: list[CaseEvaluation] = []
    for case in cases:
        source_text, target_text, _origin = _build_source_target_text(case)
        loss = run_pipeline(
            source_text=source_text,
            target_text=target_text,
            threshold=threshold,
            use_mock_parser=use_mock_parser,
        )
        evaluations.append(CaseEvaluation(case=case, auto=loss))
    return evaluations


def _mean(values: Iterable[float]) -> float:
    v = list(values)
    return sum(v) / len(v) if v else float("nan")


def _profile_comment(case_title: str, profile: str, r_struct: float, r_context: float, r_qualia: float | None) -> str:
    rq = r_qualia if r_qualia is not None else 0.0
    if profile.startswith("P07") or profile.startswith("P08"):
        return f"{case_title}: 構造優位分類。R_struct={r_struct:.2f} が相対的に高く、技術主張の骨格保持が優勢。"
    if profile.startswith("P09") or profile.startswith("P10"):
        return f"{case_title}: 文脈優位分類。R_context={r_context:.2f} が中心で、背景説明の保持が主。"
    if profile.startswith("P11") or profile.startswith("P12"):
        return f"{case_title}: qualia単軸分類。R_qualia={rq:.2f} が相対的優位。"
    if profile.startswith("P03") or profile.startswith("P04"):
        return f"{case_title}: 構造×qualia 複合。技術保持と語り口保持のバランス型。"
    if profile.startswith("P05") or profile.startswith("P06"):
        return f"{case_title}: 文脈×qualia 複合。背景説明と語調保存の中間型。"
    return f"{case_title}: 構造×文脈 複合。R_struct={r_struct:.2f}, R_context={r_context:.2f} の総合型。"


def write_report(evaluations: list[CaseEvaluation]) -> None:
    manual_struct = [ev.case.manual_r_struct for ev in evaluations]
    manual_context = [ev.case.manual_r_context for ev in evaluations]
    manual_qualia = [ev.case.manual_r_qualia for ev in evaluations]

    auto_struct = [ev.auto.r_struct for ev in evaluations]
    auto_context = [ev.auto.r_context for ev in evaluations]
    auto_qualia = [ev.auto.r_qualia if ev.auto.r_qualia is not None else 0.0 for ev in evaluations]

    corr_struct = _pearson(manual_struct, auto_struct)
    corr_context = _pearson(manual_context, auto_context)
    corr_qualia = _pearson(manual_qualia, auto_qualia)

    lines: list[str] = []
    lines.append("# HTLF Phase 2 Results (Auto vs Manual)")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Correlation")
    lines.append("")
    lines.append(f"- Pearson(manual R_struct, auto R_struct): **{_fmt(corr_struct)}**")
    lines.append(f"- Pearson(manual R_context, auto R_context): **{_fmt(corr_context)}**")
    lines.append(f"- Pearson(manual R_qualia, auto R_qualia): **{_fmt(corr_qualia)}**")
    lines.append("")
    lines.append("## Phase Comparison (1 -> 1.5 -> 2)")
    lines.append("")
    lines.append("| Axis | Phase 1 | Phase 1.5 | Phase 2 | Δ(1.5→2) |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(f"| R_struct corr | {PHASE1_CORR_STRUCT:.4f} | {PHASE15_CORR_STRUCT:.4f} | {corr_struct:.4f} | {corr_struct - PHASE15_CORR_STRUCT:+.4f} |")
    lines.append(f"| R_context corr | {PHASE1_CORR_CONTEXT:.4f} | {PHASE15_CORR_CONTEXT:.4f} | {corr_context:.4f} | {corr_context - PHASE15_CORR_CONTEXT:+.4f} |")
    lines.append(f"| R_qualia corr | n/a | n/a | {corr_qualia:.4f} | n/a |")
    lines.append("")
    lines.append("## Aggregate Means")
    lines.append("")
    lines.append(f"- Manual mean R_struct: {_mean(manual_struct):.4f}")
    lines.append(f"- Auto mean R_struct: {_mean(auto_struct):.4f}")
    lines.append(f"- Manual mean R_context: {_mean(manual_context):.4f}")
    lines.append(f"- Auto mean R_context: {_mean(auto_context):.4f}")
    lines.append(f"- Manual mean R_qualia: {_mean(manual_qualia):.4f}")
    lines.append(f"- Auto mean R_qualia: {_mean(auto_qualia):.4f}")
    lines.append("")
    lines.append("## Per-case")
    lines.append("")
    lines.append("| Case | Title | Manual R_struct | Auto R_struct | Manual R_context | Auto R_context | Manual R_qualia | Auto R_qualia | Profile | Total Loss |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|---:|")

    for ev in evaluations:
        lines.append(
            "| {id} | {title} | {ms:.2f} | {as_:.2f} | {mc:.2f} | {ac:.2f} | {mq:.2f} | {aq:.2f} | {profile} | {loss:.2f} |".format(
                id=ev.case.case_id,
                title=ev.case.title.replace("|", " "),
                ms=ev.case.manual_r_struct,
                as_=ev.auto.r_struct,
                mc=ev.case.manual_r_context,
                ac=ev.auto.r_context,
                mq=ev.case.manual_r_qualia,
                aq=ev.auto.r_qualia if ev.auto.r_qualia is not None else 0.0,
                profile=ev.auto.profile_type,
                loss=ev.auto.total_loss,
            )
        )

    lines.append("")
    lines.append("## 12-Pattern Profile Classification Check")
    lines.append("")
    for ev in evaluations:
        lines.append(
            f"- Case {ev.case.case_id} [{ev.auto.profile_type}] — "
            + _profile_comment(
                ev.case.title,
                ev.auto.profile_type,
                ev.auto.r_struct,
                ev.auto.r_context,
                ev.auto.r_qualia,
            )
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- R_context is now implemented as LLM-as-reader protocol: source prerequisite extraction -> target-only definition reconstruction -> embedding similarity weighted average.")
    lines.append("- Backend fallback chain: OpenAI -> Gemini (GOOGLE_API_KEY/GEMINI_API_KEY) -> heuristic scorer.")
    lines.append("- R_qualia is a proxy metric from 3 LLM ratings (median/5.0), with heuristic fallback when API keys are unavailable.")
    lines.append("- Parser in this run uses mock mode by default unless --no-mock-parser is set and API key exists.")

    RESULT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate HTLF Phase 2 against manual annotations")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--no-mock-parser", action="store_true", help="Use OpenAI parser if key exists")
    args = parser.parse_args()

    evaluations = run_validation(use_mock_parser=not args.no_mock_parser, threshold=args.threshold)
    write_report(evaluations)
    print(f"Wrote validation report to: {RESULT_PATH}")


if __name__ == "__main__":
    main()
