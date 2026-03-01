"""
KS Urban Mobility — Katala Samurai Urban Domain Extension

Architecture (KS30b S2-S7 applied to urban mobility):
  S2: Semantic structure extraction from SG JSON → key_concepts / implicit_assumptions
  S3: Spatial patch clustering — lat/lng grid division + observation point clustering
  S4: Cross-modal correlation — mobility × environment × infrastructure
  S5: Temporal synchronization — timestamp sync + time-series pattern detection
  S6: TrustScorer — 4-axis self-analysis (freshness / provenance / verification / accessibility)
  S7: Theory reference — key_concepts-based urban planning paper search

R_struct relations:
  spatial_proximity, temporal_correlation, causal_dependency, environmental_impact

Design: Youta Hilono (@visz_cham)
Implementation: Shirokuma
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ═══ Configuration ═══

GRID_SIZE_DEG: float = 0.005  # ~500m grid cells
TEMPORAL_WINDOW_SEC: int = 300  # 5-minute sync window
CORRELATION_THRESHOLD: float = 0.3
MAX_PAPERS: int = 5
FRESHNESS_DECAY_HOURS: float = 24.0
MIN_CLUSTER_SIZE: int = 3


@dataclass
class UrbanConfig:
    """Configuration for urban mobility pipeline."""

    grid_size_deg: float = GRID_SIZE_DEG
    temporal_window_sec: int = TEMPORAL_WINDOW_SEC
    correlation_threshold: float = CORRELATION_THRESHOLD
    max_papers: int = MAX_PAPERS
    freshness_decay_hours: float = FRESHNESS_DECAY_HOURS
    min_cluster_size: int = MIN_CLUSTER_SIZE


# ═══ S2: Semantic Structure Extraction ═══

@dataclass
class UrbanStructure:
    """Semantic structure extracted from urban data source."""

    key_concepts: list[str] = field(default_factory=list)
    implicit_assumptions: list[str] = field(default_factory=list)
    semantic_domain: str = "urban_mobility"
    data_schema: dict[str, Any] = field(default_factory=dict)
    source_region: str = ""
    observation_count: int = 0
    temporal_range: tuple[str, str] | None = None


def extract_urban_structure(data: dict | list, source: str = "SG") -> UrbanStructure:
    """S2: Extract semantic structure from urban API JSON response.

    Analyzes JSON schema to identify key concepts (taxi availability,
    air quality, traffic camera positions), derives implicit assumptions
    (uniform spatial distribution, real-time freshness), and tags the
    semantic domain.

    Parameters
    ----------
    data : dict | list
        Raw JSON response from urban data API (e.g., data.gov.sg).
    source : str
        Source region code: "SG", "US", "EU" (default "SG").

    Returns
    -------
    UrbanStructure
        Populated structure with concepts, assumptions, and schema info.
    """
    us = UrbanStructure(source_region=source)

    # Flatten to find schema
    if isinstance(data, dict):
        us.data_schema = _extract_schema(data)
        items = data.get("features", data.get("value", data.get("items", [])))
        if isinstance(items, list):
            us.observation_count = len(items)
    elif isinstance(data, list):
        us.observation_count = len(data)
        if data:
            us.data_schema = _extract_schema(data[0])

    # Extract concepts from schema keys
    us.key_concepts = _schema_to_concepts(us.data_schema, source)
    us.implicit_assumptions = _derive_urban_assumptions(us)

    # Temporal range detection
    us.temporal_range = _detect_temporal_range(data)

    return us


def _extract_schema(obj: dict, depth: int = 0, max_depth: int = 3) -> dict[str, Any]:
    """Recursively extract JSON schema (type + nested structure)."""
    if depth >= max_depth:
        return {"_type": type(obj).__name__}
    schema: dict[str, Any] = {}
    for k, v in obj.items():
        if isinstance(v, dict):
            schema[k] = _extract_schema(v, depth + 1, max_depth)
        elif isinstance(v, list):
            schema[k] = {"_type": "list", "_len": len(v)}
            if v and isinstance(v[0], dict):
                schema[k]["_item"] = _extract_schema(v[0], depth + 1, max_depth)
        else:
            schema[k] = {"_type": type(v).__name__}
    return schema


# SG/US/EU concept mapping (canonical → source-specific terms)
_CONCEPT_INDICATORS: dict[str, list[str]] = {
    "taxi_availability": ["taxi", "cab", "ride", "hail", "availability"],
    "traffic_flow": ["traffic", "speed", "flow", "congestion", "volume"],
    "air_quality": ["pm25", "pm10", "psi", "aqi", "pollutant", "air"],
    "weather": ["temperature", "humidity", "rainfall", "wind", "weather"],
    "camera_surveillance": ["camera", "image", "cctv", "surveillance"],
    "parking": ["parking", "carpark", "lot", "space"],
    "public_transport": ["bus", "train", "mrt", "subway", "transit"],
    "cycling": ["bike", "bicycle", "cycling", "pcn"],
}


def _schema_to_concepts(schema: dict, source: str) -> list[str]:
    """Derive key concepts from JSON schema keys."""
    flat_keys = _flatten_keys(schema)
    key_text = " ".join(flat_keys).lower()

    concepts: list[str] = []
    for concept, indicators in _CONCEPT_INDICATORS.items():
        if any(ind in key_text for ind in indicators):
            concepts.append(concept)

    # Add source-specific meta-concepts
    source_meta = {
        "SG": ["smart_nation", "data_gov_sg"],
        "US": ["open_data", "dot_api"],
        "EU": ["eu_open_data", "mobility_as_service"],
    }
    concepts.extend(source_meta.get(source, []))
    return concepts


def _flatten_keys(obj: dict, prefix: str = "") -> list[str]:
    """Flatten nested dict keys into dot-separated strings."""
    keys: list[str] = []
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        keys.append(full)
        if isinstance(v, dict) and not k.startswith("_"):
            keys.extend(_flatten_keys(v, full))
    return keys


def _derive_urban_assumptions(us: UrbanStructure) -> list[str]:
    """Derive implicit assumptions from urban data structure."""
    assumptions: list[str] = []
    if us.observation_count > 0:
        assumptions.append(
            f"Data represents {us.observation_count} discrete observations"
        )
    if "taxi_availability" in us.key_concepts:
        assumptions.append("Taxi positions represent instantaneous snapshot, not trajectories")
    if "air_quality" in us.key_concepts:
        assumptions.append("Air quality readings are point measurements, spatial interpolation assumed")
    if us.source_region == "SG":
        assumptions.append("Singapore: small island city-state, spatial scale ~50km")
    assumptions.append("Data freshness assumed unless timestamp indicates otherwise")
    return assumptions


def _detect_temporal_range(data: dict | list) -> tuple[str, str] | None:
    """Detect min/max timestamps in data."""
    timestamps: list[str] = []
    _collect_timestamps(data, timestamps)
    if len(timestamps) >= 2:
        timestamps.sort()
        return timestamps[0], timestamps[-1]
    return None


def _collect_timestamps(obj: Any, acc: list[str], depth: int = 0) -> None:
    """Recursively find timestamp-like string values."""
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
                acc.append(v)
            else:
                _collect_timestamps(v, acc, depth + 1)
    elif isinstance(obj, list):
        for item in obj[:100]:  # limit scan
            _collect_timestamps(item, acc, depth + 1)


# ═══ S3: Spatial Patch Clustering ═══

@dataclass
class SpatialPatch:
    """A spatial grid cell with aggregated observations."""

    grid_x: int
    grid_y: int
    lat_center: float
    lng_center: float
    observations: list[dict] = field(default_factory=list)
    cluster_id: int = -1

    @property
    def count(self) -> int:
        """Number of observations in this patch."""
        return len(self.observations)


def extract_spatial_patches(
    data: list[dict],
    config: UrbanConfig | None = None,
) -> list[SpatialPatch]:
    """S3: Cluster geo-located observations into spatial grid patches.

    Divides lat/lng space into grid cells and assigns each observation
    to its cell. Cells with fewer than min_cluster_size observations
    are discarded.

    Parameters
    ----------
    data : list[dict]
        List of observations with 'latitude'/'longitude' or 'lat'/'lng' fields.
    config : UrbanConfig | None
        Grid configuration. Uses defaults if None.

    Returns
    -------
    list[SpatialPatch]
        Patches with ≥ min_cluster_size observations, sorted by count descending.
    """
    cfg = config or UrbanConfig()
    grid: dict[tuple[int, int], SpatialPatch] = {}

    for obs in data:
        lat = obs.get("latitude", obs.get("lat"))
        lng = obs.get("longitude", obs.get("lng"))
        if lat is None or lng is None:
            continue

        lat, lng = float(lat), float(lng)
        gx = int(lng / cfg.grid_size_deg)
        gy = int(lat / cfg.grid_size_deg)
        key = (gx, gy)

        if key not in grid:
            grid[key] = SpatialPatch(
                grid_x=gx, grid_y=gy,
                lat_center=(gy + 0.5) * cfg.grid_size_deg,
                lng_center=(gx + 0.5) * cfg.grid_size_deg,
            )
        grid[key].observations.append(obs)

    # Filter and assign cluster IDs
    patches = [p for p in grid.values() if p.count >= cfg.min_cluster_size]
    patches.sort(key=lambda p: p.count, reverse=True)
    for i, p in enumerate(patches):
        p.cluster_id = i

    return patches


# ═══ S4: Cross-Modal Correlation ═══

@dataclass
class CrossModalCorrelation:
    """Correlation between two data modalities within spatial/temporal overlap."""

    modality_a: str
    modality_b: str
    spatial_overlap: float  # 0-1: fraction of patches with both modalities
    temporal_alignment: float  # 0-1: how well timestamps align
    correlation_strength: float  # Pearson-like: -1 to 1
    relation_type: str  # spatial_proximity | temporal_correlation | causal | environmental


def compute_cross_modal(
    patches_a: list[SpatialPatch],
    patches_b: list[SpatialPatch],
    label_a: str = "mobility",
    label_b: str = "environment",
    config: UrbanConfig | None = None,
) -> CrossModalCorrelation:
    """S4: Compute cross-modal correlation between two urban data layers.

    Measures spatial overlap (shared grid cells), temporal alignment
    (timestamp proximity), and correlation strength (observation count
    covariance) between modality A and modality B.

    Parameters
    ----------
    patches_a, patches_b : list[SpatialPatch]
        Spatial patches from two different data sources.
    label_a, label_b : str
        Human-readable modality labels.
    config : UrbanConfig | None
        Configuration for thresholds.

    Returns
    -------
    CrossModalCorrelation
        Populated correlation analysis.
    """
    cfg = config or UrbanConfig()

    # Spatial overlap: fraction of grid cells in common
    cells_a = {(p.grid_x, p.grid_y) for p in patches_a}
    cells_b = {(p.grid_x, p.grid_y) for p in patches_b}
    union = cells_a | cells_b
    intersection = cells_a & cells_b
    spatial_overlap = len(intersection) / max(len(union), 1)

    # Correlation: count covariance on shared cells
    counts_a = {(p.grid_x, p.grid_y): p.count for p in patches_a}
    counts_b = {(p.grid_x, p.grid_y): p.count for p in patches_b}
    shared = list(intersection)
    if len(shared) >= 2:
        va = [counts_a.get(c, 0) for c in shared]
        vb = [counts_b.get(c, 0) for c in shared]
        corr = _pearson(va, vb)
    else:
        corr = 0.0

    # Classify relation type
    if abs(corr) > 0.7:
        rtype = "causal_dependency"
    elif spatial_overlap > 0.5:
        rtype = "spatial_proximity"
    elif abs(corr) > cfg.correlation_threshold:
        rtype = "temporal_correlation"
    else:
        rtype = "environmental_impact"

    return CrossModalCorrelation(
        modality_a=label_a,
        modality_b=label_b,
        spatial_overlap=round(spatial_overlap, 4),
        temporal_alignment=1.0,  # TODO: implement timestamp comparison
        correlation_strength=round(corr, 4),
        relation_type=rtype,
    )


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    num = sum(a * b for a, b in zip(dx, dy))
    den = math.sqrt(sum(a * a for a in dx) * sum(b * b for b in dy))
    return num / den if den > 1e-12 else 0.0


# ═══ S5: Temporal Synchronization ═══

@dataclass
class TemporalPattern:
    """Detected temporal pattern in urban data."""

    pattern_type: str  # "periodic" | "trend" | "anomaly"
    period_hours: float | None = None
    description: str = ""
    confidence: float = 0.0


def analyze_temporal(
    observations: list[dict],
    config: UrbanConfig | None = None,
) -> list[TemporalPattern]:
    """S5: Detect temporal patterns in time-series observations.

    Analyzes observation timestamps to detect periodicity (rush hour,
    daily cycles), trends (increasing/decreasing), and anomalies
    (unexpected gaps or spikes).

    Parameters
    ----------
    observations : list[dict]
        Observations with 'timestamp' field (ISO format or epoch).
    config : UrbanConfig | None
        Configuration for temporal window size.

    Returns
    -------
    list[TemporalPattern]
        Detected patterns, sorted by confidence descending.
    """
    cfg = config or UrbanConfig()
    timestamps = _parse_timestamps(observations)
    if len(timestamps) < 3:
        return []

    patterns: list[TemporalPattern] = []

    # Detect gaps
    diffs = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    if diffs:
        avg_diff = sum(diffs) / len(diffs)
        for i, d in enumerate(diffs):
            if d > avg_diff * 3 and avg_diff > 0:
                patterns.append(TemporalPattern(
                    pattern_type="anomaly",
                    description=f"Gap at index {i}: {d:.0f}s vs avg {avg_diff:.0f}s",
                    confidence=min(1.0, d / (avg_diff * 3)),
                ))

        # Periodic detection (simple: check if median diff suggests hourly/daily cycle)
        sorted_diffs = sorted(diffs)
        median_diff = sorted_diffs[len(sorted_diffs) // 2]
        if 3000 < median_diff < 7200:
            patterns.append(TemporalPattern(
                pattern_type="periodic",
                period_hours=median_diff / 3600,
                description=f"~{median_diff / 3600:.1f}h cycle detected",
                confidence=0.6,
            ))
        elif 60 < median_diff < 600:
            patterns.append(TemporalPattern(
                pattern_type="periodic",
                period_hours=median_diff / 3600,
                description=f"~{median_diff / 60:.0f}min reporting interval",
                confidence=0.8,
            ))

    # Trend detection (linear regression on counts per hour)
    if len(timestamps) >= 10:
        hour_counts = _count_by_hour(timestamps)
        if len(hour_counts) >= 3:
            xs = list(range(len(hour_counts)))
            ys = list(hour_counts.values())
            slope = _simple_slope(xs, ys)
            if abs(slope) > 0.5:
                direction = "increasing" if slope > 0 else "decreasing"
                patterns.append(TemporalPattern(
                    pattern_type="trend",
                    description=f"{direction} trend (slope={slope:.2f}/hour)",
                    confidence=min(1.0, abs(slope) / 2),
                ))

    patterns.sort(key=lambda p: p.confidence, reverse=True)
    return patterns


def _parse_timestamps(observations: list[dict]) -> list[float]:
    """Extract and sort epoch timestamps from observations."""
    epochs: list[float] = []
    for obs in observations:
        ts = obs.get("timestamp", obs.get("time", obs.get("datetime")))
        if ts is None:
            continue
        if isinstance(ts, (int, float)):
            epochs.append(float(ts))
        elif isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                epochs.append(dt.timestamp())
            except ValueError:
                continue
    epochs.sort()
    return epochs


def _count_by_hour(timestamps: list[float]) -> dict[int, int]:
    """Count observations per hour."""
    counts: dict[int, int] = {}
    for ts in timestamps:
        hour = int(ts // 3600)
        counts[hour] = counts.get(hour, 0) + 1
    return dict(sorted(counts.items()))


def _simple_slope(xs: list[int | float], ys: list[float]) -> float:
    """Simple linear regression slope."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den > 1e-12 else 0.0


