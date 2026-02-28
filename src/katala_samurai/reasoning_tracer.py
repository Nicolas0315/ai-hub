"""
Reasoning Tracer — DAG-based reasoning chain analysis for self-monitoring.

Traces WHY each layer reached its conclusion, then detects:
  - Unjustified leaps (conclusion without evidence path)
  - Circular reasoning (A→B→C→A)
  - Evidence gaps (missing intermediate steps)
  - Confidence without basis (high confidence from low-evidence chains)

Target: Self-Monitoring 65% → 90%+

Design: Youta Hilono, 2026-02-28
"""

import networkx as nx
from typing import Dict, Any, List, Optional
from collections import defaultdict


class ReasoningTrace:
    """Build and analyze a reasoning DAG from verification results."""
    
    def __init__(self):
        self.G = nx.DiGraph()
        self._step_counter = 0
    
    def add_step(self, layer: str, conclusion: str, evidence: List[str] = None,
                 confidence: float = 0.5, metadata: Dict = None) -> int:
        """Add a reasoning step (node) with evidence links (edges)."""
        node_id = self._step_counter
        self._step_counter += 1
        
        self.G.add_node(node_id, layer=layer, conclusion=conclusion[:200],
                       confidence=confidence, metadata=metadata or {},
                       evidence_count=len(evidence or []))
        
        # Link evidence to this conclusion
        for ev in (evidence or []):
            # Find existing node matching this evidence
            for n, d in self.G.nodes(data=True):
                if d.get("conclusion", "")[:50] == ev[:50] and n != node_id:
                    self.G.add_edge(n, node_id, type="supports")
                    break
        
        return node_id
    
    def detect_leaps(self) -> List[Dict[str, Any]]:
        """Find conclusions with no incoming evidence edges (unjustified leaps)."""
        leaps = []
        for node, data in self.G.nodes(data=True):
            in_degree = self.G.in_degree(node)
            conf = data.get("confidence", 0)
            
            if in_degree == 0 and conf > 0.6:
                leaps.append({
                    "node": node,
                    "layer": data.get("layer", "?"),
                    "conclusion": data.get("conclusion", "")[:100],
                    "confidence": conf,
                    "issue": "high_confidence_no_evidence",
                    "severity": "high" if conf > 0.8 else "medium",
                })
            elif in_degree == 0 and data.get("layer") not in ("input", "claim"):
                leaps.append({
                    "node": node,
                    "layer": data.get("layer", "?"),
                    "conclusion": data.get("conclusion", "")[:100],
                    "confidence": conf,
                    "issue": "unsupported_step",
                    "severity": "low",
                })
        return leaps
    
    def detect_circular(self) -> List[Dict[str, Any]]:
        """Find circular reasoning patterns."""
        cycles = []
        try:
            for cycle in nx.simple_cycles(self.G):
                if len(cycle) >= 2:
                    cycles.append({
                        "nodes": cycle,
                        "layers": [self.G.nodes[n].get("layer", "?") for n in cycle],
                        "issue": "circular_reasoning",
                        "severity": "high",
                    })
                if len(cycles) >= 5:
                    break
        except nx.NetworkXError:
            pass
        return cycles
    
    def detect_evidence_gaps(self) -> List[Dict[str, Any]]:
        """Find long reasoning chains with missing intermediate evidence."""
        gaps = []
        if not nx.is_directed_acyclic_graph(self.G):
            return gaps
        
        # Check for jumps: conclusion depends on distant node with nothing in between
        for node in self.G.nodes:
            predecessors = list(self.G.predecessors(node))
            if not predecessors:
                continue
            
            node_layer = self.G.nodes[node].get("layer", "")
            for pred in predecessors:
                pred_layer = self.G.nodes[pred].get("layer", "")
                # If layers are far apart with no intermediate steps
                path_length = nx.shortest_path_length(self.G, pred, node) if nx.has_path(self.G, pred, node) else 0
                if path_length == 1:  # Direct edge but layers suggest steps were skipped
                    node_conf = self.G.nodes[node].get("confidence", 0)
                    pred_conf = self.G.nodes[pred].get("confidence", 0)
                    conf_jump = abs(node_conf - pred_conf)
                    if conf_jump > 0.3:
                        gaps.append({
                            "from": pred, "to": node,
                            "from_layer": pred_layer, "to_layer": node_layer,
                            "confidence_jump": round(conf_jump, 3),
                            "issue": "large_confidence_jump",
                            "severity": "medium",
                        })
        return gaps
    
    def detect_confidence_without_basis(self) -> List[Dict[str, Any]]:
        """Find high-confidence conclusions supported only by low-confidence evidence."""
        issues = []
        for node, data in self.G.nodes(data=True):
            conf = data.get("confidence", 0)
            if conf < 0.7:
                continue
            
            supporters = list(self.G.predecessors(node))
            if not supporters:
                continue
            
            supporter_confs = [self.G.nodes[s].get("confidence", 0) for s in supporters]
            max_support = max(supporter_confs) if supporter_confs else 0
            avg_support = sum(supporter_confs) / len(supporter_confs) if supporter_confs else 0
            
            if max_support < 0.5:
                issues.append({
                    "node": node,
                    "conclusion_confidence": conf,
                    "max_evidence_confidence": max_support,
                    "avg_evidence_confidence": round(avg_support, 3),
                    "issue": "confidence_exceeds_evidence",
                    "severity": "high",
                })
            elif avg_support < conf - 0.3:
                issues.append({
                    "node": node,
                    "conclusion_confidence": conf,
                    "avg_evidence_confidence": round(avg_support, 3),
                    "issue": "confidence_inflated",
                    "severity": "medium",
                })
        return issues


