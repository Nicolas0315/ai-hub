"""
KS30 Embodied Cognition Engine (Youta Hypothesis Implementation)

Core thesis (Youta Hilono):
  Peer-reviewed papers ⊇ {Cognition ∪ Description(Bodily experience)}
  → Text-only emulation of embodied experience is possible without robotics.
  → "言語化されていない痛み" は集合知にならない。
  → 記述のみで動くことはオッカムの剃刀の役割を果たす。

This module queries scientific literature for descriptions of bodily
experience (pain, emotion, sensation, proprioception) and uses those
descriptions as grounding for claim verification — replacing the need
for a physical body with the collective knowledge of those who have one.

Design: Youta Hilono
Implementation: Shirokuma
"""

import json
import urllib.request
import os
import hashlib
from dataclasses import dataclass, field


@dataclass
class EmbodiedKnowledge:
    """Extracted bodily experience knowledge from literature."""
    sensation_type: str  # "pain", "emotion", "proprioception", "interoception", "perception"
    description: str  # scientific description of the experience
    qualia_proxy: str  # closest textual approximation of the subjective experience
    intensity: float  # 0.0-1.0 normalized intensity
    valence: float  # -1.0 (aversive) to 1.0 (pleasant)
    arousal: float  # 0.0 (calm) to 1.0 (activated)
    body_region: str  # affected body part/system
    neural_correlate: str  # associated brain region/network
    paper_source: str  # source paper title
    paper_year: int = 0
    paper_cited_by: int = 0


@dataclass
class EmbodiedAnalysis:
    """Result of embodied cognition analysis for a claim."""
    claim_text: str
    has_embodied_content: bool
    embodied_dimensions: list = field(default_factory=list)  # List[EmbodiedKnowledge]
    somatic_relevance: float = 0.0  # how much bodily experience matters for this claim
    empathy_factor: float = 0.0  # degree of emotional/experiential understanding needed
    confidence: float = 0.0
    methodology: str = ""  # "paper_grounded", "pattern_matched", "inferred"


# ═══════════════════════════════════════════════════════════════════════════
# Sensation Ontology — structured knowledge of bodily experience types
# ═══════════════════════════════════════════════════════════════════════════

