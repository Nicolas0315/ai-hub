"""
Goal Quality Evaluator — addresses weakness ②: Autonomous Goal Setting 45%.

Evaluates goal quality by:
  Q1: Relevance — how related is the goal to the original claim
  Q2: Testability — can this goal actually be verified
  Q3: Novelty — does this goal add new information vs original
  Q4: Priority Recalibration — dynamic priority based on quality

Non-LLM: word overlap + structural checks.
"""

import re


def evaluate_goal_quality(goal_text, original_text, domain_result=None):
    """Evaluate quality of an auto-generated goal."""
    scores = {}
    
    # Q1: Relevance (word overlap with original)
    orig_words = set(re.findall(r'\b(\w{4,})\b', original_text.lower()))
    goal_words = set(re.findall(r'\b(\w{4,})\b', goal_text.lower()))
    
    if orig_words:
        overlap = len(orig_words & goal_words) / len(orig_words)
    else:
        overlap = 0.0
    scores["relevance"] = min(overlap * 1.5, 1.0)  # Scale up, cap at 1.0
    
    # Q2: Testability (does it contain verifiable structure?)
    testable_markers = [
        re.compile(r'\b(is|are|was|were|has|have|contains?|causes?|prevents?)\b', re.I),
        re.compile(r'\b(should|must|always|never)\b', re.I),
        re.compile(r'\b(more|less|greater|smaller|equal)\b', re.I),
    ]
    testability = sum(1 for p in testable_markers if p.search(goal_text)) / len(testable_markers)
    scores["testability"] = round(testability, 2)
    
    # Q3: Novelty (new concepts beyond original)
    novel_words = goal_words - orig_words
    common_filler = {"verify", "check", "that", "this", "from", "with", "should", "would", "could"}
    novel_meaningful = novel_words - common_filler
    novelty = min(len(novel_meaningful) / max(len(goal_words), 1), 1.0)
    scores["novelty"] = round(novelty, 2)
    
    # Q4: Length/specificity check
    word_count = len(goal_text.split())
    if word_count < 5:
        scores["specificity"] = 0.3  # Too vague
    elif word_count > 30:
        scores["specificity"] = 0.5  # Too verbose
    else:
        scores["specificity"] = 0.8
    
    # Composite quality score
    quality = (
        0.35 * scores["relevance"] +
        0.25 * scores["testability"] +
        0.20 * scores["novelty"] +
        0.20 * scores["specificity"]
    )
    
    # Quality tier
    if quality >= 0.7:
        tier = "HIGH"
    elif quality >= 0.4:
        tier = "MEDIUM"
    else:
        tier = "LOW"
    
    return {
        "scores": scores,
        "quality": round(quality, 3),
        "tier": tier,
    }


def filter_goals_by_quality(goals, original_text, min_quality=0.3, domain_result=None):
    """Filter and re-rank goals by quality."""
    evaluated = []
    for goal in goals:
        target = goal.get("target", goal.get("target_text", ""))
        quality = evaluate_goal_quality(target, original_text, domain_result)
        evaluated.append({
            **goal,
            "quality": quality["quality"],
            "quality_tier": quality["tier"],
            "quality_scores": quality["scores"],
            # Recalibrate priority by quality
            "adjusted_priority": round(goal.get("priority", 0.5) * (0.5 + 0.5 * quality["quality"]), 3),
        })
    
    # Filter low quality
    filtered = [g for g in evaluated if g["quality"] >= min_quality]
    
    # Re-sort by adjusted priority
    filtered.sort(key=lambda g: g["adjusted_priority"], reverse=True)
    
    return {
        "total": len(goals),
        "filtered": len(filtered),
        "removed": len(goals) - len(filtered),
        "goals": filtered,
        "avg_quality": round(sum(g["quality"] for g in evaluated) / max(len(evaluated), 1), 3),
    }
