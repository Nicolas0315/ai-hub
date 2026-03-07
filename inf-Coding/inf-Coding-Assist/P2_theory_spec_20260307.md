# P2 Theory Spec (Draft) — 2026-03-07

## Core role

P2 is the IUT bridge layer of Katala GUT.
It does **not** perform final unified computation by itself.
Its role is to bridge the source components of relativity and quantum theory so that L3 can run unified computation and attempt Euclidean recovery.

## Six source components

### Quantum side
- `Q_time`
- `Q_space`
- `Q_dimension`

### Relativity side
- `R_time`
- `R_space`
- `R_dimension`

## Interpretation

- Relativity's strength is that it does not separate time and space too aggressively.
- Quantum theory often treats field description, time description, and dimension description in a more split manner.
- Therefore Katala should mediate these six components in P2, then unify them in a higher layer.

## P2 objective

P2 should build bridges for:
- `Q_time <-> R_time`
- `Q_space <-> R_space`
- `Q_dimension <-> R_dimension`

And then expose these as:
- `unified_time`
- `unified_space`
- `unified_dimension`

for L3 computation.

## L3 objective after P2

L3 is the unified computation layer.
If the unified computation can be reduced directly into Euclidean geometry, that is sufficient.
If not, local and/or limit Euclidean recovery is acceptable.

So the intended logic is:
1. P2 bridges quantum and relativity components through IUT.
2. L3 computes in the unified higher layer.
3. If possible, L3 reduces the result into continuous-dimensional Euclidean geometry.
4. Otherwise L3 accepts local/limit Euclidean recovery.

## Dimensional note

Current working intuition: by existing relativity-style dimensional counting, the unified description may require at least an 8-dimensional spacetime-like carrier.
This remains a working estimate, not yet a final theorem.
