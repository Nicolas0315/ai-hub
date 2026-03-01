"""
KCS-2a Urban — Cross-Domain Concept Mapping for Urban Mobility

Maps equivalent concepts across SG / US / EU urban data sources.
Measures translation loss between:
  1. Different regional APIs (SG taxi-availability ≈ US ride-hail demand ≈ EU MaaS load)
  2. KS30b music domain ↔ urban mobility domain (structural analogy)

Connects to Katala TrustScorer for 4-axis trust interface.

Design: Youta Hilono (@visz_cham)
Implementation: Shirokuma
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══ Cross-Regional Concept Mapping ═══

@dataclass
class ConceptMapping:
    """A mapping between equivalent concepts across regional sources."""

    canonical: str
    sg_term: str
    us_term: str
    eu_term: str
    confidence: float  # 0-1: how confident the mapping is
    notes: str = ""


# Canonical mapping table: SG/US/EU equivalences
URBAN_CONCEPT_MAP: list[ConceptMapping] = [
    ConceptMapping(
        canonical="ride_demand",
        sg_term="taxi-availability",
        us_term="ride-hail demand",
        eu_term="mobility-on-demand load",
        confidence=0.85,
        notes="SG measures supply (available taxis); US/EU measure demand. Inverse relationship.",
    ),
    ConceptMapping(
        canonical="traffic_density",
        sg_term="traffic-speedband",
        us_term="traffic flow volume",
        eu_term="road occupancy rate",
        confidence=0.9,
        notes="Different units: SG=speed bands, US=vehicles/hour, EU=percentage occupancy.",
    ),
    ConceptMapping(
        canonical="air_quality_index",
        sg_term="psi (Pollutant Standards Index)",
        us_term="AQI (Air Quality Index)",
        eu_term="CAQI (Common Air Quality Index)",
        confidence=0.8,
        notes="Different scales and pollutant weightings. PSI/AQI ≠ linear transform.",
    ),
    ConceptMapping(
        canonical="public_transit_load",
        sg_term="bus-arrival / mrt-status",
        us_term="GTFS real-time feed",
        eu_term="NeTEx / SIRI service status",
        confidence=0.75,
        notes="SG: proprietary API. US: GTFS standard. EU: NeTEx/SIRI standards.",
    ),
    ConceptMapping(
        canonical="parking_availability",
        sg_term="carpark-availability",
        us_term="parking sensor data",
        eu_term="DATEX II parking",
        confidence=0.9,
        notes="Functionally identical: real-time lot counts.",
    ),
    ConceptMapping(
        canonical="weather_conditions",
        sg_term="weather-forecast / rainfall",
        us_term="NOAA weather API",
        eu_term="ECMWF / national met services",
        confidence=0.95,
        notes="Meteorological standards are globally harmonized (WMO).",
    ),
    ConceptMapping(
        canonical="cycling_infrastructure",
        sg_term="cycling-path-network",
        us_term="bike share / cycling counts",
        eu_term="EuroVelo / cycling counters",
        confidence=0.7,
        notes="SG: infrastructure focus. US/EU: usage + infrastructure.",
    ),
    ConceptMapping(
        canonical="pedestrian_activity",
        sg_term="footfall (limited)",
        us_term="pedestrian sensor counts",
        eu_term="pedestrian zone monitoring",
        confidence=0.6,
        notes="SG has limited pedestrian data compared to US/EU smart city sensors.",
    ),
]


def get_concept_map() -> list[ConceptMapping]:
    """Return the full cross-regional concept mapping table."""
    return URBAN_CONCEPT_MAP


def find_equivalent(
    term: str,
    source_region: str = "SG",
    target_region: str = "US",
) -> ConceptMapping | None:
    """Find the equivalent concept mapping for a term across regions.

    Parameters
    ----------
    term : str
        Source term to look up (case-insensitive partial match).
    source_region : str
        Region of the source term ("SG", "US", "EU").
    target_region : str
        Target region for equivalent term.

    Returns
    -------
    ConceptMapping | None
        Matching mapping, or None if no equivalent found.
    """
    term_lower = term.lower()
    field_map = {"SG": "sg_term", "US": "us_term", "EU": "eu_term"}
    source_field = field_map.get(source_region)
    if not source_field:
        return None

    for mapping in URBAN_CONCEPT_MAP:
        source_val = getattr(mapping, source_field, "").lower()
        if term_lower in source_val or source_val in term_lower:
            return mapping
    return None


# ═══ Translation Loss Metrics (Urban) ═══

@dataclass
class UrbanTranslationLoss:
    """Translation loss between two regional data representations."""

    source_region: str
    target_region: str
    structural_overlap: float     # Schema/format similarity (0-1)
    semantic_distance: float      # Concept-level divergence (0-1, lower=closer)
    relation_preservation: float  # How well R_struct relations map (0-1)
    translation_loss: float       # Composite loss (0-1, lower=better)
    unmapped_concepts: list[str] = field(default_factory=list)


def compute_urban_translation_loss(
    concepts_a: list[str],
    concepts_b: list[str],
    region_a: str = "SG",
    region_b: str = "US",
) -> UrbanTranslationLoss:
    """Compute translation loss between two regional concept sets.

    Measures how much information is lost when translating urban data
    concepts from one regional framework to another.

    Parameters
    ----------
    concepts_a, concepts_b : list[str]
        Key concepts from each region's data.
    region_a, region_b : str
        Region codes.

    Returns
    -------
    UrbanTranslationLoss
        Detailed loss breakdown.
    """
    # Find mappable concepts
    mapped = 0
    unmapped: list[str] = []
    total_confidence = 0.0

    for concept in concepts_a:
        mapping = find_equivalent(concept, region_a, region_b)
        if mapping:
            mapped += 1
            total_confidence += mapping.confidence
        else:
            unmapped.append(concept)

    n = max(len(concepts_a), 1)
    structural_overlap = mapped / n
    avg_confidence = total_confidence / max(mapped, 1)
    semantic_distance = 1.0 - avg_confidence

    # Relation preservation: how many of region_b's concepts are covered
    reverse_mapped = 0
    for concept in concepts_b:
        if find_equivalent(concept, region_b, region_a):
            reverse_mapped += 1
    relation_pres = reverse_mapped / max(len(concepts_b), 1)

    # Composite loss: geometric mean of gaps
    loss = 1.0 - (structural_overlap * (1 - semantic_distance) * relation_pres) ** (1 / 3)

    return UrbanTranslationLoss(
        source_region=region_a,
        target_region=region_b,
        structural_overlap=round(structural_overlap, 4),
        semantic_distance=round(semantic_distance, 4),
        relation_preservation=round(relation_pres, 4),
        translation_loss=round(loss, 4),
        unmapped_concepts=unmapped,
    )


# ═══ KS30b ↔ Urban Cross-Domain Analogy ═══

@dataclass
class CrossDomainAnalogy:
    """Structural analogy between music (KS30b) and urban mobility."""

    music_concept: str
    urban_concept: str
    analogy_type: str  # "structural" | "temporal" | "spectral"
    strength: float    # 0-1


# Structural parallels: KS30b music concepts → urban mobility concepts
CROSS_DOMAIN_ANALOGIES: list[CrossDomainAnalogy] = [
    CrossDomainAnalogy("chroma_profile", "spatial_density_map", "structural", 0.7),
    CrossDomainAnalogy("tempo", "traffic_flow_rate", "temporal", 0.8),
    CrossDomainAnalogy("chord_progression", "route_sequence", "structural", 0.6),
    CrossDomainAnalogy("spectral_centroid", "spatial_centroid", "spectral", 0.75),
    CrossDomainAnalogy("key_signature", "dominant_transport_mode", "structural", 0.5),
    CrossDomainAnalogy("beat_grid", "signal_timing_grid", "temporal", 0.85),
    CrossDomainAnalogy("harmonic_series", "nested_service_areas", "structural", 0.55),
    CrossDomainAnalogy("patch_clustering", "zone_clustering", "structural", 0.9),
    CrossDomainAnalogy("gl_phase_estimation", "demand_prediction", "spectral", 0.4),
    CrossDomainAnalogy("stereo_positioning", "modal_split", "spectral", 0.45),
]


def compute_cross_domain_loss(
    music_concepts: list[str],
    urban_concepts: list[str],
) -> float:
    """Compute translation loss between KS30b music domain and urban mobility.

    Uses the structural analogy table to measure how well music-domain
    concepts transfer to urban mobility understanding.

    Parameters
    ----------
    music_concepts : list[str]
        Key concepts from music analysis.
    urban_concepts : list[str]
        Key concepts from urban data.

    Returns
    -------
    float
        Translation loss (0-1, lower = better transfer).
    """
    if not music_concepts or not urban_concepts:
        return 1.0

    matched_strength = 0.0
    matches = 0
    for analogy in CROSS_DOMAIN_ANALOGIES:
        mc_match = any(analogy.music_concept in c for c in music_concepts)
        uc_match = any(analogy.urban_concept in c for c in urban_concepts)
        if mc_match and uc_match:
            matched_strength += analogy.strength
            matches += 1

    if matches == 0:
        return 0.8  # High loss but not total — structural parallels still exist

    avg_strength = matched_strength / matches
    coverage = matches / len(CROSS_DOMAIN_ANALOGIES)
    return round(1.0 - avg_strength * coverage, 4)


# ═══ Trust Interface ═══

def trust_interface(urban_result: Any) -> dict[str, float]:
    """Interface to Katala TrustScorer: extract 4-axis trust from pipeline result.

    Parameters
    ----------
    urban_result : UrbanPipelineResult
        Result from run_ks_urban_pipeline().

    Returns
    -------
    dict[str, float]
        4-axis trust scores compatible with Katala TrustScorer format.
    """
    trust = getattr(urban_result, "trust", None)
    if trust is None:
        return {
            "freshness": 0.0,
            "provenance": 0.0,
            "verification": 0.0,
            "accessibility": 0.0,
        }
    return {
        "freshness": trust.freshness,
        "provenance": trust.provenance,
        "verification": trust.verification,
        "accessibility": trust.accessibility,
    }
