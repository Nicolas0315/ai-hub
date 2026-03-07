# P2 Theory Spec (Draft) — 2026-03-07

## Core role

P2 is the IUT bridge layer of Katala GUT.
Its role is to take **all P1-submitted geometry programs** and bridge them into either:
1. a structure directly bridgeable into Euclidean geometry, or
2. a structure bridgeable into Euclidean geometry through local and/or limit recovery.

P2 is therefore the layer that organizes all submitted geometry programs into Euclid-direct or Euclid-recoverable bridge structures.

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

## P3 objective after P2

P3 is the layer where the Euclidean-recovered program actually runs.
P2 should already have produced either:
- a direct Euclidean bridge structure, or
- a local/limit Euclidean bridge structure.

So the intended logic is:
1. P2 bridges all relevant P1-submitted geometry programs through IUT.
2. P2 outputs either direct-Euclid or local/limit-Euclid bridge structure.
3. P3 runs the Euclidean-recovered program.
4. If the program cannot be run in direct Euclidean form, P3 accepts local/limit recovery execution.
5. If even that fails, the result becomes feedback for revising P2.

## Dimensional note

Current working intuition: by existing relativity-style dimensional counting, the unified description may require at least an 8-dimensional spacetime-like carrier.
This remains a working estimate, not yet a final theorem.
