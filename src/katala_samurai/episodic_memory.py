"""
Episodic Memory Engine — Long-horizon memory consolidation and retrieval.

Target: Long-term Agent 92% → 95% (-3 point gap)

What was missing:
  SubgoalResolver handles replanning and CheckpointEngine saves state, but:
  1. No EPISODIC MEMORY: agent doesn't remember what it learned from past tasks
  2. No CONSOLIDATION: raw experiences aren't distilled into reusable knowledge
  3. No RETRIEVAL by similarity: past episodes aren't searchable by context
  4. No TRANSFER from episodes: successful strategies aren't reapplied

Insight: Human long-term agents succeed because they remember EPISODES
(specific situations + actions + outcomes), not just checkpoints (state).
SubgoalResolver learns failure patterns; this module learns SUCCESS patterns.

Architecture:
  1. Episode Recording — capture (context, action, outcome, lessons)
  2. Consolidation — merge similar episodes into schemas
  3. Retrieval — find relevant episodes by context similarity
  4. Strategy Transfer — apply past episode strategies to new situations

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from checkpoint import CheckpointEngine
    _HAS_CHECKPOINT = True
except ImportError:
    _HAS_CHECKPOINT = False


# ── Constants ──
VERSION = "1.0.0"

# Episode storage
MAX_EPISODES = 1000                 # Max episodes before pruning
CONSOLIDATION_THRESHOLD = 3         # Min similar episodes to consolidate into schema
SIMILARITY_THRESHOLD = 0.60         # Min similarity for episode retrieval

# Consolidation
SCHEMA_CONFIDENCE_DECAY = 0.98      # Per-access confidence decay
MIN_SCHEMA_CONFIDENCE = 0.10        # Prune schemas below this
MAX_SCHEMAS = 200                   # Max consolidated schemas

# Retrieval
TOP_K_RETRIEVAL = 5                 # Return top-K most relevant episodes
RECENCY_WEIGHT = 0.3                # Weight for recency vs similarity
SIMILARITY_WEIGHT = 0.5             # Weight for context similarity
SUCCESS_WEIGHT = 0.2                # Weight for past success rate

# Strategy transfer
TRANSFER_CONFIDENCE_THRESHOLD = 0.6 # Min confidence to suggest strategy transfer
MIN_EPISODES_FOR_TRANSFER = 2       # Min supporting episodes for strategy suggestion


@dataclass
class Episode:
    """A single episodic memory: situation + action + outcome."""
    episode_id: str
    timestamp: float
    context: Dict[str, Any]           # Situation description (task type, domain, difficulty, etc.)
    context_fingerprint: str          # Character n-gram fingerprint for fast similarity
    action: str                       # What was done
    action_type: str                  # Category: "decompose", "retry", "delegate", "search", etc.
    outcome: str                      # "success", "partial", "failure"
    outcome_score: float              # 0.0-1.0 outcome quality
    lessons: List[str]                # What was learned
    domain: str = "general"           # Task domain
    strategy_used: str = ""           # High-level strategy name
    duration_sec: float = 0.0         # How long it took
    access_count: int = 0             # How many times retrieved
    last_accessed: float = 0.0        # Last retrieval timestamp


@dataclass
class Schema:
    """Consolidated knowledge from multiple similar episodes."""
    schema_id: str
    pattern_name: str                 # Human-readable pattern name
    context_pattern: Dict[str, Any]   # Generalized context pattern
    best_strategy: str                # Most successful strategy for this pattern
    success_rate: float               # Historical success rate
    avg_score: float                  # Average outcome score
    episode_count: int                # Number of episodes contributing
    episode_ids: List[str]            # Contributing episode IDs
    confidence: float                 # Confidence in this schema (decays)
    domain: str = "general"
    alternative_strategies: List[Tuple[str, float]] = field(default_factory=list)  # (strategy, success_rate)
    created_at: float = 0.0
    last_updated: float = 0.0


def _fingerprint(text: str, n: int = 3) -> str:
    """Character n-gram fingerprint for fast similarity."""
    text_lower = text.lower()
    ngrams = set()
    for i in range(len(text_lower) - n + 1):
        ngrams.add(text_lower[i:i+n])
    # Sort and hash for deterministic fingerprint
    sorted_ngrams = sorted(ngrams)
    return hashlib.md5("|".join(sorted_ngrams).encode()).hexdigest()


def _context_to_text(context: Dict[str, Any]) -> str:
    """Flatten context dict to text for fingerprinting."""
    parts = []
    for k, v in sorted(context.items()):
        parts.append(f"{k}={v}")
    return " ".join(parts)


def _jaccard_similarity(fp1_text: str, fp2_text: str, n: int = 3) -> float:
    """Jaccard similarity between two text strings using character n-grams."""
    def ngrams(text):
        text_lower = text.lower()
        return set(text_lower[i:i+n] for i in range(len(text_lower) - n + 1))
    
    s1 = ngrams(fp1_text)
    s2 = ngrams(fp2_text)
    
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


class EpisodicMemoryEngine:
    """
    Episodic memory for long-horizon agent: record, consolidate, retrieve, transfer.
    
    Lifecycle:
      1. record_episode() — after each significant action
      2. consolidate() — periodically merge similar episodes into schemas
      3. retrieve() — find relevant past episodes for current context
      4. suggest_strategy() — recommend actions based on past success
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.episodes: List[Episode] = []
        self.schemas: List[Schema] = []
        self.storage_path = storage_path
        self._episode_index: Dict[str, Episode] = {}  # episode_id → Episode
        self._domain_index: Dict[str, List[str]] = defaultdict(list)  # domain → [episode_id]
        self._strategy_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
        
        if storage_path and os.path.exists(storage_path):
            self._load(storage_path)

    def record_episode(
        self,
        context: Dict[str, Any],
        action: str,
        action_type: str,
        outcome: str,
        outcome_score: float,
        lessons: Optional[List[str]] = None,
        domain: str = "general",
        strategy_used: str = "",
        duration_sec: float = 0.0,
    ) -> Episode:
        """Record a new episodic memory."""
        ctx_text = _context_to_text(context)
        episode = Episode(
            episode_id=hashlib.md5(f"{time.time()}{ctx_text}{action}".encode()).hexdigest()[:12],
            timestamp=time.time(),
            context=context,
            context_fingerprint=_fingerprint(ctx_text),
            action=action,
            action_type=action_type,
            outcome=outcome,
            outcome_score=outcome_score,
            lessons=lessons or [],
            domain=domain,
            strategy_used=strategy_used,
            duration_sec=duration_sec,
        )
        
        self.episodes.append(episode)
        self._episode_index[episode.episode_id] = episode
        self._domain_index[domain].append(episode.episode_id)
        
        # Update strategy stats
        key = f"{domain}:{strategy_used}" if strategy_used else f"{domain}:_default"
        self._strategy_stats[key]["total"] += 1
        if outcome == "success":
            self._strategy_stats[key]["success"] += 1
        
        # Prune if over limit
        if len(self.episodes) > MAX_EPISODES:
            self._prune_oldest(MAX_EPISODES // 10)
        
        return episode

    def retrieve(
        self,
        context: Dict[str, Any],
        domain: Optional[str] = None,
        top_k: int = TOP_K_RETRIEVAL,
    ) -> List[Tuple[Episode, float]]:
        """Retrieve most relevant episodes for a given context.
        
        Returns list of (episode, relevance_score) sorted by relevance.
        Relevance = weighted sum of context_similarity + recency + success_rate.
        """
        if not self.episodes:
            return []
        
        ctx_text = _context_to_text(context)
        now = time.time()
        
        candidates = self.episodes
        if domain:
            domain_ids = set(self._domain_index.get(domain, []))
            candidates = [e for e in candidates if e.episode_id in domain_ids]
        
        scored = []
        for ep in candidates:
            ep_ctx_text = _context_to_text(ep.context)
            
            # Context similarity (Jaccard on character n-grams)
            sim = _jaccard_similarity(ctx_text, ep_ctx_text)
            
            # Recency score (exponential decay, half-life = 1 day)
            age_hours = (now - ep.timestamp) / 3600
            recency = math.exp(-0.029 * age_hours)  # ~50% at 24h
            
            # Success score
            success = ep.outcome_score
            
            # Combined relevance
            relevance = (
                SIMILARITY_WEIGHT * sim +
                RECENCY_WEIGHT * recency +
                SUCCESS_WEIGHT * success
            )
            
            if relevance >= SIMILARITY_THRESHOLD * 0.5:  # Loose filter
                scored.append((ep, relevance))
        
        # Sort by relevance descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Update access counts
        for ep, _ in scored[:top_k]:
            ep.access_count += 1
            ep.last_accessed = now
        
        return scored[:top_k]

    def consolidate(self) -> List[Schema]:
        """Consolidate similar episodes into reusable schemas.
        
        Groups episodes by context similarity, then extracts:
        - Common context patterns
        - Best-performing strategies
        - Average outcomes
        """
        if len(self.episodes) < CONSOLIDATION_THRESHOLD:
            return []
        
        new_schemas = []
        used_ids: Set[str] = set()
        
        # Group by domain first, then by context similarity
        for domain, ep_ids in self._domain_index.items():
            domain_eps = [self._episode_index[eid] for eid in ep_ids 
                         if eid in self._episode_index and eid not in used_ids]
            
            if len(domain_eps) < CONSOLIDATION_THRESHOLD:
                continue
            
            # Cluster by context similarity (greedy)
            clusters: List[List[Episode]] = []
            for ep in domain_eps:
                placed = False
                ep_ctx_text = _context_to_text(ep.context)
                for cluster in clusters:
                    rep_ctx_text = _context_to_text(cluster[0].context)
                    sim = _jaccard_similarity(ep_ctx_text, rep_ctx_text)
                    if sim >= SIMILARITY_THRESHOLD:
                        cluster.append(ep)
                        placed = True
                        break
                if not placed:
                    clusters.append([ep])
            
            # Create schemas from large enough clusters
            for cluster in clusters:
                if len(cluster) < CONSOLIDATION_THRESHOLD:
                    continue
                
                # Find best strategy
                strategy_scores: Dict[str, List[float]] = defaultdict(list)
                all_lessons: List[str] = []
                
                for ep in cluster:
                    strat = ep.strategy_used or ep.action_type
                    strategy_scores[strat].append(ep.outcome_score)
                    all_lessons.extend(ep.lessons)
                    used_ids.add(ep.episode_id)
                
                # Best strategy by avg score
                best_strat = max(strategy_scores.keys(),
                                key=lambda s: sum(strategy_scores[s]) / len(strategy_scores[s]))
                best_score = sum(strategy_scores[best_strat]) / len(strategy_scores[best_strat])
                
                # Alternative strategies
                alternatives = []
                for strat, scores in strategy_scores.items():
                    if strat != best_strat:
                        avg = sum(scores) / len(scores)
                        success = sum(1 for s in scores if s > 0.5) / len(scores)
                        alternatives.append((strat, success))
                alternatives.sort(key=lambda x: x[1], reverse=True)
                
                # Common context pattern (intersection of keys with modal values)
                context_pattern = {}
                all_keys = set()
                for ep in cluster:
                    all_keys.update(ep.context.keys())
                for key in all_keys:
                    values = [ep.context.get(key) for ep in cluster if key in ep.context]
                    if values:
                        # Use most common value
                        from collections import Counter
                        most_common = Counter(str(v) for v in values).most_common(1)
                        if most_common and most_common[0][1] >= len(cluster) * 0.5:
                            context_pattern[key] = most_common[0][0]
                
                schema = Schema(
                    schema_id=hashlib.md5(f"{domain}{best_strat}{time.time()}".encode()).hexdigest()[:12],
                    pattern_name=f"{domain}_{best_strat}_pattern",
                    context_pattern=context_pattern,
                    best_strategy=best_strat,
                    success_rate=sum(1 for ep in cluster if ep.outcome_score > 0.5) / len(cluster),
                    avg_score=sum(ep.outcome_score for ep in cluster) / len(cluster),
                    episode_count=len(cluster),
                    episode_ids=[ep.episode_id for ep in cluster],
                    confidence=min(1.0, len(cluster) / 10),
                    domain=domain,
                    alternative_strategies=alternatives[:3],
                    created_at=time.time(),
                    last_updated=time.time(),
                )
                new_schemas.append(schema)
        
        self.schemas.extend(new_schemas)
        
        # Prune low-confidence schemas
        self.schemas = [s for s in self.schemas if s.confidence >= MIN_SCHEMA_CONFIDENCE]
        if len(self.schemas) > MAX_SCHEMAS:
            self.schemas.sort(key=lambda s: s.confidence * s.success_rate, reverse=True)
            self.schemas = self.schemas[:MAX_SCHEMAS]
        
        return new_schemas

    def suggest_strategy(
        self,
        context: Dict[str, Any],
        domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Suggest strategies based on past episodes and schemas.
        
        Returns list of strategy suggestions, each with:
        - strategy: name of the strategy
        - confidence: how confident we are
        - basis: "episode" or "schema"
        - supporting_evidence: count of supporting episodes/schemas
        - expected_score: predicted outcome score
        """
        suggestions = []
        
        # 1. Schema-based suggestions (consolidated knowledge)
        for schema in self.schemas:
            if domain and schema.domain != domain:
                continue
            
            # Check context pattern match
            ctx_text = _context_to_text(context)
            pattern_text = _context_to_text(schema.context_pattern)
            sim = _jaccard_similarity(ctx_text, pattern_text)
            
            if sim >= SIMILARITY_THRESHOLD and schema.confidence >= TRANSFER_CONFIDENCE_THRESHOLD:
                suggestions.append({
                    "strategy": schema.best_strategy,
                    "confidence": schema.confidence * sim,
                    "basis": "schema",
                    "pattern_name": schema.pattern_name,
                    "supporting_evidence": schema.episode_count,
                    "expected_score": schema.avg_score,
                    "success_rate": schema.success_rate,
                    "alternatives": schema.alternative_strategies[:2],
                })
        
        # 2. Episode-based suggestions (raw experience)
        relevant_episodes = self.retrieve(context, domain=domain, top_k=TOP_K_RETRIEVAL)
        
        if len(relevant_episodes) >= MIN_EPISODES_FOR_TRANSFER:
            # Group by strategy
            strategy_episodes: Dict[str, List[Tuple[Episode, float]]] = defaultdict(list)
            for ep, relevance in relevant_episodes:
                strat = ep.strategy_used or ep.action_type
                strategy_episodes[strat].append((ep, relevance))
            
            for strat, eps_with_score in strategy_episodes.items():
                avg_relevance = sum(r for _, r in eps_with_score) / len(eps_with_score)
                avg_outcome = sum(ep.outcome_score for ep, _ in eps_with_score) / len(eps_with_score)
                success_count = sum(1 for ep, _ in eps_with_score if ep.outcome == "success")
                
                if avg_relevance >= TRANSFER_CONFIDENCE_THRESHOLD * 0.5:
                    suggestions.append({
                        "strategy": strat,
                        "confidence": avg_relevance * avg_outcome,
                        "basis": "episode",
                        "supporting_evidence": len(eps_with_score),
                        "expected_score": avg_outcome,
                        "success_rate": success_count / len(eps_with_score),
                        "lessons": list(set(
                            lesson for ep, _ in eps_with_score for lesson in ep.lessons[:2]
                        ))[:5],
                    })
        
        # Sort by confidence
        suggestions.sort(key=lambda s: s["confidence"], reverse=True)
        
        return suggestions

    def get_strategy_stats(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about strategy effectiveness."""
        stats = {}
        for key, counts in self._strategy_stats.items():
            d, strat = key.split(":", 1)
            if domain and d != domain:
                continue
            success_rate = counts["success"] / counts["total"] if counts["total"] > 0 else 0
            stats[key] = {
                "domain": d,
                "strategy": strat,
                "total": counts["total"],
                "success": counts["success"],
                "success_rate": round(success_rate, 3),
            }
        return stats

    def get_summary(self) -> Dict[str, Any]:
        """Summary of episodic memory state."""
        return {
            "version": VERSION,
            "total_episodes": len(self.episodes),
            "total_schemas": len(self.schemas),
            "domains": list(self._domain_index.keys()),
            "episodes_per_domain": {d: len(ids) for d, ids in self._domain_index.items()},
            "strategy_stats": self.get_strategy_stats(),
            "avg_outcome": (
                sum(e.outcome_score for e in self.episodes) / len(self.episodes)
                if self.episodes else 0.0
            ),
            "success_rate": (
                sum(1 for e in self.episodes if e.outcome == "success") / len(self.episodes)
                if self.episodes else 0.0
            ),
        }

    def _prune_oldest(self, count: int):
        """Remove oldest low-value episodes."""
        # Score: outcome_score × recency × access_frequency
        now = time.time()
        scored = []
        for ep in self.episodes:
            age_hours = (now - ep.timestamp) / 3600
            recency = math.exp(-0.029 * age_hours)
            access_freq = ep.access_count / max(age_hours, 1)
            value = ep.outcome_score * 0.4 + recency * 0.3 + min(access_freq, 1.0) * 0.3
            scored.append((ep, value))
        
        scored.sort(key=lambda x: x[1])
        to_remove = set(ep.episode_id for ep, _ in scored[:count])
        
        self.episodes = [e for e in self.episodes if e.episode_id not in to_remove]
        for eid in to_remove:
            self._episode_index.pop(eid, None)
            for domain_ids in self._domain_index.values():
                if eid in domain_ids:
                    domain_ids.remove(eid)

    def _save(self, path: str):
        """Persist to JSON."""
        data = {
            "version": VERSION,
            "episodes": [asdict(e) for e in self.episodes],
            "schemas": [asdict(s) for s in self.schemas],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self, path: str):
        """Load from JSON."""
        try:
            with open(path) as f:
                data = json.load(f)
            for ep_data in data.get("episodes", []):
                ep = Episode(**ep_data)
                self.episodes.append(ep)
                self._episode_index[ep.episode_id] = ep
                self._domain_index[ep.domain].append(ep.episode_id)
            for schema_data in data.get("schemas", []):
                # Handle tuples in alternative_strategies
                if "alternative_strategies" in schema_data:
                    schema_data["alternative_strategies"] = [
                        tuple(s) if isinstance(s, list) else s
                        for s in schema_data["alternative_strategies"]
                    ]
                self.schemas.append(Schema(**schema_data))
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # Corrupted file, start fresh


# ── Integration with SubgoalResolver ──

def integrate_with_subgoal_resolver(memory: EpisodicMemoryEngine, resolver) -> None:
    """Hook episodic memory into SubgoalResolver for strategy suggestions.
    
    When resolver encounters a failure:
    1. Query episodic memory for similar past situations
    2. Suggest strategy based on past success
    3. Record outcome after resolution attempt
    """
    if not hasattr(resolver, '_original_resolve'):
        resolver._original_resolve = resolver.resolve_failure if hasattr(resolver, 'resolve_failure') else None
    
    def enhanced_resolve(subgoal, failure_type, **kwargs):
        # Query past episodes
        context = {
            "task_type": getattr(subgoal, 'task_type', 'unknown'),
            "failure_type": str(failure_type),
            "domain": kwargs.get("domain", "general"),
        }
        suggestions = memory.suggest_strategy(context, domain=kwargs.get("domain"))
        
        # Try suggested strategy first if confident
        if suggestions and suggestions[0]["confidence"] >= TRANSFER_CONFIDENCE_THRESHOLD:
            kwargs["preferred_strategy"] = suggestions[0]["strategy"]
        
        # Call original resolver
        result = resolver._original_resolve(subgoal, failure_type, **kwargs) if resolver._original_resolve else None
        
        # Record episode
        outcome = "success" if result and getattr(result, 'resolved', False) else "failure"
        score = getattr(result, 'confidence', 0.5) if result else 0.0
        memory.record_episode(
            context=context,
            action=str(getattr(result, 'strategy_used', 'unknown')),
            action_type=kwargs.get("preferred_strategy", "default"),
            outcome=outcome,
            outcome_score=score,
            lessons=[str(getattr(result, 'lesson', ''))],
            domain=kwargs.get("domain", "general"),
        )
        
        return result
    
    if resolver._original_resolve:
        resolver.resolve_failure = enhanced_resolve


if __name__ == "__main__":
    # Smoke test
    engine = EpisodicMemoryEngine()
    
    # Record some episodes
    for i in range(5):
        engine.record_episode(
            context={"task_type": "search", "difficulty": "hard", "domain": "biology"},
            action=f"search_pubmed_{i}",
            action_type="search",
            outcome="success" if i % 2 == 0 else "failure",
            outcome_score=0.8 if i % 2 == 0 else 0.3,
            lessons=[f"PubMed works for biology queries (trial {i})"],
            domain="biology",
            strategy_used="pubmed_search",
        )
    
    for i in range(4):
        engine.record_episode(
            context={"task_type": "verify", "difficulty": "medium", "domain": "physics"},
            action=f"verify_claim_{i}",
            action_type="verify",
            outcome="success" if i < 3 else "failure",
            outcome_score=0.9 if i < 3 else 0.2,
            lessons=[f"Cross-reference with arxiv effective (trial {i})"],
            domain="physics",
            strategy_used="arxiv_verify",
        )
    
    # Consolidate
    new_schemas = engine.consolidate()
    print(f"Created {len(new_schemas)} schemas from {len(engine.episodes)} episodes")
    
    # Retrieve
    results = engine.retrieve(
        context={"task_type": "search", "difficulty": "hard", "domain": "biology"},
        domain="biology"
    )
    print(f"Retrieved {len(results)} relevant episodes")
    
    # Suggest
    suggestions = engine.suggest_strategy(
        context={"task_type": "search", "difficulty": "hard", "domain": "biology"},
        domain="biology"
    )
    print(f"Got {len(suggestions)} strategy suggestions")
    for s in suggestions[:3]:
        print(f"  → {s['strategy']} (conf={s['confidence']:.2f}, basis={s['basis']})")
    
    # Summary
    summary = engine.get_summary()
    print(f"\nSummary: {summary['total_episodes']} episodes, {summary['total_schemas']} schemas")
    print(f"Domains: {summary['domains']}")
    print(f"Avg outcome: {summary['avg_outcome']:.2f}")
    print("✅ EpisodicMemoryEngine smoke test passed")
