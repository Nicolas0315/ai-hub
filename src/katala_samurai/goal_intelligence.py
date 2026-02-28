"""
Goal Intelligence Layer — elevates autonomous goal-setting quality.

GI1: Impact Scorer — how much could this goal change the verdict
GI2: Coverage Checker — are all verification angles covered
GI3: Dependency Graph — optimal verification order
GI4: Meta-Goal Generator — what are we missing

Design: Youta Hilono, 2026-02-28
Non-LLM: structural analysis + graph + set operations.
"""

import re
from collections import defaultdict

try:
    from .analogical_transfer import match_templates
except ImportError:
    from analogical_transfer import match_templates


# ─── Verification Angles ────────────────────────────────────────────────────

VERIFICATION_ANGLES = {
    "causal": {
        "description": "Is the causal mechanism valid?",
        "markers": ["causes", "leads to", "results in", "produces", "because", "due to"],
        "weight": 0.9,
    },
    "classification": {
        "description": "Is the category assignment correct?",
        "markers": ["is a", "type of", "kind of", "belongs to", "classified as"],
        "weight": 0.7,
    },
    "conditional": {
        "description": "Is the conditional relationship valid?",
        "markers": ["if", "when", "unless", "provided", "assuming"],
        "weight": 0.8,
    },
    "quantitative": {
        "description": "Are the quantities/magnitudes accurate?",
        "markers": ["more", "less", "percent", "ratio", "rate", "amount", "level", "degree"],
        "weight": 0.75,
    },
    "temporal": {
        "description": "Is the temporal ordering correct?",
        "markers": ["before", "after", "during", "while", "then", "first", "finally", "since"],
        "weight": 0.65,
    },
    "scope": {
        "description": "Is the scope/generality appropriate?",
        "markers": ["all", "every", "always", "never", "most", "some", "none", "few"],
        "weight": 0.85,
    },
    "existence": {
        "description": "Does the referenced entity/concept exist?",
        "markers": ["exists", "there is", "contains", "has", "includes"],
        "weight": 0.6,
    },
    "negation": {
        "description": "Is the negation correctly applied?",
        "markers": ["not", "no", "never", "neither", "doesn't", "isn't", "cannot"],
        "weight": 0.8,
    },
}


# ─── GI1: Impact Scorer ────────────────────────────────────────────────────

def score_impact(goal_text, original_text, original_template=None):
    """Score how much a goal could change the overall verdict."""
    
    # Extract causal chain elements from original
    orig_words = set(re.findall(r'\b(\w{4,})\b', original_text.lower()))
    goal_words = set(re.findall(r'\b(\w{4,})\b', goal_text.lower()))
    
    # Core concept overlap: goals targeting core concepts have higher impact
    overlap = orig_words & goal_words
    core_ratio = len(overlap) / max(len(orig_words), 1)
    
    # Verdict-changing potential
    verdict_changers = {
        "counterfactual": 0.9,  # "Without X, Y shouldn't occur"
        "contrapositive": 0.85,
        "negation": 0.8,
        "universal": 0.75,
        "exception": 0.7,
    }
    
    impact_type = "general"
    impact_bonus = 0.0
    
    goal_lower = goal_text.lower()
    if "without" in goal_lower or "removing" in goal_lower:
        impact_type = "counterfactual"
        impact_bonus = verdict_changers["counterfactual"]
    elif "not " in goal_lower and any(w in goal_lower for w in ["then", "therefore"]):
        impact_type = "contrapositive"
        impact_bonus = verdict_changers["contrapositive"]
    elif any(w in goal_lower for w in ["never", "always", "all", "none"]):
        impact_type = "universal"
        impact_bonus = verdict_changers["universal"]
    elif any(w in goal_lower for w in ["except", "unless", "however"]):
        impact_type = "exception"
        impact_bonus = verdict_changers["exception"]
    
    impact_score = 0.3 * core_ratio + 0.7 * impact_bonus
    
    return {
        "impact_score": round(min(impact_score, 1.0), 3),
        "impact_type": impact_type,
        "core_overlap": round(core_ratio, 3),
        "verdict_change_potential": impact_type != "general",
    }