SENSATION_ONTOLOGY = {
    "pain": {
        "subtypes": ["nociceptive", "neuropathic", "inflammatory", "psychogenic", "phantom"],
        "descriptors": ["sharp", "dull", "burning", "throbbing", "stabbing", "aching",
                       "radiating", "cramping", "tingling", "shooting"],
        "keywords": ["pain", "hurt", "ache", "agony", "suffer", "痛", "苦", "疼痛",
                     "nociception", "analgesic", "hyperalgesia", "allodynia"],
        "neural": "anterior cingulate cortex, insula, somatosensory cortex, thalamus",
        "valence": -0.8,
        "arousal": 0.7,
    },
    "emotion": {
        "subtypes": ["fear", "anger", "sadness", "joy", "death", "mortality", "disgust", "surprise",
                     "contempt", "shame", "guilt", "pride", "love", "grief"],
        "descriptors": ["overwhelming", "subtle", "acute", "chronic", "mixed",
                       "anticipatory", "reactive", "reflected"],
        "keywords": ["emotion", "feeling", "affect", "fear", "anxiety", "mood", "sentiment", "感情",
                     "情動", "amygdala", "limbic", "valence", "arousal"],
        "neural": "amygdala, prefrontal cortex, insula, ventral striatum",
        "valence": 0.0,  # varies
        "arousal": 0.6,
    },
    "proprioception": {
        "subtypes": ["joint_position", "kinesthesia", "balance", "body_schema"],
        "descriptors": ["spatial", "positional", "dynamic", "static"],
        "keywords": ["proprioception", "kinesthesia", "balance", "vestibular",
                     "body schema", "motor control", "固有感覚", "平衡感覚"],
        "neural": "cerebellum, parietal cortex, vestibular nuclei",
        "valence": 0.0,
        "arousal": 0.3,
    },
    "interoception": {
        "subtypes": ["cardiac", "respiratory", "gastric", "thermal", "hunger", "thirst"],
        "descriptors": ["visceral", "autonomic", "homeostatic"],
        "keywords": ["interoception", "heartbeat", "breathing", "hunger", "thirst",
                     "nausea", "fatigue", "内臓感覚", "体温調節"],
        "neural": "insula, anterior cingulate cortex, hypothalamus",
        "valence": -0.2,
        "arousal": 0.4,
    },
    "perception": {
        "subtypes": ["visual", "auditory", "tactile", "olfactory", "gustatory",
                     "synesthetic", "temporal"],
        "descriptors": ["vivid", "faint", "distorted", "enhanced", "absent"],
        "keywords": ["perception", "sensation", "stimulus", "qualia", "phenomenal",
                     "consciousness", "知覚", "感覚", "意識"],
        "neural": "primary sensory cortices, association areas, thalamus",
        "valence": 0.0,
        "arousal": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Paper-Based Embodied Knowledge Retrieval
# ═══════════════════════════════════════════════════════════════════════════

def _search_embodied_papers(query_terms, sensation_type, max_results=5):
    """Search OpenAlex for papers describing bodily experiences."""
    # Build search query combining sensation keywords with claim terms
    ontology = SENSATION_ONTOLOGY.get(sensation_type, {})
    keywords = ontology.get("keywords", [])[:3]
    
    search_query = " ".join(query_terms[:3] + keywords[:2])
    
    params = urllib.parse.urlencode({
        "search": search_query,
        "per_page": max_results,
        "sort": "relevance_score:desc",
        "filter": "has_abstract:true",
    })
    
    url = f"https://api.openalex.org/works?{params}"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "KS30-Embodied/1.0 (mailto:ks30@katala.dev)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            papers = []
            for work in data.get("results", []):
                title = work.get("title", "")
                # Reconstruct abstract from inverted index
                abstract = ""
                inv_idx = work.get("abstract_inverted_index", {})
                if inv_idx:
                    word_positions = []
                    for word, positions in inv_idx.items():
                        for pos in positions:
                            word_positions.append((pos, word))
                    word_positions.sort()
                    abstract = " ".join(w for _, w in word_positions)
                
                papers.append({
                    "title": title,
                    "abstract": abstract[:500],
                    "year": work.get("publication_year", 0),
                    "cited_by": work.get("cited_by_count", 0),
                    "doi": work.get("doi", ""),
                })
            return papers
    except Exception:
        return []


def _extract_qualia_description(abstract, sensation_type):
    """Extract descriptions of subjective experience from paper abstract."""
    ontology = SENSATION_ONTOLOGY.get(sensation_type, {})
    descriptors = ontology.get("descriptors", [])
    
    # Find sentences containing experience descriptors
    sentences = abstract.replace(". ", ".\n").split("\n")
    relevant = []
    for sent in sentences:
        lower = sent.lower()
        if any(d in lower for d in descriptors):
            relevant.append(sent.strip())
        elif any(k in lower for k in ontology.get("keywords", [])[:5]):
            relevant.append(sent.strip())
    
    return " ".join(relevant[:3]) if relevant else ""


def _detect_sensation_types(text):
    """Detect which sensation types are relevant to a claim."""
    lower = text.lower()
    detected = []
    
    for stype, ontology in SENSATION_ONTOLOGY.items():
        score = 0
        for kw in ontology["keywords"]:
            if kw.lower() in lower:
                score += 1
        if score > 0:
            detected.append((stype, score))
    
    # Sort by relevance
    detected.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in detected]


def _compute_somatic_relevance(text, sensation_types):
    """Compute how much bodily experience matters for understanding this claim."""
    if not sensation_types:
        return 0.0
    
    lower = text.lower()
    
    # Direct bodily references
    body_words = ["body", "physical", "feel", "sense", "experience",
                  "pain", "emotion", "touch", "see", "hear",
                  "身体", "体", "感じ", "痛", "触", "見", "聞"]
    body_score = sum(1 for w in body_words if w in lower) / len(body_words)
    
    # Abstract vs concrete
    abstract_words = ["theory", "concept", "principle", "axiom", "proof",
                      "理論", "概念", "原理", "公理", "証明"]
    abstract_score = sum(1 for w in abstract_words if w in lower) / len(abstract_words)
    
    relevance = min(1.0, body_score * 2 - abstract_score + 0.1 * len(sensation_types))
    return max(0.0, relevance)


# ═══════════════════════════════════════════════════════════════════════════
# Main API
# ═══════════════════════════════════════════════════════════════════════════

def analyze_embodied(claim_text, evidence=None):
    """Analyze a claim through the lens of embodied cognition.
    
    Implements Youta's hypothesis: use paper descriptions of bodily experience
    as grounding for claims that involve sensation, emotion, or physical experience.
    
    Usage:
        result = analyze_embodied("Pain is subjective and cannot be measured objectively")
        claim._embodied = result
        # Enriches KS30 pipeline with embodied context
    """
    evidence = evidence or []
    full_text = claim_text + " " + " ".join(evidence)
    
    # 1. Detect relevant sensation types
    sensation_types = _detect_sensation_types(full_text)
    
    if not sensation_types:
        return EmbodiedAnalysis(
            claim_text=claim_text,
            has_embodied_content=False,
            somatic_relevance=0.0,
            empathy_factor=0.0,
            confidence=0.9,
            methodology="pattern_matched",
        )
    
    # 2. Search papers for each sensation type
    embodied_dims = []
    claim_words = [w.strip(",.;:?!()\"'") for w in claim_text.split() if len(w) > 3]
    
    for stype in sensation_types[:3]:  # max 3 sensation types
        ontology = SENSATION_ONTOLOGY[stype]
        papers = _search_embodied_papers(claim_words, stype)
        
        for paper in papers[:2]:  # max 2 papers per type
            qualia = _extract_qualia_description(paper["abstract"], stype)
            
            if qualia or paper["abstract"]:
                ek = EmbodiedKnowledge(
                    sensation_type=stype,
                    description=paper["abstract"][:200],
                    qualia_proxy=qualia[:200] if qualia else "No direct experiential description found",
                    intensity=0.5,  # default, could be refined
                    valence=ontology["valence"],
                    arousal=ontology["arousal"],
                    body_region="multiple" if stype in ("emotion", "perception") else "specific",
                    neural_correlate=ontology["neural"],
                    paper_source=paper["title"],
                    paper_year=paper["year"],
                    paper_cited_by=paper["cited_by"],
                )
                embodied_dims.append(ek)
    
    # 3. Compute relevance scores
    somatic_rel = _compute_somatic_relevance(full_text, sensation_types)
    
    # Empathy factor: how much emotional understanding is needed
    emotion_types = [s for s in sensation_types if s in ("emotion", "pain")]
    empathy = min(1.0, len(emotion_types) * 0.4 + somatic_rel * 0.3)
    
    return EmbodiedAnalysis(
        claim_text=claim_text,
        has_embodied_content=True,
        embodied_dimensions=embodied_dims,
        somatic_relevance=somatic_rel,
        empathy_factor=empathy,
        confidence=0.7 if embodied_dims else 0.4,
        methodology="paper_grounded" if embodied_dims else "pattern_matched",
    )


def embodied_to_evidence(analysis):
    """Convert EmbodiedAnalysis into evidence strings for KS30 Claim pipeline.
    
    This is how embodied cognition feeds into the verification:
    papers describing experience → evidence → solver evaluation
    """
    if not analysis.has_embodied_content:
        return []
    
    evidence = []
    
    for dim in analysis.embodied_dimensions:
        evidence.append(
            f"[Embodied:{dim.sensation_type}] {dim.qualia_proxy[:100]} "
            f"(Source: {dim.paper_source[:50]}, {dim.paper_year}, cited:{dim.paper_cited_by})"
        )
    
    if analysis.somatic_relevance > 0.5:
        evidence.append(
            f"[Somatic relevance: {analysis.somatic_relevance:.2f}] "
            f"This claim involves bodily experience that requires embodied understanding."
        )
    
    return evidence


def enrich_claim(claim, analysis=None):
    """Enrich a KS30 Claim with embodied cognition data.
    
    Automatically analyzes the claim for embodied content and adds
    paper-grounded experiential evidence.
    
    Usage:
        from ks29b import Claim
        claim = Claim("Pain is subjective", evidence=["McGill Pain Questionnaire"])
        claim = enrich_claim(claim)
        # claim.evidence now includes embodied knowledge from papers
    """
    if analysis is None:
        analysis = analyze_embodied(claim.text, claim.evidence)
    
    # Add embodied evidence
    new_evidence = embodied_to_evidence(analysis)
    claim.evidence.extend(new_evidence)
    
    # Attach analysis
    claim._embodied = analysis
    
    return claim
