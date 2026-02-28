"""
Layer 5: Semantic Bridge — LLM-powered content understanding for KS31d.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Purpose:
  Solve Issue #64 (content-blindness): S01-S28 verify form, not meaning.
  The Semantic Bridge extracts structured meaning from claims using LLM,
  then converts it into formal propositions that S01-S28 CAN verify.

Architecture:
  claim_text → LLM semantic extraction → structured propositions
    → each proposition → L1 formal verification
    → delta comparison: original L1 score vs semantically-enriched L1 score

  This is NOT "LLM says true/false". This is:
    "LLM extracts what the claim MEANS → formal verifiers check if that meaning holds"

Principles:
  - LLM is used for UNDERSTANDING, not JUDGING
  - All judgments still go through S01-S28 (non-LLM, deterministic)
  - M1 Counter-Factual validates that semantic enrichment actually helps
  - No accumulation: fresh extraction every run
"""

import os
import json
import urllib.request
import re
import time


EXTRACTION_PROMPT = """Extract the core logical propositions from this claim. 
Break it into independent, verifiable statements.

Claim: {claim_text}
Evidence context: {evidence}

Respond in EXACTLY this JSON format (no markdown):
{{
  "propositions": [
    {{"text": "proposition 1", "type": "factual|causal|definitional|comparative"}},
    {{"text": "proposition 2", "type": "factual|causal|definitional|comparative"}}
  ],
  "implicit_assumptions": ["assumption 1", "assumption 2"],
  "key_entities": ["entity1", "entity2"],
  "causal_links": [
    {{"cause": "X", "effect": "Y", "strength": "strong|moderate|weak|assumed"}}
  ]
}}"""


CAUSAL_ANALYSIS_PROMPT = """Analyze the causal structure of this claim.
Identify all cause-effect relationships, their direction, and any missing links.

Claim: {claim_text}

Respond in EXACTLY this JSON format (no markdown):
{{
  "causal_chain": [
    {{"from": "cause", "to": "effect", "mechanism": "how", "strength": "strong|moderate|weak|assumed", "reversible": true}}
  ],
  "confounders": ["possible confounder 1"],
  "missing_links": ["gap in reasoning 1"],
  "overall_causal_validity": "valid|partial|weak|unfounded"
}}"""


def _call_llm(prompt, timeout=15):
    """Call available LLM for semantic extraction. Non-judging use only."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
            }).encode()
            req = urllib.request.Request(url, data=payload,
                                        headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = re.sub(r'^```json\s*', '', text.strip())
                text = re.sub(r'\s*```$', '', text.strip())
                return json.loads(text)
        except Exception:
            pass

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1, "max_tokens": 1024,
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions", data=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                text = data["choices"][0]["message"]["content"]
                text = re.sub(r'^```json\s*', '', text.strip())
                text = re.sub(r'\s*```$', '', text.strip())
                return json.loads(text)
        except Exception:
            pass

    return None


def extract_semantics(claim_text, evidence=None):
    """Extract structured semantic content from a claim using LLM."""
    t0 = time.time()
    evidence_str = ", ".join(evidence[:5]) if evidence else "none"
    prompt = EXTRACTION_PROMPT.format(claim_text=claim_text, evidence=evidence_str)

    result = _call_llm(prompt)
    latency = round(time.time() - t0, 3)

    if result and "propositions" in result:
        return {
            "mode": "llm",
            "propositions": result["propositions"],
            "implicit_assumptions": result.get("implicit_assumptions", []),
            "key_entities": result.get("key_entities", []),
            "causal_links": result.get("causal_links", []),
            "latency_ms": latency * 1000,
        }

    # Degraded mode: sentence splitting (no LLM)
    sentences = re.split(r'[.;]\s+', claim_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    return {
        "mode": "degraded",
        "propositions": [{"text": s, "type": "unknown"} for s in sentences],
        "implicit_assumptions": [],
        "key_entities": [],
        "causal_links": [],
        "latency_ms": latency * 1000,
    }


def analyze_causality(claim_text):
    """Analyze causal structure of a claim using LLM."""
    t0 = time.time()
    prompt = CAUSAL_ANALYSIS_PROMPT.format(claim_text=claim_text)

    result = _call_llm(prompt)
    latency = round(time.time() - t0, 3)

    if result and "causal_chain" in result:
        return {
            "mode": "llm",
            "causal_chain": result["causal_chain"],
            "confounders": result.get("confounders", []),
            "missing_links": result.get("missing_links", []),
            "overall_causal_validity": result.get("overall_causal_validity", "unknown"),
            "latency_ms": latency * 1000,
        }

    causal_keywords = ["therefore", "because", "causes", "leads to", "results in", "due to"]
    has_causal = any(kw in claim_text.lower() for kw in causal_keywords)
    return {
        "mode": "degraded",
        "causal_chain": [],
        "confounders": [],
        "missing_links": ["LLM unavailable — causal analysis not possible"],
        "overall_causal_validity": "unknown" if has_causal else "non_causal",
        "latency_ms": latency * 1000,
    }


def semantic_enrichment_delta(original_l1_results, enriched_l1_results):
    """Compare L1 results before/after semantic enrichment."""
    orig_rate = original_l1_results.get("pass_rate", 0)
    enriched_rates = [r.get("pass_rate", 0) for r in enriched_l1_results]

    if not enriched_rates:
        return {
            "original_rate": orig_rate, "enriched_avg_rate": 0,
            "delta": 0, "semantic_impact": "NO_PROPOSITIONS",
        }

    avg_enriched = sum(enriched_rates) / len(enriched_rates)
    delta = abs(orig_rate - avg_enriched)

    impact = "HIGH" if delta >= 0.15 else ("MODERATE" if delta >= 0.05 else "LOW")

    return {
        "original_rate": round(orig_rate, 4),
        "enriched_avg_rate": round(avg_enriched, 4),
        "enriched_individual_rates": [round(r, 4) for r in enriched_rates],
        "delta": round(delta, 4),
        "semantic_impact": impact,
        "proposition_count": len(enriched_rates),
    }
