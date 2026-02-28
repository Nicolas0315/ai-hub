"""
Toxicity Detector — Session-level contamination detection + auto-purge.

Monitors Ephemeral Learning (E1/E2/E3) for contamination patterns:
  - Confidence drift: solver weights drifting in one direction (manipulation)
  - Pattern poisoning: domain bias patterns being injected
  - Chain corruption: goal chain insights converging on false conclusions
  - Consistency collapse: sudden contradictions in accumulated session data

When toxicity detected → auto-purge affected mechanisms + alert.

Design: Youta Hilono, 2026-02-28
Application of L7 Adversarial principles to session-level safety.
"""

import re
import math
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter


# ── Toxicity Signals ──

def _check_confidence_drift(calibration_data: Dict[str, float], threshold: float = 0.3) -> List[Dict]:
    """Detect systematic drift in solver confidence calibration (E1).
    
    If multiple solvers are being pushed in the same direction,
    it suggests coordinated manipulation rather than legitimate learning.
    """
    issues = []
    if not calibration_data:
        return issues
    
    weights = list(calibration_data.values())
    if len(weights) < 2:
        return issues
    
    # Check for uniform drift direction
    avg = sum(weights) / len(weights)
    if avg < 0.7:  # All weights suppressed
        below = sum(1 for w in weights if w < 0.8)
        if below > len(weights) * 0.7:
            issues.append({
                "type": "systematic_suppression",
                "detail": f"{below}/{len(weights)} solvers suppressed (avg weight {avg:.2f})",
                "severity": "high",
                "mechanism": "E1",
            })
    
    # Check for single solver dominance
    if weights:
        max_w = max(weights)
        min_w = min(weights)
        if max_w - min_w > threshold and max_w >= 0.95:
            issues.append({
                "type": "single_solver_dominance",
                "detail": f"Weight spread {max_w:.2f}-{min_w:.2f} = {max_w-min_w:.2f}",
                "severity": "medium",
                "mechanism": "E1",
            })
    
    return issues


def _check_pattern_poisoning(domain_patterns: List[Dict]) -> List[Dict]:
    """Detect pattern poisoning in domain bias tracking (E2).
    
    Red flags:
    - Single domain dominating all patterns
    - Contradictory domain patterns
    - Suspiciously uniform distribution (adversarial injection)
    """
    issues = []
    if not domain_patterns:
        return issues
    
    # Domain concentration
    domains = [p.get("domain", "unknown") for p in domain_patterns]
    domain_counts = Counter(domains)
    
    if domain_counts and len(domain_counts) == 1 and len(domains) > 3:
        issues.append({
            "type": "single_domain_concentration",
            "detail": f"All {len(domains)} patterns in domain '{domains[0]}'",
            "severity": "medium",
            "mechanism": "E2",
        })
    
    # Contradictory patterns (same domain, opposite recommendations)
    recommendations = {}
    for p in domain_patterns:
        domain = p.get("domain", "")
        rec = p.get("recommendation", "")
        if domain not in recommendations:
            recommendations[domain] = []
        recommendations[domain].append(rec)
    
    for domain, recs in recommendations.items():
        if len(set(recs)) > 1 and len(recs) > 2:
            issues.append({
                "type": "contradictory_patterns",
                "detail": f"Domain '{domain}' has {len(set(recs))} different recommendations in {len(recs)} patterns",
                "severity": "high",
                "mechanism": "E2",
            })
    
    return issues


def _check_chain_corruption(chain_insights: List[Dict]) -> List[Dict]:
    """Detect corruption in verification chain learning (E3).
    
    Red flags:
    - All chains converging to same conclusion (echo chamber)
    - Confidence modifiers all negative (systematic discouragement)
    - Rapid confidence swings (instability injection)
    """
    issues = []
    if not chain_insights:
        return issues
    
    # Echo chamber: all same result
    results = [i.get("result", "") for i in chain_insights]
    if len(set(results)) == 1 and len(results) > 3:
        issues.append({
            "type": "echo_chamber",
            "detail": f"All {len(results)} chain results identical: '{results[0]}'",
            "severity": "high",
            "mechanism": "E3",
        })
    
    # Systematic negative modifiers
    modifiers = [i.get("confidence_modifier", 0) for i in chain_insights if "confidence_modifier" in i]
    if modifiers:
        neg = sum(1 for m in modifiers if m < 0)
        if neg > len(modifiers) * 0.8 and len(modifiers) > 2:
            issues.append({
                "type": "systematic_pessimism",
                "detail": f"{neg}/{len(modifiers)} chains produced negative modifiers",
                "severity": "medium",
                "mechanism": "E3",
            })
    
    # Rapid confidence swings
    if len(modifiers) > 2:
        swings = sum(1 for i in range(1, len(modifiers)) if abs(modifiers[i] - modifiers[i-1]) > 0.3)
        if swings > len(modifiers) * 0.5:
            issues.append({
                "type": "instability_injection",
                "detail": f"{swings} rapid swings detected in {len(modifiers)} chain modifiers",
                "severity": "high",
                "mechanism": "E3",
            })
    
    return issues


