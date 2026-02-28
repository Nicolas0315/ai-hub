"""
Confound Detector — Automatic confounding variable discovery.

Non-LLM: Uses ConceptNet + OpenAlex to find common parent concepts
that could confound an observed A→B relationship.

This is the key to surpassing Q* in causal reasoning.
Q* relies on LLM world knowledge for confounder guessing.
KS uses structured knowledge graphs for systematic enumeration.

Design: Youta Hilono, 2026-02-28
"""

import os
import re
import json
import networkx as nx
from typing import Dict, Any, List, Set, Optional

# Fast mode: skip external APIs
_FAST_MODE = os.environ.get("KS_FAST_MODE", "0") == "1"


def _query_conceptnet_parents(term: str, limit: int = 10) -> List[Dict[str, str]]:
    """Get parent/broader concepts from ConceptNet for a term."""
    if _FAST_MODE:
        return []
    
    try:
        import urllib.request
        url = f"https://api.conceptnet.io/query?node=/c/en/{term.lower().replace(' ','_')}&rel=/r/IsA&limit={limit}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        
        parents = []
        for edge in data.get("edges", []):
            if edge["start"]["label"].lower() == term.lower():
                parents.append({
                    "concept": edge["end"]["label"],
                    "relation": "IsA",
                    "weight": edge.get("weight", 1.0),
                })
            elif edge["end"]["label"].lower() == term.lower():
                parents.append({
                    "concept": edge["start"]["label"],
                    "relation": "HasA",
                    "weight": edge.get("weight", 1.0),
                })
        return parents
    except Exception:
        return []


def _query_conceptnet_related(term: str, limit: int = 15) -> List[Dict[str, str]]:
    """Get related concepts from ConceptNet."""
    if _FAST_MODE:
        return []
    
    try:
        import urllib.request
        url = f"https://api.conceptnet.io/related/c/en/{term.lower().replace(' ','_')}?limit={limit}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        return [
            {"concept": item["@id"].split("/")[-1].replace("_", " "), "weight": item.get("weight", 0)}
            for item in data.get("related", [])
        ]
    except Exception:
        return []


def _find_common_parents(
    cause_label: str, effect_label: str
) -> List[Dict[str, Any]]:
    """Find concepts that are parents/related to BOTH cause and effect.
    
    Common parents = potential confounders.
    """
    cause_parents = set()
    effect_parents = set()
    
    # Get parents from ConceptNet
    for p in _query_conceptnet_parents(cause_label):
        cause_parents.add(p["concept"].lower())
    for p in _query_conceptnet_related(cause_label):
        cause_parents.add(p["concept"].lower())
    
    for p in _query_conceptnet_parents(effect_label):
        effect_parents.add(p["concept"].lower())
    for p in _query_conceptnet_related(effect_label):
        effect_parents.add(p["concept"].lower())
    
    # Intersection = potential confounders
    common = cause_parents & effect_parents
    # Remove trivial matches
    trivial = {"thing", "object", "entity", "something", "concept", cause_label.lower(), effect_label.lower()}
    common -= trivial
    
    return [
        {"concept": c, "source": "conceptnet", "affects_both": True}
        for c in sorted(common)
    ]


# Built-in confounder templates (domain-agnostic structural patterns)
_CONFOUNDER_TEMPLATES = [
    {
        "pattern": "age",
        "keywords": re.compile(r'\b(?:age|aging|elderly|young|old)\b', re.I),
        "description": "Age is a common confounder in health/social claims",
    },
    {
        "pattern": "socioeconomic",
        "keywords": re.compile(r'\b(?:income|wealth|poverty|education|socioeconomic|SES)\b', re.I),
        "description": "Socioeconomic status confounds health/education/crime claims",
    },
    {
        "pattern": "genetics",
        "keywords": re.compile(r'\b(?:gene|genetic|hereditary|DNA|inherited)\b', re.I),
        "description": "Genetic factors confound health/behavior claims",
    },
    {
        "pattern": "environment",
        "keywords": re.compile(r'\b(?:environment|climate|weather|pollution|temperature)\b', re.I),
        "description": "Environmental factors as shared cause",
    },
    {
        "pattern": "selection_bias",
        "keywords": re.compile(r'\b(?:select|sample|population|group|cohort)\b', re.I),
        "description": "Selection bias: who is in the sample affects both variables",
    },
    {
        "pattern": "temporal",
        "keywords": re.compile(r'\b(?:time|trend|season|year|decade|era)\b', re.I),
        "description": "Temporal trends affect both variables simultaneously",
    },
    {
        "pattern": "measurement",
        "keywords": re.compile(r'\b(?:measure|survey|self.report|questionnaire)\b', re.I),
        "description": "Measurement method affects both observed variables",
    },
]


