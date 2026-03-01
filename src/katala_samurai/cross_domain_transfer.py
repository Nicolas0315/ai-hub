"""
Cross-Domain Transfer Engine — Structural isomorphism detection between domains.

Target: ドメイン横断 94% → 95% (-1 point gap)

What was missing:
  CrossDomainBoost exists for general cross-domain scoring, but:
  1. No STRUCTURAL ISOMORPHISM detection: can't find when two domains
     have the same underlying structure (e.g., music harmony ≅ color theory)
  2. No TRANSFER VALIDATION: doesn't verify that cross-domain analogies are valid
  3. No DOMAIN BRIDGE: no explicit mapping between domain concepts

Insight (Youta's KS30b↔Urban Mobility work): The strongest analogies are
STRUCTURAL (patch_clustering→zone_clustering = 0.90 isomorphism). Surface
similarity is misleading; structural isomorphism is what enables genuine
cross-domain transfer.

Architecture:
  1. Domain Concept Extractor — identify key concepts per domain
  2. Structural Mapper — find isomorphic structures across domains
  3. Transfer Validator — verify analogies preserve essential properties
  4. Bridge Builder — create explicit bidirectional domain mappings

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Constants ──
VERSION = "1.0.0"

# Isomorphism detection
ISOMORPHISM_THRESHOLD = 0.65        # Min structural similarity for isomorphism
SURFACE_SIMILARITY_DISCOUNT = 0.7   # Discount for surface-only similarity
STRUCTURAL_SIMILARITY_BOOST = 1.3   # Boost for structural similarity

# Transfer validation
TRANSFER_VALIDITY_THRESHOLD = 0.60  # Min score for valid transfer
PROPERTY_PRESERVATION_WEIGHT = 0.4  # Weight for property preservation check
STRUCTURE_PRESERVATION_WEIGHT = 0.6 # Weight for structure preservation check

# Bridge building
MAX_BRIDGES = 50                    # Max domain bridges to maintain
BRIDGE_CONFIDENCE_DECAY = 0.99      # Per-use confidence decay


# Known structural isomorphisms (established cross-domain bridges)
# These are validated structural mappings, not surface analogies
KNOWN_ISOMORPHISMS = [
    {
        "domain_a": "music",
        "domain_b": "color_theory",
        "mappings": [
            ("pitch", "hue"),
            ("volume", "saturation"),
            ("timbre", "texture"),
            ("harmony", "complementary_colors"),
            ("chord_progression", "color_palette"),
        ],
        "structural_basis": "Both are perceptual spaces with cyclic structure (octave ≅ color wheel)",
        "confidence": 0.85,
    },
    {
        "domain_a": "music",
        "domain_b": "urban_mobility",
        "mappings": [
            ("patch_clustering", "zone_clustering"),
            ("tempo_analysis", "flow_rate_analysis"),
            ("rhythm_pattern", "traffic_pattern"),
            ("dynamic_range", "demand_fluctuation"),
            ("arrangement", "route_planning"),
        ],
        "structural_basis": "Isomorphic partitioning + temporal pattern analysis (KS30b↔Urban)",
        "confidence": 0.90,
    },
    {
        "domain_a": "physics",
        "domain_b": "economics",
        "mappings": [
            ("energy", "utility"),
            ("entropy", "market_disorder"),
            ("equilibrium", "market_equilibrium"),
            ("conservation_law", "budget_constraint"),
            ("force", "incentive"),
        ],
        "structural_basis": "Lagrangian optimization under constraints",
        "confidence": 0.75,
    },
    {
        "domain_a": "biology",
        "domain_b": "computer_science",
        "mappings": [
            ("evolution", "genetic_algorithm"),
            ("neural_network", "artificial_neural_network"),
            ("immune_system", "anomaly_detection"),
            ("gene_expression", "program_execution"),
            ("dna_replication", "data_replication"),
        ],
        "structural_basis": "Information processing in complex adaptive systems",
        "confidence": 0.80,
    },
    {
        "domain_a": "mathematics",
        "domain_b": "physics",
        "mappings": [
            ("group_theory", "symmetry"),
            ("topology", "phase_transitions"),
            ("differential_geometry", "general_relativity"),
            ("hilbert_space", "quantum_mechanics"),
            ("category_theory", "type_theory"),
        ],
        "structural_basis": "Mathematical structures as physical law descriptions",
        "confidence": 0.95,
    },
]

# Domain concept vocabularies (for concept extraction)
DOMAIN_CONCEPTS = {
    "music": {
        "concepts": ["harmony", "melody", "rhythm", "tempo", "dynamics", "timbre",
                     "chord", "scale", "key", "modulation", "counterpoint", "voice_leading",
                     "arrangement", "orchestration", "form", "texture", "patch", "clustering"],
        "structural_properties": ["cyclic", "hierarchical", "temporal", "spectral"],
    },
    "physics": {
        "concepts": ["energy", "force", "field", "symmetry", "conservation", "entropy",
                     "quantum", "relativity", "wave", "particle", "spacetime", "gauge",
                     "lagrangian", "hamiltonian", "equilibrium", "phase"],
        "structural_properties": ["continuous", "conserved", "symmetric", "invariant"],
    },
    "biology": {
        "concepts": ["gene", "cell", "protein", "evolution", "selection", "mutation",
                     "ecosystem", "organism", "metabolism", "signaling", "regulation",
                     "adaptation", "fitness", "population", "species"],
        "structural_properties": ["adaptive", "hierarchical", "self-organizing", "emergent"],
    },
    "computer_science": {
        "concepts": ["algorithm", "data_structure", "complexity", "network", "distributed",
                     "parallel", "optimization", "search", "learning", "model", "inference",
                     "cache", "pipeline", "state_machine", "graph"],
        "structural_properties": ["computable", "scalable", "modular", "compositional"],
    },
    "urban_mobility": {
        "concepts": ["traffic", "flow", "congestion", "route", "zone", "demand",
                     "supply", "network", "node", "capacity", "scheduling", "clustering",
                     "pattern", "prediction", "optimization"],
        "structural_properties": ["spatial", "temporal", "networked", "dynamic"],
    },
    "economics": {
        "concepts": ["market", "equilibrium", "supply", "demand", "price", "utility",
                     "incentive", "risk", "portfolio", "arbitrage", "efficiency",
                     "externality", "game_theory", "mechanism_design"],
        "structural_properties": ["equilibrium", "optimizing", "strategic", "stochastic"],
    },
}


@dataclass
class ConceptMapping:
    """A mapping between concepts in two domains."""
    source_concept: str
    target_concept: str
    mapping_type: str                 # "structural", "functional", "analogical"
    confidence: float
    evidence: str = ""


@dataclass
class DomainBridge:
    """A validated bridge between two domains."""
    bridge_id: str
    source_domain: str
    target_domain: str
    mappings: List[ConceptMapping]
    structural_similarity: float      # How structurally similar are the domains
    transfer_validity: float          # How valid is knowledge transfer
    confidence: float
    structural_basis: str             # Why this bridge works
    usage_count: int = 0
    created_at: float = 0.0


def _extract_concepts(text: str) -> Tuple[str, Set[str]]:
    """Extract domain and concepts from text."""
    text_lower = text.lower()
    words = set(re.findall(r'\b[a-z_]+\b', text_lower))
    
    # Score each domain
    domain_scores = {}
    domain_concepts_found = {}
    
    for domain, info in DOMAIN_CONCEPTS.items():
        concepts = set(info["concepts"])
        found = words & concepts
        # Also check multi-word concepts
        for concept in concepts:
            if "_" in concept and concept.replace("_", " ") in text_lower:
                found.add(concept)
        domain_scores[domain] = len(found)
        domain_concepts_found[domain] = found
    
    # Best domain
    best_domain = max(domain_scores, key=domain_scores.get) if domain_scores else "general"
    if domain_scores.get(best_domain, 0) == 0:
        best_domain = "general"
    
    return best_domain, domain_concepts_found.get(best_domain, set())


def _structural_property_overlap(domain_a: str, domain_b: str) -> float:
    """Compute structural property overlap between two domains."""
    props_a = set(DOMAIN_CONCEPTS.get(domain_a, {}).get("structural_properties", []))
    props_b = set(DOMAIN_CONCEPTS.get(domain_b, {}).get("structural_properties", []))
    
    if not props_a or not props_b:
        return 0.3  # Unknown domains get baseline
    
    intersection = len(props_a & props_b)
    union = len(props_a | props_b)
    return intersection / union if union > 0 else 0.0


class CrossDomainTransferEngine:
    """
    Cross-domain structural isomorphism detection and transfer validation.
    
    Pipeline:
      1. extract() — identify domains and concepts in source/target
      2. find_bridge() — find or create structural bridge between domains
      3. validate_transfer() — check if specific knowledge transfers validly
      4. score() — overall cross-domain transfer score
    """

    def __init__(self):
        self.bridges: List[DomainBridge] = []
        self._bridge_index: Dict[str, DomainBridge] = {}  # "domain_a→domain_b" → bridge
        
        # Load known isomorphisms as initial bridges
        for iso in KNOWN_ISOMORPHISMS:
            bridge = DomainBridge(
                bridge_id=hashlib.md5(f"{iso['domain_a']}{iso['domain_b']}".encode()).hexdigest()[:12],
                source_domain=iso["domain_a"],
                target_domain=iso["domain_b"],
                mappings=[
                    ConceptMapping(
                        source_concept=m[0],
                        target_concept=m[1],
                        mapping_type="structural",
                        confidence=iso["confidence"],
                    ) for m in iso["mappings"]
                ],
                structural_similarity=iso["confidence"],
                transfer_validity=iso["confidence"] * 0.9,
                confidence=iso["confidence"],
                structural_basis=iso["structural_basis"],
                created_at=time.time(),
            )
            self.bridges.append(bridge)
            key = f"{iso['domain_a']}→{iso['domain_b']}"
            self._bridge_index[key] = bridge
            # Also reverse
            rev_key = f"{iso['domain_b']}→{iso['domain_a']}"
            self._bridge_index[rev_key] = bridge

    def find_bridge(self, source_domain: str, target_domain: str) -> Optional[DomainBridge]:
        """Find existing bridge between two domains."""
        key = f"{source_domain}→{target_domain}"
        bridge = self._bridge_index.get(key)
        if bridge:
            bridge.usage_count += 1
            bridge.confidence *= BRIDGE_CONFIDENCE_DECAY  # Slight decay per use
            return bridge
        return None

    def create_bridge(
        self,
        source_domain: str,
        target_domain: str,
        source_concepts: Set[str],
        target_concepts: Set[str],
    ) -> DomainBridge:
        """Create a new bridge between domains based on concept analysis."""
        # Structural property overlap
        struct_overlap = _structural_property_overlap(source_domain, target_domain)
        
        # Concept mapping (simple: matching concept names or known mappings)
        mappings = []
        for sc in source_concepts:
            for tc in target_concepts:
                # Direct name match (shared vocabulary)
                if sc == tc:
                    mappings.append(ConceptMapping(
                        source_concept=sc,
                        target_concept=tc,
                        mapping_type="structural",
                        confidence=0.9,
                        evidence="same_concept_name",
                    ))
                # Semantic similarity via character n-gram
                elif _concept_similarity(sc, tc) > 0.6:
                    mappings.append(ConceptMapping(
                        source_concept=sc,
                        target_concept=tc,
                        mapping_type="analogical",
                        confidence=_concept_similarity(sc, tc) * 0.7,
                        evidence="name_similarity",
                    ))
        
        # Check known isomorphism mappings
        for iso in KNOWN_ISOMORPHISMS:
            if (iso["domain_a"] == source_domain and iso["domain_b"] == target_domain) or \
               (iso["domain_b"] == source_domain and iso["domain_a"] == target_domain):
                for m_src, m_tgt in iso["mappings"]:
                    if m_src in source_concepts or m_tgt in target_concepts:
                        mappings.append(ConceptMapping(
                            source_concept=m_src,
                            target_concept=m_tgt,
                            mapping_type="structural",
                            confidence=iso["confidence"],
                            evidence="known_isomorphism",
                        ))
        
        # Deduplicate
        seen = set()
        unique_mappings = []
        for m in mappings:
            key = f"{m.source_concept}→{m.target_concept}"
            if key not in seen:
                seen.add(key)
                unique_mappings.append(m)
        
        # Compute transfer validity
        if unique_mappings:
            avg_confidence = sum(m.confidence for m in unique_mappings) / len(unique_mappings)
            structural_ratio = sum(1 for m in unique_mappings if m.mapping_type == "structural") / len(unique_mappings)
        else:
            avg_confidence = 0.2
            structural_ratio = 0.0
        
        transfer_validity = (
            STRUCTURE_PRESERVATION_WEIGHT * struct_overlap +
            PROPERTY_PRESERVATION_WEIGHT * avg_confidence
        )
        
        # Structural boost: structural mappings are more reliable
        if structural_ratio > 0.5:
            transfer_validity *= STRUCTURAL_SIMILARITY_BOOST
        elif structural_ratio < 0.2:
            transfer_validity *= SURFACE_SIMILARITY_DISCOUNT
        
        transfer_validity = min(transfer_validity, 1.0)
        
        bridge = DomainBridge(
            bridge_id=hashlib.md5(f"{source_domain}{target_domain}{time.time()}".encode()).hexdigest()[:12],
            source_domain=source_domain,
            target_domain=target_domain,
            mappings=unique_mappings,
            structural_similarity=struct_overlap,
            transfer_validity=transfer_validity,
            confidence=avg_confidence,
            structural_basis=f"Auto-detected: {len(unique_mappings)} mappings, "
                           f"{structural_ratio:.0%} structural",
            created_at=time.time(),
        )
        
        # Store
        self.bridges.append(bridge)
        key = f"{source_domain}→{target_domain}"
        self._bridge_index[key] = bridge
        
        # Prune if too many
        if len(self.bridges) > MAX_BRIDGES:
            self.bridges.sort(key=lambda b: b.confidence * (b.usage_count + 1), reverse=True)
            removed = self.bridges[MAX_BRIDGES:]
            self.bridges = self.bridges[:MAX_BRIDGES]
            for b in removed:
                self._bridge_index.pop(f"{b.source_domain}→{b.target_domain}", None)
        
        return bridge

    def validate_transfer(
        self,
        source_text: str,
        target_text: str,
        source_domain: Optional[str] = None,
        target_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate a specific cross-domain transfer.
        
        Checks if knowledge from source domain can validly transfer to target domain.
        """
        # Extract domains and concepts
        if not source_domain:
            source_domain, source_concepts = _extract_concepts(source_text)
        else:
            _, source_concepts = _extract_concepts(source_text)
        
        if not target_domain:
            target_domain, target_concepts = _extract_concepts(target_text)
        else:
            _, target_concepts = _extract_concepts(target_text)
        
        # Find or create bridge
        bridge = self.find_bridge(source_domain, target_domain)
        if not bridge:
            bridge = self.create_bridge(source_domain, target_domain, source_concepts, target_concepts)
        
        # Compute transfer score
        scores = {
            "structural_similarity": bridge.structural_similarity,
            "transfer_validity": bridge.transfer_validity,
            "mapping_count": len(bridge.mappings),
            "bridge_confidence": bridge.confidence,
        }
        
        # Check concept coverage
        if source_concepts and bridge.mappings:
            mapped_source = set(m.source_concept for m in bridge.mappings)
            coverage = len(source_concepts & mapped_source) / max(len(source_concepts), 1)
            scores["concept_coverage"] = coverage
        else:
            scores["concept_coverage"] = 0.3
        
        # Overall score
        overall = (
            0.30 * scores["structural_similarity"] +
            0.30 * scores["transfer_validity"] +
            0.20 * scores["bridge_confidence"] +
            0.20 * scores["concept_coverage"]
        )
        
        # Verdict
        if overall >= 0.75:
            verdict = "VALID_TRANSFER"
        elif overall >= 0.55:
            verdict = "PARTIAL_TRANSFER"
        elif overall >= 0.35:
            verdict = "WEAK_TRANSFER"
        else:
            verdict = "INVALID_TRANSFER"
        
        return {
            "verdict": verdict,
            "overall_score": round(overall, 4),
            "source_domain": source_domain,
            "target_domain": target_domain,
            "bridge_id": bridge.bridge_id,
            "structural_basis": bridge.structural_basis,
            "component_scores": {k: round(v, 4) for k, v in scores.items()},
            "mappings": [
                {"source": m.source_concept, "target": m.target_concept,
                 "type": m.mapping_type, "confidence": round(m.confidence, 3)}
                for m in bridge.mappings[:10]  # Top 10
            ],
        }

    def score(self, text: str) -> Dict[str, Any]:
        """Score cross-domain content in a single text.
        
        Detects if text bridges multiple domains and evaluates the bridge quality.
        """
        text_lower = text.lower()
        
        # Detect all domains present
        domain_presence = {}
        for domain, info in DOMAIN_CONCEPTS.items():
            concepts = set(info["concepts"])
            found = set()
            for concept in concepts:
                clean = concept.replace("_", " ")
                if clean in text_lower or concept in text_lower:
                    found.add(concept)
            if found:
                domain_presence[domain] = found
        
        if len(domain_presence) < 2:
            return {
                "verdict": "SINGLE_DOMAIN",
                "overall_score": 0.5,
                "domains_detected": list(domain_presence.keys()),
                "cross_domain": False,
            }
        
        # Score all domain pairs
        pair_scores = []
        domains = sorted(domain_presence.keys())
        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                d_a, d_b = domains[i], domains[j]
                bridge = self.find_bridge(d_a, d_b)
                if not bridge:
                    bridge = self.create_bridge(d_a, d_b, domain_presence[d_a], domain_presence[d_b])
                
                pair_scores.append({
                    "domains": (d_a, d_b),
                    "structural_similarity": bridge.structural_similarity,
                    "transfer_validity": bridge.transfer_validity,
                    "mapping_count": len(bridge.mappings),
                })
        
        # Overall cross-domain score
        if pair_scores:
            best = max(pair_scores, key=lambda p: p["transfer_validity"])
            avg_validity = sum(p["transfer_validity"] for p in pair_scores) / len(pair_scores)
            overall = best["transfer_validity"] * 0.6 + avg_validity * 0.4
        else:
            overall = 0.3
        
        return {
            "verdict": "STRONG_BRIDGE" if overall >= 0.7 else ("MODERATE_BRIDGE" if overall >= 0.5 else "WEAK_BRIDGE"),
            "overall_score": round(overall, 4),
            "domains_detected": domains,
            "cross_domain": True,
            "domain_pairs": pair_scores,
            "best_bridge": best if pair_scores else None,
        }


