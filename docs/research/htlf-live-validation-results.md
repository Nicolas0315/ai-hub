# HTLF Live Validation Results: Real Paper-News Pairs

> Generated: 2026-02-28
> Method: Mock parser (heuristic DAG extraction), lexical matcher, heuristic R_context, online_approximation R_qualia

## Summary

5 real-world scientific paper → news article pairs were collected and run through the HTLF pipeline with `use_mock_parser=True`.

## Results

| Case | Domain | R_struct | R_context | R_qualia | total_loss | profile_type |
|------|--------|----------|-----------|----------|------------|-------------|
| 1 | LIGO Gravitational Waves | 0.000 | 0.255 | 0.628 | 0.372 | P11_qualia_sum |
| 2 | AlphaFold Protein Structure | 0.000 | 0.193 | 0.597 | 0.403 | P11_qualia_sum |
| 3 | CRISPR-Cas9 Gene Editing | 0.000 | 0.169 | 0.584 | 0.416 | P11_qualia_sum |
| 4 | mRNA Vaccine (BNT162b2) | 0.000 | 0.232 | 0.616 | 0.384 | P11_qualia_sum |
| 5 | GPT-4 Technical Report | 0.000 | 0.271 | 0.635 | 0.365 | P11_qualia_sum |

**All backends**: parser=mock, context=heuristic, qualia=online_approximation, matcher=lexical

## Comparison with Manual Annotations (htlf-validation-dataset.md)

| Case | Domain | Manual R_struct | Pipeline R_struct | Manual R_context | Pipeline R_context |
|------|--------|-----------------|-------------------|------------------|--------------------|
| 1 | LIGO | 0.45 | 0.00 | 0.55 | 0.26 |
| 5 | CRISPR | 0.35 | 0.00 | 0.35 | 0.17 |

(Cases 2, 4, 5 in pipeline correspond to different papers than cases 2-4 in annotation dataset)

## Key Findings

### 1. R_struct = 0.0 across all cases (Critical Issue)

**Root cause**: The mock parser extracts sentence-level DAG nodes. The lexical matcher uses Jaccard similarity with a 0.7 threshold. Scientific paper sentences and news article sentences share very few exact tokens (different vocabulary, framing, detail level), so **zero nodes match** → R_struct collapses to 0.0.

**Impact**: R_struct is the core structural preservation metric. Its complete failure means the pipeline cannot distinguish between "well-structured news translation" and "garbage output" in mock mode.

**Fix needed**: 
- Lower matcher threshold for mock mode (e.g., 0.3-0.4)
- Use sentence-transformer embeddings for matching (already coded but not available in this env)
- The LLM parser (`use_mock=False`) would produce concept-level nodes that match better across domains

### 2. R_context underestimates (0.17-0.27 vs manual 0.35-0.55)

The heuristic context scorer relies on token overlap and sentence-level semantic similarity. Without sentence-transformers, it falls back to Jaccard, which misses:
- Synonym groups (partially handled but limited)
- Paraphrased concepts
- Implicit context preservation

The LLM-based reader protocol would produce more accurate scores but requires API access.

### 3. R_qualia shows surprisingly narrow range (0.58-0.64)

The `online_approximation` qualia backend produces scores in a tight band because it's derived from R_context via a formula. This is expected behavior for the approximation mode — it cannot capture true experiential quality differences without behavioral or physiological data.

### 4. All cases classified as P11_qualia_sum

Because R_struct = 0.0, the profile classifier selects the qualia-only profile (highest non-zero axis). This masks the expected profile diversity across different translation types.

## Interpretation

The mock parser + lexical matcher combination is **inadequate for cross-domain paper-news comparison**. The pipeline architecture is sound — the scoring formulas, profile classification, and edge-type weighting are all well-designed — but the input layer (parser + matcher) needs semantic capabilities to handle vocabulary divergence between scientific and journalistic text.

**Confidence ranking of components**:
1. ✅ Profile classification logic — works correctly given inputs
2. ✅ Edge-type weighted R_struct formula — correct, just starved of matched nodes
3. ⚠️ Heuristic R_context — underestimates by ~50%, needs embeddings
4. ⚠️ Online R_qualia approximation — narrow range, needs behavioral data
5. ❌ Mock parser + lexical matcher — fails on cross-register text pairs

## Recommended Improvements

1. **Install sentence-transformers** in the environment → matcher and context scorer will automatically use embeddings
2. **Add a "relaxed mock" mode** with threshold=0.3 for cross-domain comparisons
3. **Run with LLM parser** (`use_mock=False` with OpenAI API) for concept-level DAG extraction
4. **Collect behavioral R_qualia data** to validate the approximation formula
5. **Add domain-specific synonym groups** to TERM_SYNONYM_GROUPS (currently only 5 groups)

## Data Files

- Source texts: `data/htlf_validation/case_{1-5}_source.txt`
- Target texts: `data/htlf_validation/case_{1-5}_target.txt`
- Cases: LIGO, AlphaFold, CRISPR, mRNA Vaccine, GPT-4