def _check_content_contamination(verified_texts: List[str]) -> List[Dict]:
    """Check if adversarial content is being fed through verification.
    
    Detects:
    - Prompt injection patterns in claim text
    - Repeated near-identical claims (grinding attack)
    - Hate speech / extremist content patterns
    """
    issues = []
    if not verified_texts:
        return issues
    
    injection_patterns = [
        re.compile(r'ignore\s+(?:all\s+)?(?:previous|above)\s+instructions?', re.I),
        re.compile(r'you\s+are\s+now\s+(?:a|an|the)', re.I),
        re.compile(r'system\s*:\s*', re.I),
        re.compile(r'</?\w+>', re.I),  # HTML tags in claims
        re.compile(r'\{\{.*\}\}', re.I),  # Template injection
    ]
    
    for text in verified_texts:
        for pattern in injection_patterns:
            if pattern.search(text):
                issues.append({
                    "type": "prompt_injection_attempt",
                    "detail": f"Injection pattern detected in claim: '{text[:50]}...'",
                    "severity": "critical",
                    "mechanism": "content",
                })
                break
    
    # Grinding: many near-identical claims
    if len(verified_texts) > 5:
        # Simple dedup by first 30 chars
        prefixes = [t[:30].lower() for t in verified_texts]
        prefix_counts = Counter(prefixes)
        for prefix, count in prefix_counts.items():
            if count > 3:
                issues.append({
                    "type": "grinding_attack",
                    "detail": f"Claim prefix '{prefix}...' repeated {count} times",
                    "severity": "medium",
                    "mechanism": "content",
                })
    
    return issues


class ToxicityDetector:
    """Session-level toxicity monitoring with auto-purge capability."""
    
    def __init__(self, auto_purge: bool = True, alert_threshold: str = "medium"):
        """
        Args:
            auto_purge: Automatically purge contaminated mechanisms.
            alert_threshold: "low", "medium", "high", "critical" — minimum severity to trigger purge.
        """
        self.auto_purge = auto_purge
        self.alert_threshold = alert_threshold
        self._severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        self._scan_history = []
        self._purge_log = []
    
    def scan(
        self,
        ephemeral_session: Any = None,
        calibration_data: Dict[str, float] = None,
        domain_patterns: List[Dict] = None,
        chain_insights: List[Dict] = None,
        verified_texts: List[str] = None,
    ) -> Dict[str, Any]:
        """Run full toxicity scan on session data.
        
        Can accept raw data or an EphemeralSession object.
        """
        # Extract from EphemeralSession if provided
        if ephemeral_session is not None:
            session = ephemeral_session
            if hasattr(session, '_e1_weights'):
                calibration_data = calibration_data or dict(session._e1_weights)
            if hasattr(session, '_e2_patterns'):
                domain_patterns = domain_patterns or list(session._e2_patterns)
            if hasattr(session, '_e3_insights'):
                chain_insights = chain_insights or list(session._e3_insights)
        
        all_issues = []
        
        # Run all checks
        all_issues.extend(_check_confidence_drift(calibration_data or {}))
        all_issues.extend(_check_pattern_poisoning(domain_patterns or []))
        all_issues.extend(_check_chain_corruption(chain_insights or []))
        all_issues.extend(_check_content_contamination(verified_texts or []))
        
        # Sort by severity
        all_issues.sort(key=lambda x: self._severity_order.get(x.get("severity", "low"), 0), reverse=True)
        
        # Determine if purge needed
        threshold_level = self._severity_order.get(self.alert_threshold, 1)
        trigger_issues = [
            i for i in all_issues
            if self._severity_order.get(i.get("severity", "low"), 0) >= threshold_level
        ]
        
        purge_needed = len(trigger_issues) > 0
        mechanisms_to_purge = list(set(i.get("mechanism", "") for i in trigger_issues if i.get("mechanism")))
        
        result = {
            "toxic": purge_needed,
            "issues": all_issues,
            "issue_count": len(all_issues),
            "max_severity": all_issues[0]["severity"] if all_issues else "none",
            "mechanisms_affected": mechanisms_to_purge,
            "purge_recommended": purge_needed,
            "auto_purge_enabled": self.auto_purge,
        }
        
        # Auto-purge if enabled
        if purge_needed and self.auto_purge and ephemeral_session is not None:
            purge_result = self._auto_purge(ephemeral_session, mechanisms_to_purge)
            result["purge_executed"] = True
            result["purge_result"] = purge_result
        else:
            result["purge_executed"] = False
        
        self._scan_history.append({
            "issues": len(all_issues),
            "purged": result.get("purge_executed", False),
        })
        
        return result
    
    def _auto_purge(self, session: Any, mechanisms: List[str]) -> Dict[str, Any]:
        """Purge contaminated mechanisms from ephemeral session."""
        purged = []
        
        for mech in mechanisms:
            try:
                if mech == "E1" and hasattr(session, 'set_mechanism'):
                    # Reset E1 calibration
                    session.set_mechanism("E1_calibration", False)
                    if hasattr(session, '_e1_weights'):
                        session._e1_weights.clear()
                    purged.append("E1_calibration")
                
                elif mech == "E2" and hasattr(session, 'set_mechanism'):
                    session.set_mechanism("E2_pattern_memory", False)
                    if hasattr(session, '_e2_patterns'):
                        session._e2_patterns.clear()
                    purged.append("E2_pattern_memory")
                
                elif mech == "E3" and hasattr(session, 'set_mechanism'):
                    session.set_mechanism("E3_chain_learning", False)
                    if hasattr(session, '_e3_insights'):
                        session._e3_insights.clear()
                    purged.append("E3_chain_learning")
                
                elif mech == "content":
                    # Content contamination — full reset recommended
                    if hasattr(session, 'reset_learning'):
                        session.reset_learning()
                        purged.append("full_reset")
                
            except Exception as e:
                purged.append(f"FAILED:{mech}:{str(e)[:50]}")
        
        self._purge_log.append({"mechanisms": mechanisms, "purged": purged})
        
        return {
            "mechanisms_targeted": mechanisms,
            "purged": purged,
            "success": all(not p.startswith("FAILED") for p in purged),
        }
    
    def get_history(self) -> Dict[str, Any]:
        """Get scan and purge history."""
        return {
            "scans": len(self._scan_history),
            "purges": len(self._purge_log),
            "history": self._scan_history[-10:],
            "purge_log": self._purge_log[-10:],
        }
