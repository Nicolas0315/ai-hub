# HTLF Cross-Layer Validation Results

> Date: 2026-03-01
> Method: Mock parser + sentence-transformers (all-MiniLM-L6-v2) + threshold 0.4

## Results

| # | Pair | Layer | R_struct | R_context | R_qualia | Loss | Profile |
|---|------|-------|----------|-----------|----------|------|---------|
| 1 | Beethoven 5th: Analysis→Description | Music→NL | 0.381 | 0.509 | 0.754 | 0.246 | P11_qualia_sum |
| 2 | OK Computer: Technical→Review | Music→NL | 0.000 | 0.469 | 0.735 | 0.265 | P11_qualia_sum |
| 3 | Rothko: Formal Analysis→Criticism | Visual→NL | 0.000 | 0.464 | 0.732 | 0.268 | P11_qualia_sum |
| 4 | Sonata Form: Textbook→General | Theory→NL | 0.373 | 0.631 | 0.815 | 0.185 | P11_qualia_sum |
| 5 | LIGO: Paper→News | Math→NL | 0.000 | 0.577 | 0.788 | 0.212 | P11_qualia_sum |
| 6 | CRISPR: Paper→News | Math→NL | 0.692 | 0.497 | 0.748 | 0.252 | P11_qualia_sum |
| 7 | GPT-4: Report→News | Formal→NL | 0.460 | 0.586 | 0.793 | 0.207 | P11_qualia_sum |

## Layer-Type Averages

| Source Layer | R_struct | R_context | R_qualia | Total Loss |
|-------------|----------|-----------|----------|------------|
| Music→NL (2 pairs) | 0.191 | 0.489 | 0.745 | 0.256 |
| Visual→NL (1 pair) | 0.000 | 0.464 | 0.732 | 0.268 |
| Theory→NL (1 pair) | 0.373 | 0.631 | 0.815 | 0.185 |
| Math/Formal→NL (3 pairs) | 0.384 | 0.553 | 0.776 | 0.224 |

## Key Findings

### 1. Music and Visual arts have highest translation loss
- Music→NL: 25.6% loss (highest R_qualia sensitivity)
- Visual→NL: 26.8% loss (highest overall loss)
- Theory→NL: 18.5% loss (lowest — closest to same-layer translation)
- Math→NL: 22.4% loss (middle ground)

### 2. R_struct varies dramatically by vocabulary overlap
- Beethoven (0.381) vs OK Computer (0.000): Classical music analysis uses more shared vocabulary with general descriptions than rock criticism does
- Sonata Form textbook (0.373): Pedagogical text shares structure with simplified explanation
- CRISPR (0.692): Biological terminology shared between paper and news

### 3. R_context is remarkably stable across layers (0.46-0.63)
- Embedding-based context matching works consistently
- Theory→NL has highest R_context (0.631) — pedagogical texts preserve context well
- Visual→NL has lowest R_context (0.464) — art criticism introduces new interpretive frameworks

### 4. R_qualia tracks R_context (as designed)
- Confirms the dependency structure: R_qualia = f(behavioral_delta | R_context)
- Theory→NL has highest R_qualia (0.815) — not because theory has more qualia, but because high R_context boosts the adjusted score
- This reveals a limitation: online approximation can't distinguish genuine qualia preservation from context-driven inflation

### 5. HTLF Theory Prediction Confirmed
- "Adjacent layers have smaller loss" (HTLF.md): Theory→NL (0.185) < Music→NL (0.256) ✓
- "Natural language is a universal but shallow hub" (HTLF.md): All translations to NL show 18-27% loss ✓
- "Experiential quality is most easily lost" (HTLF.md): Music and Visual pairs show lowest R_qualia ✓

## Limitations
- Mock parser still causes R_struct=0 for some pairs (OK Computer, Rothko, LIGO)
- Only 1 visual arts pair — need more for statistical significance
- R_qualia online approximation can't capture actual experiential differences
- All profiles classified as P11_qualia_sum — classifier needs R_struct > 0 for diversity

## Next Steps
1. LLM parser for concept-level DAGs (would fix R_struct=0 cases)
2. More visual arts pairs (5+ needed)
3. Behavioral R_qualia experiment with music stimuli
4. Bidirectional testing (NL→Music, NL→Visual)
