"""Integrated HTLF pipeline with CLI (Phase 2 + KS39b integration mode)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .matcher import get_similarity_backend_name, match_dags
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
    parser_backend: str = "llm"
    context_backend: str = "heuristic"
    qualia_backend: str = "online_approximation"
    matcher_backend: str = "lexical"


def run_pipeline(
    source_text: str,
    target_text: str,
    threshold: float = 0.7,
    use_mock_parser: bool = False,
    qualia_mode: Literal["online", "behavioral", "physio"] = "online",
    responses_data: dict | None = None,
    physio_data: dict | None = None,
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
        qualia_mode=qualia_mode,
        responses_data=responses_data,
        physio_data=physio_data,
    )

    return LossVector(
        r_struct=scores.r_struct,
        r_context=scores.r_context,
        r_qualia=scores.r_qualia,
        total_loss=scores.total_loss,
        profile_type=scores.profile_type,
        parser_backend="mock" if use_mock_parser else "llm",
        context_backend=scores.context_backend,
        qualia_backend=scores.qualia_backend,
        matcher_backend=get_similarity_backend_name(),
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
    parser.add_argument("--mode", choices=["htlf", "ks", "ks29b"], default="htlf", help="Execution mode")

    parser.add_argument("--source", help="Source file path (htlf) or source text/file (ks mode)")
    parser.add_argument("--target", help="Target text file path (htlf mode)")
    parser.add_argument("--claim", help="Claim text or file path (ks mode)")

    parser.add_argument("--threshold", type=float, default=0.7, help="Node match threshold")
    parser.add_argument("--mock-parser", action="store_true", help="Use heuristic parser instead of OpenAI API")
    parser.add_argument(
        "--qualia-mode",
        choices=["online", "behavioral", "physio"],
        default="online",
        help="R_qualia mode: online (default), behavioral, or physio",
    )
    parser.add_argument("--responses-file", help="JSON file for behavioral participant responses")
    parser.add_argument("--physio-file", help="JSON file for physiological signals")

    parser.add_argument("--source-layer", choices=["math", "formal_language", "natural_language", "music", "creative"])
    parser.add_argument("--target-layer", choices=["math", "formal_language", "natural_language", "music", "creative"])
    parser.add_argument("--ks39b-confidence", type=float, help="Optional precomputed KS39b confidence (0-1)")
    parser.add_argument("--ks29b-score", type=float, help="Backward-compatible alias for --ks39b-confidence")
    parser.add_argument("--ks39b-result", help="Path to KS39b verify() JSON result")
    parser.add_argument("--alpha", type=float, default=0.7, help="Weight of KS39b confidence")
    parser.add_argument("--beta", type=float, default=0.3, help="Weight of translation fidelity")

    args = parser.parse_args()

    if args.mode == "htlf":
        if not args.source or not args.target:
            raise SystemExit("--source and --target are required in --mode htlf")
        source_text = _read_text(Path(args.source))
        target_text = _read_text(Path(args.target))

        responses_data = None
        physio_data = None
        if args.qualia_mode == "behavioral":
            if not args.responses_file:
                raise SystemExit("--responses-file is required for --qualia-mode behavioral")
            responses_data = json.loads(_read_text(Path(args.responses_file)))
        if args.qualia_mode == "physio":
            if not args.physio_file:
                raise SystemExit("--physio-file is required for --qualia-mode physio")
            physio_data = json.loads(_read_text(Path(args.physio_file)))

        result = run_pipeline(
            source_text=source_text,
            target_text=target_text,
            threshold=args.threshold,
            use_mock_parser=args.mock_parser,
            qualia_mode=args.qualia_mode,
            responses_data=responses_data,
            physio_data=physio_data,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return

    # ks mode (ks29b kept as backward-compatible alias)
    if not args.claim:
        raise SystemExit("--claim is required in --mode ks/ks29b")

    from .ks_integration import HTLFScorer

    scorer = HTLFScorer(alpha=args.alpha, beta=args.beta)
    claim_text = _read_text_or_literal(args.claim)
    source_text = _read_text_or_literal(args.source)

    ks39b_payload = None
    if args.ks39b_result:
        ks39b_payload = json.loads(_read_text(Path(args.ks39b_result)))

    result = scorer.evaluate(
        claim_text=claim_text or "",
        source_text=source_text,
        source_layer=args.source_layer,
        target_layer=args.target_layer,
        ks39b_result=ks39b_payload,
        ks39b_confidence=args.ks39b_confidence if args.ks39b_confidence is not None else args.ks29b_score,
        use_mock_parser=args.mock_parser,
    )
    payload = asdict(result)
    if payload.get("self_other_boundary"):
        payload["self_other_boundary_summary"] = payload["self_other_boundary"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