def trace_verification(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build reasoning trace from a KS verification result and analyze it."""
    tracer = ReasoningTrace()
    
    # Add input claim
    tracer.add_step("input", result.get("claim", "input claim"), confidence=1.0)
    
    # Add layer results from trace
    for step in result.get("trace", []):
        layer = step.get("layer", step.get("stage", "unknown"))
        conclusion = str(step.get("result", step.get("verdict", "")))[:200]
        conf = step.get("confidence", 0.5)
        tracer.add_step(layer, conclusion, confidence=conf)
    
    # Add L6/L7 if present
    l6 = result.get("L6_statistical", {})
    if l6:
        tracer.add_step("L6", l6.get("verdict", ""), confidence=0.5 + l6.get("modifier", 0))
    
    l7 = result.get("L7_adversarial", {})
    if l7:
        tracer.add_step("L7", l7.get("verdict", ""), confidence=0.5 + l7.get("modifier", 0))
    
    # Add final verdict
    tracer.add_step("final", result.get("verdict", "UNKNOWN"),
                    confidence=result.get("confidence", 0.5))
    
    # Analyze
    leaps = tracer.detect_leaps()
    circular = tracer.detect_circular()
    gaps = tracer.detect_evidence_gaps()
    baseless = tracer.detect_confidence_without_basis()
    
    all_issues = leaps + circular + gaps + baseless
    
    severity_scores = {"low": 1, "medium": 2, "high": 3}
    total_severity = sum(severity_scores.get(i.get("severity", "low"), 1) for i in all_issues)
    
    # Self-monitoring score (higher = better reasoning quality)
    max_possible = len(tracer.G.nodes) * 3  # If every node had a high issue
    monitoring_score = max(0, 1.0 - (total_severity / max(max_possible, 1)))
    
    return {
        "nodes": tracer.G.number_of_nodes(),
        "edges": tracer.G.number_of_edges(),
        "leaps": leaps,
        "circular": circular,
        "evidence_gaps": gaps,
        "baseless_confidence": baseless,
        "total_issues": len(all_issues),
        "monitoring_score": round(monitoring_score, 4),
        "confidence_modifier": round(-0.05 * len([i for i in all_issues if i.get("severity") in ("high",)]), 4),
    }
