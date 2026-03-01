# KS Urban Mobility — Specification

## Overview

KS Urban Mobility applies the KS30b S2→S7 pipeline architecture to urban mobility data,
demonstrating HTLF cross-domain translation from music (KS30b) to smart city analytics.

**Design:** Youta Hilono  
**Implementation:** Shirokuma

## Architecture: KS30b ↔ Urban Mapping

| Stage | KS30b (Music) | Urban Mobility | Structural Parallel |
|-------|--------------|----------------|-------------------|
| S2 | Harmonic structure → key_concepts | JSON schema → key_concepts | Both extract semantic structure from raw signal |
| S3 | Spectral patch clustering | Spatial grid clustering | Frequency bins ≈ lat/lng grid cells |
| S4 | Chord/energy/CNN patch selection | Mobility × environment × infra correlation | Multi-dimensional feature matching |
| S5 | Griffin-Lim phase estimation | Timestamp sync + temporal patterns | Signal reconstruction ≈ time-series analysis |
| S6 | Spectrogram self-critique | TrustScorer 4-axis | Quality self-assessment (different axes) |
| S7 | Theory reference via key_concepts | Urban planning paper search | Identical mechanism: concept → OpenAlex |

## R_struct Definition

Four structural relation types for urban data:

| Relation | Definition | Analogy to KS30b |
|----------|-----------|-----------------|
| `spatial_proximity` | How spatially clustered observations are | Spectral coherence |
| `temporal_correlation` | Strength of temporal patterns (periodicity, trends) | Rhythmic regularity |
| `causal_dependency` | Cross-modal causal links (traffic → air quality) | Harmonic→timbral dependencies |
| `environmental_impact` | Environment-mobility correlation strength | Acoustic environment effects |

Composite: `0.3×spatial + 0.25×temporal + 0.25×causal + 0.2×environmental`

## KCS-2a Urban: Cross-Regional Concept Mapping

### SG / US / EU Equivalences

| Canonical Concept | SG | US | EU | Confidence |
|-------------------|----|----|-----|-----------|
| ride_demand | taxi-availability | ride-hail demand | MaaS load | 0.85 |
| traffic_density | traffic-speedband | traffic flow volume | road occupancy rate | 0.90 |
| air_quality_index | PSI | AQI | CAQI | 0.80 |
| public_transit_load | bus-arrival / mrt-status | GTFS real-time | NeTEx / SIRI | 0.75 |
| parking_availability | carpark-availability | parking sensors | DATEX II | 0.90 |
| weather_conditions | weather-forecast | NOAA API | ECMWF | 0.95 |

**Key insight:** SG taxi-availability measures *supply* (available vehicles), while US ride-hail
demand measures *demand* (passenger requests). They are **inverse representations** of the same
underlying concept. This is a textbook case of HTLF translation loss — the structural relation
is preserved but the semantic orientation is flipped.

### Translation Loss (SG → US)

Measured via `compute_urban_translation_loss()`:
- **Structural overlap:** Schema/format similarity
- **Semantic distance:** Concept-level divergence (accounts for inverse relationships)
- **Relation preservation:** How well R_struct maps across regions
- **Composite loss:** Geometric mean of gaps

## KS30b ↔ Urban Cross-Domain Analogies

| Music (KS30b) | Urban Mobility | Type | Strength |
|---------------|---------------|------|----------|
| chroma_profile | spatial_density_map | structural | 0.70 |
| tempo | traffic_flow_rate | temporal | 0.80 |
| beat_grid | signal_timing_grid | temporal | 0.85 |
| patch_clustering | zone_clustering | structural | 0.90 |
| spectral_centroid | spatial_centroid | spectral | 0.75 |
| chord_progression | route_sequence | structural | 0.60 |

**Strongest analogy:** `patch_clustering → zone_clustering` (0.90) — the S3 stage
is structurally identical between domains. Frequency bins and lat/lng grid cells
are isomorphic partitioning strategies.

## Trust Model (S6)

4-axis assessment:

| Axis | Weight | Definition |
|------|--------|-----------|
| Freshness | 0.30 | Exponential decay from data age |
| Provenance | 0.25 | Source reliability (SG=0.9, US=0.8, EU=0.85) |
| Verification | 0.25 | Internal consistency (null rate, dedup) |
| Accessibility | 0.20 | Schema completeness (normalized at 10 keys) |

## Woven City Application Path

Toyota Woven City (Susono, Japan) as target for comparative analysis:

1. **Data mapping:** Woven City APIs → KS Urban schema (new source region "JP_WOVEN")
2. **Baseline comparison:** SG (dense tropical city-state) vs JP_WOVEN (purpose-built greenfield)
3. **Translation loss measurement:** How much urban planning knowledge transfers between
   organic cities (SG) and designed cities (Woven City)?
4. **Hypothesis:** Designed cities should have *lower* R_struct loss (more explicit structure)
   but potentially *higher* R_qualia loss (less emergent/organic behavioral patterns)

## Files

- `src/katala_samurai/ks_urban_mobility.py` — S2-S7 pipeline + R_struct
- `src/katala_samurai/kcs2a_urban.py` — Cross-regional mapping + cross-domain loss
- `docs/KS_URBAN_MOBILITY_SPEC.md` — This document