# ═══ S6: TrustScorer ═══

@dataclass
class TrustProfile:
    """4-axis trust assessment for urban data."""

    freshness: float = 0.0      # How recent the data is (0-1)
    provenance: float = 0.0     # Source reliability (0-1)
    verification: float = 0.0   # Cross-verification status (0-1)
    accessibility: float = 0.0  # Data completeness / ease of access (0-1)
    overall: float = 0.0        # Weighted composite score

    def __post_init__(self) -> None:
        """Compute overall trust score (weighted mean)."""
        weights = {"freshness": 0.3, "provenance": 0.25,
                   "verification": 0.25, "accessibility": 0.2}
        self.overall = round(
            weights["freshness"] * self.freshness +
            weights["provenance"] * self.provenance +
            weights["verification"] * self.verification +
            weights["accessibility"] * self.accessibility,
            4,
        )


# Known source provenance scores
_SOURCE_PROVENANCE: dict[str, float] = {
    "SG": 0.9,   # data.gov.sg — official government API
    "US": 0.8,   # various DOT / city APIs
    "EU": 0.85,  # EU Open Data Portal
}


def compute_trust(
    structure: UrbanStructure,
    observations: list[dict] | None = None,
    config: UrbanConfig | None = None,
) -> TrustProfile:
    """S6: Compute 4-axis trust profile for urban data.

    Evaluates data quality along four dimensions:
    - Freshness: based on temporal range vs current time
    - Provenance: based on known source reliability
    - Verification: based on internal consistency checks
    - Accessibility: based on schema completeness

    Parameters
    ----------
    structure : UrbanStructure
        S2 output with semantic structure.
    observations : list[dict] | None
        Raw observation data for verification checks.
    config : UrbanConfig | None
        Configuration for freshness decay.

    Returns
    -------
    TrustProfile
        4-axis trust assessment with overall score.
    """
    cfg = config or UrbanConfig()

    # Freshness
    freshness = 0.5  # default: unknown
    if structure.temporal_range:
        try:
            latest = datetime.fromisoformat(
                structure.temporal_range[1].replace("Z", "+00:00")
            )
            age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
            freshness = max(0.0, 1.0 - age_hours / cfg.freshness_decay_hours)
        except (ValueError, TypeError):
            pass

    # Provenance
    provenance = _SOURCE_PROVENANCE.get(structure.source_region, 0.5)

    # Verification: internal consistency
    verification = _verify_consistency(structure, observations or [])

    # Accessibility: schema completeness
    n_keys = len(_flatten_keys(structure.data_schema))
    accessibility = min(1.0, n_keys / 10)  # normalize: 10+ keys = full coverage

    return TrustProfile(
        freshness=round(freshness, 4),
        provenance=round(provenance, 4),
        verification=round(verification, 4),
        accessibility=round(accessibility, 4),
    )


