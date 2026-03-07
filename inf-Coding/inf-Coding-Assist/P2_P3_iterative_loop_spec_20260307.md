# P2/P3 Iterative Loop Spec v1 — 2026-03-07

## Purpose

This document defines the core iterative loop for Katala GUT after L1/S1/P1 preparation.
The loop is:

1. P2 bridges geometry used in relativity and geometry used in quantum theory.
2. P3 performs unified computation on top of the P2 bridge result.
3. P3 attempts Euclidean recovery.
4. If recovery fails, P2 is revised and the loop repeats.

## Layer roles

### P2
P2 is the IUT bridge layer.
Its job is to connect relativity-side geometry and quantum-side geometry.
P2 does not finalize the theory and does not decide final Euclidean recovery by itself.

### P3
P3 is the unified computation layer.
Its job is to calculate on top of P2-mediated structures and test whether the result can be reduced into Euclidean geometry.
P3 is also the evaluation layer for P2 quality.

## P2 responsibilities

P2 must define:
- which relativity geometry is being connected,
- which quantum geometry is being connected,
- which mediation profile is being used,
- which invariants must be preserved,
- which unified fields are produced for P3.

### Required P2 output fields
- `mediation_profile`
- `input_geometries`
- `bridge_fields`
- `invariant_targets`
- `unified_outputs`
- `revision_id`

## P3 responsibilities

P3 must:
- receive the unified outputs from P2,
- run unified computation,
- test direct Euclidean reduction,
- if direct reduction fails, test local recovery,
- if local recovery fails, test limit recovery,
- if all fail, return feedback for P2 revision.

### Required P3 output fields
- `computation_input`
- `direct_euclid_reduction`
- `local_euclid_recovery`
- `limit_euclid_recovery`
- `failure_reason`
- `feedback_to_p2`

## Acceptance logic

### Case A
If `direct_euclid_reduction == true`, the loop is considered successful.

### Case B
If direct reduction fails but `local_euclid_recovery == true`, the loop is conditionally successful.

### Case C
If direct and local reduction fail but `limit_euclid_recovery == true`, the loop is conditionally successful.

### Case D
If all three fail, then P2 must be revised.

## Feedback contract from P3 to P2

When P3 fails to recover Euclidean structure, it should return structured feedback such as:
- mismatch in time bridge,
- mismatch in space bridge,
- mismatch in dimension bridge,
- invariant preservation failure,
- causality/evolution incompatibility,
- dimensional inconsistency,
- non-recoverable geometry pairing.

This feedback becomes the next P2 revision target.

## Main design principle

Katala should not assume a perfect P2 at first attempt.
Instead, Katala should improve P2 through repeated testing by P3.

So the core design is:

> P2 bridges → P3 computes → Euclidean recovery test → if failure then revise P2.

## Relation to new axioms

Discovery of genuinely new axioms is not the first requirement in this loop.
If existing geometries plus IUT mediation and P3 recovery are sufficient, Katala GUT may proceed without new axioms.
Only when the loop repeatedly fails in a structurally irreducible way should new axioms be considered.
