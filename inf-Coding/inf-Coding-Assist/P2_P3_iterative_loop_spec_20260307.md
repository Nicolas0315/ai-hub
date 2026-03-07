# P2/P3 Iterative Loop Spec v1 — 2026-03-07

## Purpose

This document defines the core iterative loop for Katala GUT after L1/S1/P1 preparation.
The loop is:

1. P2 bridges all P1-submitted geometry programs through IUT.
2. P2 attempts to produce either a direct Euclidean bridge structure or a local/limit Euclidean bridge structure.
3. P3 runs the Euclidean-recovered program.
4. If P3 cannot run the recovered program, P2 is revised and the loop repeats.

## Layer roles

### P2
P2 is the IUT bridge layer.
Its job is to take all geometry programs submitted by P1 and bridge them into a form that is either directly Euclidean or Euclidean-recoverable through local/limit structure.

### P3
P3 is the Euclidean-executed computation layer.
Its job is to run the program that has already been reduced or recoverably bridged into Euclidean geometry.
P3 therefore tests whether P2's bridge result is computationally runnable.

## P2 responsibilities

P2 must define:
- which P1-submitted geometry programs are being bridged,
- which mediation profile is being used,
- whether the result is direct-Euclid or local/limit-Euclid bridgeable,
- which invariants must be preserved,
- which Euclidean-usable outputs are produced for P3.

### Required P2 output fields
- `mediation_profile`
- `input_geometries`
- `bridge_fields`
- `invariant_targets`
- `euclid_bridge_mode`
- `euclidean_usable_outputs`
- `revision_id`

## P3 responsibilities

P3 must:
- receive the Euclidean-usable outputs from P2,
- run the recovered Euclidean program,
- if direct Euclidean execution fails, test local execution,
- if local execution fails, test limit execution,
- if all fail, return feedback for P2 revision.

### Required P3 output fields
- `computation_input`
- `direct_euclid_execution`
- `local_euclid_execution`
- `limit_euclid_execution`
- `failure_reason`
- `feedback_to_p2`

## Acceptance logic

### Case A
If `direct_euclid_execution == true`, the loop is considered successful.

### Case B
If direct execution fails but `local_euclid_execution == true`, the loop is conditionally successful.

### Case C
If direct and local execution fail but `limit_euclid_execution == true`, the loop is conditionally successful.

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
