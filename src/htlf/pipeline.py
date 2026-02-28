"""Integrated HTLF Phase 2 pipeline with CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .matcher import match_dags
from .parser import extract_dag
from .scorer import compute_scores


@dataclass(slots=True)
class LossVector:
    """Main output vector of HTLF Phase 2."""

    r_struct: float
    r_context: float
    r_qualia: float | None
    total_loss: float
    profile_type: str


def run_pipeline(
    source_text: str,
    target_text: str,
    threshold: float = 0.7,
    use_mock_parser: bool = False,
) -> LossVector:
    """Run end-to-end HTLF scoring pipeline."""
    source_dag = extract_dag(source_text, use_mock=use_mock_parser)
    target_dag = extract_dag(target_text, use_mock=use_mock_parser)

    match_result = match_dags(source_dag, target_dag, threshold=threshold)
    scores = compute_scores(
        source_dag=source_dag,
        target_dag=target_dag,
        match_result=match_result,
        source_text=source_text,
        target_text=target_text,
    )

    return LossVector(
        r_struct=scores.r_struct,
        r_context=scores.r_context,
        r_qualia=scores.r_qualia,
        total_loss=scores.total_loss,
        profile_type=scores.profile_type,
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    """CLI entrypoint: python -m htlf.pipeline --source a.txt --target b.txt"""
    parser = argparse.ArgumentParser(description="Run HTLF Phase 2 measurement pipeline")
    parser.add_argument("--source", required=True, help="Path to source text file (paper)")
    parser.add_argument("--target", required=True, help="Path to target text file (news)")
    parser.add_argument("--threshold", type=float, default=0.7, help="Node match threshold")
    parser.add_argument("--mock-parser", action="store_true", help="Use heuristic parser instead of OpenAI API")
    args = parser.parse_args()

    source_text = _read_text(Path(args.source))
    target_text = _read_text(Path(args.target))

    result = run_pipeline(
        source_text=source_text,
        target_text=target_text,
        threshold=args.threshold,
        use_mock_parser=args.mock_parser,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