def _verify_consistency(structure: UrbanStructure, observations: list[dict]) -> float:
    """Internal consistency score: check for nulls, duplicates, schema conformance."""
    if not observations:
        return 0.3  # can't verify without data

    score = 1.0
    # Check null rate
    total_fields = 0
    null_fields = 0
    for obs in observations[:100]:
        if isinstance(obs, dict):
            for v in obs.values():
                total_fields += 1
                if v is None:
                    null_fields += 1

    if total_fields > 0:
        null_rate = null_fields / total_fields
        score -= null_rate * 0.5

    # Check for duplicates (by string repr — approximate)
    sample = observations[:100]
    reprs = [json.dumps(o, sort_keys=True, default=str) for o in sample]
    unique_rate = len(set(reprs)) / max(len(reprs), 1)
    score -= (1 - unique_rate) * 0.3

    return max(0.0, round(score, 4))


# ═══ S7: Theory Reference ═══

def search_urban_papers(
    structure: UrbanStructure,
    max_papers: int = MAX_PAPERS,
) -> list[dict]:
    """S7: Search for urban planning/transport papers using key_concepts.

    Uses OpenAlex API to find relevant academic papers matching the
    extracted key concepts from S2. Returns paper metadata (title,
    DOI, relevance score).

    Parameters
    ----------
    structure : UrbanStructure
        S2 output with key_concepts.
    max_papers : int
        Maximum papers to return.

    Returns
    -------
    list[dict]
        Papers with keys: title, doi, relevance_score, source.
    """
    if not structure.key_concepts:
        return []

    # Build search query from concepts
    query_terms = [c.replace("_", " ") for c in structure.key_concepts[:5]]
    query = " ".join(query_terms)

    papers: list[dict] = []
    try:
        import urllib.request
        import urllib.parse

        url = (
            "https://api.openalex.org/works?"
            f"search={urllib.parse.quote(query)}"
            f"&per_page={max_papers}"
            "&sort=relevance_score:desc"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            result = json.loads(resp.read())
            for work in result.get("results", []):
                papers.append({
                    "title": work.get("title", ""),
                    "doi": work.get("doi", ""),
                    "relevance_score": work.get("relevance_score", 0),
                    "source": "openalex",
                    "year": work.get("publication_year"),
                })
    except Exception:
        # Fallback: return concept-based placeholders
        for concept in structure.key_concepts[:max_papers]:
            papers.append({
                "title": f"[Search unavailable] Topic: {concept}",
                "doi": None,
                "relevance_score": 0,
                "source": "fallback",
            })

    return papers


# ═══ R_struct Output ═══

@dataclass
class UrbanRStruct:
    """R_struct decomposition for urban mobility data.

    Four structural relation types, following KS30b's harmonic structure
    pattern but adapted for spatial/temporal urban data.
    """

    spatial_proximity: float = 0.0       # How spatially clustered the data is
    temporal_correlation: float = 0.0    # Temporal pattern strength
    causal_dependency: float = 0.0       # Cross-modal causal links detected
    environmental_impact: float = 0.0    # Environment-mobility correlation

    @property
    def composite(self) -> float:
        """Weighted composite R_struct score."""
        return round(
            0.3 * self.spatial_proximity +
            0.25 * self.temporal_correlation +
            0.25 * self.causal_dependency +
            0.2 * self.environmental_impact,
            4,
        )


def compute_r_struct(
    patches: list[SpatialPatch],
    correlations: list[CrossModalCorrelation],
    patterns: list[TemporalPattern],
) -> UrbanRStruct:
    """Compute R_struct from S3/S4/S5 outputs.

    Parameters
    ----------
    patches : list[SpatialPatch]
        S3 spatial patches.
    correlations : list[CrossModalCorrelation]
        S4 cross-modal correlations.
    patterns : list[TemporalPattern]
        S5 temporal patterns.

    Returns
    -------
    UrbanRStruct
        4-component structural relation score.
    """
    # Spatial: cluster density (more observations per patch = higher)
    if patches:
        counts = [p.count for p in patches]
        max_count = max(counts)
        avg_count = sum(counts) / len(counts)
        spatial = min(1.0, avg_count / max(max_count, 1))
    else:
        spatial = 0.0

    # Temporal: best pattern confidence
    temporal = max((p.confidence for p in patterns), default=0.0)

    # Causal: strongest cross-modal correlation
    causal_corrs = [
        abs(c.correlation_strength)
        for c in correlations
        if c.relation_type == "causal_dependency"
    ]
    causal = max(causal_corrs, default=0.0)

    # Environmental: environmental-type correlations
    env_corrs = [
        abs(c.correlation_strength)
        for c in correlations
        if c.relation_type == "environmental_impact"
    ]
    environmental = max(env_corrs, default=0.0)

    return UrbanRStruct(
        spatial_proximity=round(spatial, 4),
        temporal_correlation=round(temporal, 4),
        causal_dependency=round(causal, 4),
        environmental_impact=round(environmental, 4),
    )


# ═══ Main Pipeline ═══

@dataclass
class UrbanPipelineResult:
    """Complete result from urban mobility analysis pipeline."""

    structure: UrbanStructure
    patches: list[SpatialPatch]
    correlations: list[CrossModalCorrelation]
    temporal_patterns: list[TemporalPattern]
    trust: TrustProfile
    papers: list[dict]
    r_struct: UrbanRStruct


def run_ks_urban_pipeline(
    data: dict | list,
    source: str = "SG",
    secondary_data: dict | list | None = None,
    secondary_source: str = "environment",
    config: UrbanConfig | None = None,
) -> UrbanPipelineResult:
    """Run full KS Urban Mobility pipeline (S2→S7).

    Orchestrates the complete analysis flow:
    1. S2: Extract semantic structure
    2. S3: Cluster into spatial patches
    3. S4: Cross-modal correlation (if secondary data provided)
    4. S5: Temporal pattern detection
    5. S6: Trust assessment
    6. S7: Academic paper search
    7. R_struct computation

    Parameters
    ----------
    data : dict | list
        Primary urban data (e.g., taxi availability JSON).
    source : str
        Source region code (default "SG").
    secondary_data : dict | list | None
        Optional secondary data layer for cross-modal analysis.
    secondary_source : str
        Label for secondary data modality.
    config : UrbanConfig | None
        Pipeline configuration.

    Returns
    -------
    UrbanPipelineResult
        Complete analysis with all S2-S7 outputs and R_struct.
    """
    cfg = config or UrbanConfig()

    # S2: Semantic structure
    structure = extract_urban_structure(data, source)

    # Normalize data to list of observations
    observations = _to_observation_list(data)

    # S3: Spatial patches
    patches = extract_spatial_patches(observations, cfg)

    # S4: Cross-modal correlation
    correlations: list[CrossModalCorrelation] = []
    if secondary_data is not None:
        sec_obs = _to_observation_list(secondary_data)
        sec_patches = extract_spatial_patches(sec_obs, cfg)
        correlations.append(
            compute_cross_modal(patches, sec_patches, "mobility", secondary_source, cfg)
        )

    # S5: Temporal patterns
    temporal_patterns = analyze_temporal(observations, cfg)

    # S6: Trust
    trust = compute_trust(structure, observations, cfg)

    # S7: Papers
    papers = search_urban_papers(structure, cfg.max_papers)

    # R_struct
    r_struct = compute_r_struct(patches, correlations, temporal_patterns)

    return UrbanPipelineResult(
        structure=structure,
        patches=patches,
        correlations=correlations,
        temporal_patterns=temporal_patterns,
        trust=trust,
        papers=papers,
        r_struct=r_struct,
    )


def _to_observation_list(data: dict | list) -> list[dict]:
    """Normalize API response to flat list of observation dicts."""
    if isinstance(data, list):
        return data
    # Common SG data.gov.sg patterns
    for key in ("features", "value", "items", "result", "data"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return [data]
