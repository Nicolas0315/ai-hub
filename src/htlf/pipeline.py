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
from .cultural_loss import compute_cultural_loss, CulturalLossResult
from .temporal_loss import compute_temporal_loss, TemporalLossResult


@dataclass(slots=True)
class LossVector:
    """Main output vector of HTLF.
    
    5-axis model:
      R_struct, R_context, R_qualia — original 3 axes
      R_cultural — cultural translation loss (Quine/Duhem-Quine)
      R_temporal — temporal translation loss (Kuhn/Barthes)
    
    R_cultural and R_temporal include indeterminacy measures per Quine's
    thesis that translation between radically different frameworks is
    underdetermined by all possible behavioral evidence.
    """

    r_struct: float
    r_context: float
    r_qualia: float | None
    r_cultural: float | None           # Cultural loss estimate
    r_cultural_indeterminacy: float | None  # Quinean indeterminacy width
    r_temporal: float | None           # Temporal loss estimate
    r_temporal_indeterminacy: float | None  # Paradigmatic indeterminacy
    total_loss: float
    profile_type: str
    cultural_detail: dict | None = None  # Full CulturalLossResult as dict
    temporal_detail: dict | None = None  # Full TemporalLossResult as dict
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

    # Cultural and temporal loss (new axes)
    cultural = compute_cultural_loss(source_text, target_text)
    temporal = compute_temporal_loss(source_text, target_text)

    # 5-axis total loss: weighted average including cultural/temporal
    # Cultural/temporal contribute as loss (not preservation), so they add to loss
    rq = scores.r_qualia if scores.r_qualia is not None else 0.5
    base_loss = 1.0 - (0.30 * scores.r_struct + 0.30 * scores.r_context + 0.25 * float(rq))
    cultural_temporal_loss = 0.075 * cultural.loss_estimate + 0.075 * temporal.loss_estimate
    total_loss = min(1.0, base_loss + cultural_temporal_loss)

    return LossVector(
        r_struct=scores.r_struct,
        r_context=scores.r_context,
        r_qualia=scores.r_qualia,
        r_cultural=cultural.loss_estimate,
        r_cultural_indeterminacy=cultural.indeterminacy,
        r_temporal=temporal.loss_estimate,
        r_temporal_indeterminacy=temporal.indeterminacy,
        total_loss=total_loss,
        profile_type=scores.profile_type,
        cultural_detail={
            "cultural_distance": cultural.cultural_distance,
            "holistic_dependency": cultural.holistic_dependency,
            "concept_gaps": cultural.concept_gaps,
        },
        temporal_detail={
            "paradigm_distance": temporal.paradigm_distance,
            "semantic_drift": temporal.semantic_drift,
            "web_decay": temporal.web_decay,
            "incommensurable_concepts": temporal.incommensurable_concepts,
            "era_source": temporal.era_source,
            "era_target": temporal.era_target,
        },
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