# ─── GI2: Coverage Checker ─────────────────────────────────────────────────

def check_coverage(original_text, goals):
    """Check which verification angles are covered by current goals."""
    text_lower = original_text.lower()
    
    # Detect which angles are relevant for this claim
    relevant_angles = {}
    for angle, info in VERIFICATION_ANGLES.items():
        if any(m in text_lower for m in info["markers"]):
            relevant_angles[angle] = info
    
    if not relevant_angles:
        # Default: at least check existence and scope
        relevant_angles = {
            "existence": VERIFICATION_ANGLES["existence"],
            "scope": VERIFICATION_ANGLES["scope"],
        }
    
    # Check which angles are covered by goals
    covered = set()
    for goal in goals:
        goal_text = goal.get("target", goal.get("target_text", "")).lower()
        for angle, info in relevant_angles.items():
            if any(m in goal_text for m in info["markers"]):
                covered.add(angle)
    
    uncovered = set(relevant_angles.keys()) - covered
    coverage_ratio = len(covered) / max(len(relevant_angles), 1)
    
    # Generate goals for uncovered angles
    missing_goals = []
    for angle in uncovered:
        info = VERIFICATION_ANGLES[angle]
        missing_goals.append({
            "target": f"Verify {angle}: {info['description']}",
            "source": "GI2_coverage",
            "priority": info["weight"],
            "reason": f"Uncovered verification angle: {angle}",
            "angle": angle,
        })
    
    return {
        "relevant_angles": list(relevant_angles.keys()),
        "covered": list(covered),
        "uncovered": list(uncovered),
        "coverage_ratio": round(coverage_ratio, 3),
        "missing_goals": missing_goals,
    }


# ─── GI3: Dependency Graph ─────────────────────────────────────────────────

def build_dependency_graph(goals):
    """Build dependency graph between goals and compute optimal order."""
    n = len(goals)
    if n <= 1:
        return {"order": list(range(n)), "dependencies": [], "has_cycle": False}
    
    # Extract key concepts from each goal
    goal_concepts = []
    for g in goals:
        text = g.get("target", g.get("target_text", ""))
        concepts = set(re.findall(r'\b(\w{4,})\b', text.lower()))
        goal_concepts.append(concepts)
    
    # Find dependencies: if goal_A's output concept is goal_B's input
    dependencies = []
    adj = defaultdict(list)
    in_degree = defaultdict(int)
    
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # If goal_i produces concepts that goal_j needs
            # Heuristic: if goal_i mentions "verify X" and goal_j mentions "X causes Y"
            shared = goal_concepts[i] & goal_concepts[j]
            if len(shared) >= 2 and i < j:  # Prefer earlier goals as prerequisites
                dependencies.append({"from": i, "to": j, "shared": list(shared)[:3]})
                adj[i].append(j)
                in_degree[j] += 1
    
    # Topological sort (Kahn's algorithm)
    queue = [i for i in range(n) if in_degree[i] == 0]
    order = []
    
    while queue:
        # Among zero in-degree nodes, prefer higher priority
        queue.sort(key=lambda x: goals[x].get("priority", 0), reverse=True)
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    has_cycle = len(order) != n
    if has_cycle:
        # Add remaining nodes
        remaining = [i for i in range(n) if i not in order]
        order.extend(remaining)
    
    return {
        "order": order,
        "dependencies": dependencies,
        "has_cycle": has_cycle,
    }


# ─── GI4: Meta-Goal Generator ──────────────────────────────────────────────