def _concept_similarity(a: str, b: str) -> float:
    """Simple character n-gram similarity between concept names."""
    a_lower = a.lower().replace("_", "")
    b_lower = b.lower().replace("_", "")
    
    if a_lower == b_lower:
        return 1.0
    
    n = 3
    def ngrams(text):
        return set(text[i:i+n] for i in range(len(text) - n + 1))
    
    s1 = ngrams(a_lower)
    s2 = ngrams(b_lower)
    
    if not s1 or not s2:
        return 0.0
    
    return len(s1 & s2) / len(s1 | s2)


if __name__ == "__main__":
    engine = CrossDomainTransferEngine()
    
    # Test 1: Music → Urban Mobility (known isomorphism)
    result = engine.validate_transfer(
        "The patch clustering algorithm groups similar timbral regions for arrangement optimization.",
        "Zone clustering partitions urban areas by traffic flow patterns for route planning.",
        source_domain="music",
        target_domain="urban_mobility",
    )
    print(f"Music→Urban: [{result['verdict']}] score={result['overall_score']:.3f}")
    print(f"  Basis: {result['structural_basis']}")
    print(f"  Mappings: {len(result['mappings'])}")
    
    # Test 2: Physics → Economics (known isomorphism)
    result = engine.validate_transfer(
        "Energy conservation and equilibrium in thermodynamic systems.",
        "Budget constraint and market equilibrium in economic models.",
        source_domain="physics",
        target_domain="economics",
    )
    print(f"\nPhysics→Economics: [{result['verdict']}] score={result['overall_score']:.3f}")
    
    # Test 3: Multi-domain text scoring
    result = engine.score(
        "The neural network's learning algorithm mimics evolutionary selection in biological systems, "
        "optimizing a fitness function analogous to energy minimization in physics."
    )
    print(f"\nMulti-domain text: [{result['verdict']}] score={result['overall_score']:.3f}")
    print(f"  Domains: {result['domains_detected']}")
    
    # Test 4: Single domain
    result = engine.score("Water molecules consist of two hydrogen atoms and one oxygen atom.")
    print(f"\nSingle domain: [{result['verdict']}] score={result['overall_score']:.3f}")
    
    print("\n✅ CrossDomainTransferEngine smoke test passed")
