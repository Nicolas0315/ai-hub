"""Integrated HTLF pipeline with CLI (Phase 2 + KS29B integration mode)."""

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
    """Main output vector of HTLF."""

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


def _read_text_or_literal(value: str | None) -> str | None:
    if value is None:
        return None
    p = Path(value)
    if p.exists() and p.is_file():
        return _read_text(p)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HTLF measurement pipeline")
    parser.add_argument("--mode", choices=["htlf", "ks29b"], default="htlf", help="Execution mode")

    parser.add_argument("--source", help="Source file path (htlf) or source text/file (ks29b)")
    parser.add_argument("--target", help="Target text file path (htlf mode)")
    parser.add_argument("--claim", help="Claim text or file path (ks29b mode)")

    parser.add_argument("--threshold", type=float, default=0.7, help="Node match threshold")
    parser.add_argument("--mock-parser", action="store_true", help="Use heuristic parser instead of OpenAI API")

    parser.add_argument("--source-layer", choices=["math", "formal_language", "natural_language", "music", "creative"])
    parser.add_argument("--target-layer", choices=["math", "formal_language", "natural_language", "music", "creative"])
    parser.add_argument("--ks29b-score", type=float, help="Optional precomputed KS29B score (0-1)")
    parser.add_argument("--alpha", type=float, default=0.7, help="Weight of KS29B score")
    parser.add_argument("--beta", type=float, default=0.3, help="Weight of translation fidelity")

    args = parser.parse_args()

    if args.mode == "htlf":
        if not args.source or not args.target:
            raise SystemExit("--source and --target are required in --mode htlf")
        source_text = _read_text(Path(args.source))
        target_text = _read_text(Path(args.target))

        result = run_pipeline(
            source_text=source_text,
            target_text=target_text,
            threshold=args.threshold,
            use_mock_parser=args.mock_parser,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return

    # ks29b mode
    if not args.claim:
        raise SystemExit("--claim is required in --mode ks29b")

    from .ks29b_integration import HTLFScorer

    scorer = HTLFScorer(alpha=args.alpha, beta=args.beta)
    claim_text = _read_text_or_literal(args.claim)
    source_text = _read_text_or_literal(args.source)

    result = scorer.evaluate(
        claim_text=claim_text or "",
        source_text=source_text,
        source_layer=args.source_layer,
        target_layer=args.target_layer,
        ks29b_score=args.ks29b_score,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
