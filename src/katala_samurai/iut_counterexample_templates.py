from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IUTCounterexampleTemplate:
    lemma_id: str
    failure_condition: str
    check_rule: str
    severity: str = "high"


def build_iut_counterexample_templates_v1() -> list[IUTCounterexampleTemplate]:
    return [
        IUTCounterexampleTemplate("L1-001", "encoding_not_total", "exists object: not encodable(object)"),
        IUTCounterexampleTemplate("L1-002", "local_inconsistency", "exists phi: prove(phi) and prove(not phi)"),
        IUTCounterexampleTemplate("L2-001", "object_extraction_failure", "exists theory in {GR,QM}: extract(theory)==empty"),
        IUTCounterexampleTemplate("L2-002", "no_common_invariants", "intersection(inv_GR, inv_QM)==empty"),
        IUTCounterexampleTemplate("L3-001", "bridge_nonexistence", "not exists f: bridge_map(f,GR,QM)"),
        IUTCounterexampleTemplate("L3-002", "ill_formed_morphism", "exists f: bridge_map and not well_formed(f)"),
        IUTCounterexampleTemplate("L4-001", "invariant_not_preserved", "exists inv: preserved_before_after(inv)==false"),
        IUTCounterexampleTemplate("L4-002", "counterexample_gate_bypass", "exists cex: inconsistent(cex) and accepted(cex)"),
        IUTCounterexampleTemplate("L5-001", "non_observable_projection", "exists inv: projection(inv)==none"),
        IUTCounterexampleTemplate("L5-002", "invalid_unified_claim", "accepted(unified_claim) and (not preserved or not observable)"),
    ]


def counterexample_template_index() -> dict[str, dict[str, str]]:
    return {
        t.lemma_id: {
            "failure_condition": t.failure_condition,
            "check_rule": t.check_rule,
            "severity": t.severity,
        }
        for t in build_iut_counterexample_templates_v1()
    }
