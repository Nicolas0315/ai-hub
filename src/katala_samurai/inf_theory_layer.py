from __future__ import annotations

from typing import Any

from .iut_counterexample_templates import counterexample_template_index
from .iut_physical_projection_map import physical_projection_index


def run_inf_theory_layer(prompt: str, unified: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inf-Theory layer after KQ formal probe.

    Purpose:
    - Bridge KQ formal outputs with IUT-style theory modeling metadata
    - Produce machine-readable theory model snapshot for GR/QM unification workflows
    """
    u = unified or {}
    inv = (u.get("inter_universal_invariants") or {}) if isinstance(u, dict) else {}
    kq3 = (u.get("kq3_mode") or {}) if isinstance(u, dict) else {}

    inv_score = float(inv.get("invariant_preservation_score", 0.0) or 0.0)
    cx_ok = bool(((inv.get("counterexample_invariant") or {}).get("consistent", False)))
    truth_conflict = bool(inv.get("truth_conflict", False))
    observable_map = physical_projection_index()

    consistency_score = max(0.0, min(1.0, inv_score if not truth_conflict else inv_score * 0.5))
    counterexample_resilience = 1.0 if cx_ok else 0.0
    observable_projection_score = 1.0 if len(observable_map) > 0 else 0.0
    unified_admissibility = 1.0 if (consistency_score >= 0.72 and counterexample_resilience >= 1.0 and observable_projection_score >= 1.0) else 0.0

    weighted_total = round(
        0.35 * consistency_score
        + 0.25 * counterexample_resilience
        + 0.25 * observable_projection_score
        + 0.15 * unified_admissibility,
        4,
    )

    return {
        "enabled": True,
        "schema_version": "inf-theory-v1",
        "layer": "inf-theory",
        "goal": "gr_qm_unification_theory_modeling",
        "input": {
            "prompt": (prompt or "")[:400],
            "kq3_mode": kq3,
        },
        "scores": {
            "consistency_score": round(consistency_score, 4),
            "counterexample_resilience": round(counterexample_resilience, 4),
            "observable_projection_score": round(observable_projection_score, 4),
            "unified_admissibility": round(unified_admissibility, 4),
            "weighted_total": weighted_total,
        },
        "assets": {
            "counterexample_templates": counterexample_template_index(),
            "physical_projection_map": observable_map,
        },
        "status": {
            "strict_recommended": bool(weighted_total < 0.72),
            "truth_conflict": truth_conflict,
            "counterexample_consistent": cx_ok,
        },
        "unification_theory_model": {
            "name": "gr_qm_iut_unification_candidate",
            "adopted": bool(weighted_total >= 0.72),
            "scores": {
                "weighted_total": weighted_total,
                "consistency_score": round(consistency_score, 4),
                "counterexample_resilience": round(counterexample_resilience, 4),
                "observable_projection_score": round(observable_projection_score, 4),
                "unified_admissibility": round(unified_admissibility, 4),
            },
            "relativity_foundation": {
                "version": "sr-gr-core-v1",
                "special_relativity": {
                    "minkowski_line_element_latex": "ds^2=-c^2dt^2+dx^2+dy^2+dz^2",
                    "lorentz_transform_x_latex": "x'=\\gamma(x-vt), t'=\\gamma(t-vx/c^2), \\gamma=1/\\sqrt(1-v^2/c^2)",
                    "energy_momentum_relation_latex": "E^2=(pc)^2+(mc^2)^2",
                },
                "general_relativity": {
                    "metric_line_element_latex": "ds^2=g_{\\mu\\nu}dx^\\mu dx^\\nu",
                    "geodesic_equation_latex": "d^2x^\\mu/d\\tau^2+\\Gamma^\\mu_{\\alpha\\beta}(dx^\\alpha/d\\tau)(dx^\\beta/d\\tau)=0",
                    "christoffel_symbol_latex": "\\Gamma^\\mu_{\\alpha\\beta}=\\frac{1}{2}g^{\\mu\\nu}(\\partial_\\alpha g_{\\beta\\nu}+\\partial_\\beta g_{\\alpha\\nu}-\\partial_\\nu g_{\\alpha\\beta})",
                    "einstein_field_equation_latex": "G_{\\mu\\nu}+\\Lambda g_{\\mu\\nu}=(8\\pi G/c^4)T_{\\mu\\nu}",
                    "stress_energy_conservation_latex": "\\nabla_\\mu T^{\\mu\\nu}=0",
                },
                "sr_gr_connection": {
                    "local_inertial_limit_latex": "g_{\\mu\\nu}\\to\\eta_{\\mu\\nu}",
                    "note": "GR reduces locally to SR in local inertial frames.",
                },
            },
            "quantum_foundation": {
                "version": "qm-core-v1",
                "state_space": {
                    "hilbert_space": "|\\psi\\rangle \\in \\mathcal{H}",
                    "normalization_latex": "\\langle\\psi|\\psi\\rangle=1",
                },
                "dynamics": {
                    "schrodinger_equation_latex": "i\\hbar\\frac{\\partial}{\\partial t}|\\psi(t)\\rangle=\\hat{H}|\\psi(t)\\rangle",
                    "unitary_evolution_latex": "|\\psi(t)\\rangle=U(t)|\\psi(0)\\rangle,\\ U^\\dagger U=I",
                    "von_neumann_equation_latex": "i\\hbar\\dot{\\rho}=[\\hat{H},\\rho]",
                },
                "observables_measurement": {
                    "observable_operator": "\\hat{A}=\\hat{A}^\\dagger",
                    "born_rule_latex": "P(a_i)=|\\langle a_i|\\psi\\rangle|^2",
                    "expectation_value_latex": "\\langle A\\rangle=\\langle\\psi|\\hat{A}|\\psi\\rangle=\\mathrm{Tr}(\\rho\\hat{A})",
                },
                "canonical_structure": {
                    "commutator_latex": "[\\hat{x},\\hat{p}]=i\\hbar",
                    "uncertainty_latex": "\\Delta x\\,\\Delta p\\geq \\hbar/2",
                },
                "field_theory_minimum": {
                    "kg_equation_latex": "(\\Box + m^2)\\phi=0",
                    "dirac_equation_latex": "(i\\gamma^\\mu\\partial_\\mu-m)\\psi=0",
                },
            },
        },
    }