def generate_meta_goals(original_text, goals, coverage_result):
    """Generate meta-goals: what are we missing?"""
    meta_goals = []
    
    # Meta 1: If coverage is low, add a coverage meta-goal
    if coverage_result["coverage_ratio"] < 0.6:
        uncovered = coverage_result["uncovered"]
        meta_goals.append({
            "target": f"Meta: {len(uncovered)} verification angles uncovered — "
                     f"missing {', '.join(uncovered[:3])}",
            "source": "GI4_meta",
            "priority": 0.95,
            "reason": "Low verification coverage",
            "is_meta": True,
        })
    
    # Meta 2: If all goals are from the same source, add diversity meta-goal
    sources = set(g.get("source", "") for g in goals)
    if len(sources) <= 1 and len(goals) > 2:
        meta_goals.append({
            "target": "Meta: All goals from single source — diversify verification approach",
            "source": "GI4_meta",
            "priority": 0.85,
            "reason": "Goal source concentration",
            "is_meta": True,
        })
    
    # Meta 3: If no high-impact goals exist
    has_high_impact = False
    for g in goals:
        impact = score_impact(
            g.get("target", g.get("target_text", "")),
            original_text
        )
        if impact["verdict_change_potential"]:
            has_high_impact = True
            break
    
    if not has_high_impact and len(goals) > 0:
        meta_goals.append({
            "target": "Meta: No verdict-changing goals — generate counterfactual or contrapositive",
            "source": "GI4_meta",
            "priority": 0.90,
            "reason": "Missing high-impact verification goals",
            "is_meta": True,
        })
    
    # Meta 4: Assumption audit
    templates = match_templates(original_text)
    if not templates:
        meta_goals.append({
            "target": "Meta: Claim structure unrecognized — manual structural analysis needed",
            "source": "GI4_meta",
            "priority": 0.80,
            "reason": "No structural template matched",
            "is_meta": True,
        })
    
    return meta_goals


# ─── Unified Goal Intelligence Pipeline ─────────────────────────────────────

def enhance_goals(original_text, goals, store=None):
    """Full goal intelligence pipeline.
    
    1. Score impact of each goal
    2. Check coverage
    3. Build dependency graph
    4. Generate meta-goals
    5. Merge, re-rank, and return enhanced goals
    """
    # GI1: Impact scoring
    for goal in goals:
        target = goal.get("target", goal.get("target_text", ""))
        impact = score_impact(target, original_text)
        goal["impact_score"] = impact["impact_score"]
        goal["impact_type"] = impact["impact_type"]
    
    # GI2: Coverage
    coverage = check_coverage(original_text, goals)
    
    # GI3: Dependency graph
    dep_graph = build_dependency_graph(goals)
    
    # GI4: Meta-goals
    meta_goals = generate_meta_goals(original_text, goals, coverage)
    
    # Merge coverage-missing goals + meta-goals
    all_goals = list(goals) + coverage.get("missing_goals", []) + meta_goals
    
    # Re-rank by composite score: priority * 0.4 + impact * 0.4 + coverage_contribution * 0.2
    for g in all_goals:
        priority = g.get("priority", 0.5)
        impact = g.get("impact_score", 0.3)
        is_coverage_fill = g.get("source", "").startswith("GI2")
        coverage_bonus = 0.15 if is_coverage_fill else 0.0
        is_meta = g.get("is_meta", False)
        meta_bonus = 0.1 if is_meta else 0.0
        
        g["composite_score"] = round(
            0.4 * priority + 0.4 * impact + coverage_bonus + meta_bonus, 3
        )
    
    all_goals.sort(key=lambda g: g["composite_score"], reverse=True)
    
    result = {
        "original_goals": len(goals),
        "coverage_goals_added": len(coverage.get("missing_goals", [])),
        "meta_goals_added": len(meta_goals),
        "total_goals": len(all_goals),
        "coverage": {
            "ratio": coverage["coverage_ratio"],
            "covered": coverage["covered"],
            "uncovered": coverage["uncovered"],
        },
        "dependency_order": dep_graph["order"],
        "has_dependency_cycle": dep_graph["has_cycle"],
        "goals": all_goals,
    }
    
    if store:
        store.write("goal_intelligence", {
            "coverage_ratio": coverage["coverage_ratio"],
            "meta_goals": len(meta_goals),
            "total_enhanced": len(all_goals),
        })
    
    return result
