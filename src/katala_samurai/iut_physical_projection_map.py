from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IUTPhysicalProjection:
    invariant_id: str
    source_domain: str
    target_observable: str
    projection_rule: str
    measurable: bool = True


def build_iut_physical_projection_map_v1() -> list[IUTPhysicalProjection]:
    return [
        IUTPhysicalProjection(
            invariant_id="inv_curvature_consistency",
            source_domain="GR-geometric",
            target_observable="gravitational_wave_phase_shift",
            projection_rule="project(curvature_invariant)->phase_shift_spectrum",
        ),
        IUTPhysicalProjection(
            invariant_id="inv_quantum_dispersion",
            source_domain="QM-field",
            target_observable="spectral_line_broadening",
            projection_rule="project(field_dispersion)->line_width_distribution",
        ),
        IUTPhysicalProjection(
            invariant_id="inv_bridge_energy_scale",
            source_domain="IUT-bridge",
            target_observable="effective_energy_gap",
            projection_rule="project(bridge_scale)->energy_gap_estimator",
        ),
        IUTPhysicalProjection(
            invariant_id="inv_counterexample_stability",
            source_domain="IUT-verification",
            target_observable="prediction_residual_bound",
            projection_rule="project(stability_index)->residual_upper_bound",
        ),
        IUTPhysicalProjection(
            invariant_id="inv_unified_admissibility",
            source_domain="IUT-unified-claim",
            target_observable="multi-regime_fit_score",
            projection_rule="project(admissibility)->fit_score_across_regimes",
        ),
    ]


def physical_projection_index() -> dict[str, dict[str, object]]:
    return {
        p.invariant_id: {
            "source_domain": p.source_domain,
            "target_observable": p.target_observable,
            "projection_rule": p.projection_rule,
            "measurable": p.measurable,
        }
        for p in build_iut_physical_projection_map_v1()
    }