def detect_template_confounders(
    cause_text: str, effect_text: str
) -> List[Dict[str, Any]]:
    """Detect potential confounders using structural templates.
    
    Non-LLM: regex pattern matching against known confounder categories.
    """
    combined = cause_text + " " + effect_text
    found = []
    
    for template in _CONFOUNDER_TEMPLATES:
        if template["keywords"].search(combined):
            found.append({
                "confounder_type": template["pattern"],
                "description": template["description"],
                "source": "template",
                "detected_in": "cause" if template["keywords"].search(cause_text)
                    else "effect" if template["keywords"].search(effect_text)
                    else "both",
            })
    
    return found


def detect_confounders(
    G: nx.DiGraph,
    cause: int,
    effect: int,
) -> Dict[str, Any]:
    """Full confounder detection for a causal edge.
    
    Combines:
    1. DAG structural analysis (common ancestors)
    2. ConceptNet parent intersection
    3. Template-based confounder detection
    
    Returns comprehensive confounder report.
    """
    cause_label = G.nodes[cause].get("label", "") if cause in G.nodes else ""
    effect_label = G.nodes[effect].get("label", "") if effect in G.nodes else ""
    cause_text = G.nodes[cause].get("text", "") if cause in G.nodes else ""
    effect_text = G.nodes[effect].get("text", "") if effect in G.nodes else ""
    
    confounders = []
    
    # 1. Structural: common ancestors in DAG
    if nx.is_directed_acyclic_graph(G):
        cause_ancestors = nx.ancestors(G, cause) if cause in G else set()
        effect_ancestors = nx.ancestors(G, effect) if effect in G else set()
        common_ancestors = cause_ancestors & effect_ancestors
        
        for anc in common_ancestors:
            confounders.append({
                "node": anc,
                "label": G.nodes[anc].get("label", str(anc)),
                "source": "dag_structure",
                "type": "common_ancestor",
                "confidence": 0.9,
            })
    
    # 2. ConceptNet: shared parent concepts
    if cause_label and effect_label:
        cn_confounders = _find_common_parents(cause_label, effect_label)
        for c in cn_confounders:
            confounders.append({
                "concept": c["concept"],
                "source": "conceptnet",
                "type": "shared_parent_concept",
                "confidence": 0.6,
            })
    
    # 3. Template: known confounder patterns
    template_confounders = detect_template_confounders(cause_text, effect_text)
    for t in template_confounders:
        confounders.append({
            "concept": t["confounder_type"],
            "description": t["description"],
            "source": "template",
            "type": "known_pattern",
            "confidence": 0.7,
        })
    
    # Dedup by concept name
    seen = set()
    unique = []
    for c in confounders:
        key = c.get("label", c.get("concept", "")).lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)
    
    # Assessment
    n = len(unique)
    if n == 0:
        assessment = "NO_CONFOUNDERS_DETECTED"
        risk = 0.1
    elif n <= 2:
        assessment = "LOW_CONFOUNDING_RISK"
        risk = 0.3
    elif n <= 5:
        assessment = "MODERATE_CONFOUNDING_RISK"
        risk = 0.6
    else:
        assessment = "HIGH_CONFOUNDING_RISK"
        risk = 0.85
    
    return {
        "cause": cause,
        "effect": effect,
        "cause_label": cause_label,
        "effect_label": effect_label,
        "confounders": unique,
        "confounder_count": len(unique),
        "assessment": assessment,
        "confounding_risk": round(risk, 2),
        "sources_used": list(set(c["source"] for c in unique)),
    }
