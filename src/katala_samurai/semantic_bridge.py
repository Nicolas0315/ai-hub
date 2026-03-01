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


# ── LLM connection cache ──
_ollama_alive: bool | None = None  # None = untested, True/False = cached
_ollama_alive_ts: float = 0.0
_OLLAMA_CACHE_TTL = 300.0  # cache Ollama liveness for 5 minutes


def _check_ollama_alive(host: str, port: int) -> bool:
    """Cached Ollama liveness probe. Avoids 2s socket timeout on every call."""
    global _ollama_alive, _ollama_alive_ts
    now = time.time()
    if _ollama_alive is not None and (now - _ollama_alive_ts) < _OLLAMA_CACHE_TTL:
        return _ollama_alive
    try:
        import socket
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        _ollama_alive = True
    except Exception:
        _ollama_alive = False
    _ollama_alive_ts = now
    return _ollama_alive


def _parse_llm_json(text: str):
    """Extract JSON from LLM response, stripping markdown fences."""
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json.loads(json_match.group())
    return None


def _call_llm(prompt, timeout=12):
    """Call available LLM for semantic extraction. Non-judging use only.

    Priority: Ollama (local, cached probe) → Gemini (flash) → OpenAI.
    Optimizations:
    - Ollama liveness is cached for 5 minutes (no repeated socket probes)
    - Gemini uses gemini-2.0-flash-lite for speed
    - Timeout reduced from 15s to 12s
    - JSON parsing centralized
    """
    # --- Ollama (local LLM) — cached liveness check ---
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    from urllib.parse import urlparse
    parsed = urlparse(ollama_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 11434

    if _check_ollama_alive(host, port):
        try:
            payload = json.dumps({
                "model": ollama_model,
                "prompt": prompt + "\n/no_think",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024},
            }).encode()
            req = urllib.request.Request(
                f"{ollama_url}/api/generate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                result = _parse_llm_json(data.get("response", ""))
                if result:
                    return result
        except Exception:
            pass

    # --- Gemini API (flash-lite for speed) ---
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            # Use flash-lite: faster, cheaper, sufficient for extraction
            model = os.environ.get("KS_GEMINI_MODEL", "gemini-2.0-flash-lite")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
            }).encode()
            req = urllib.request.Request(url, data=payload,
                                        headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                result = _parse_llm_json(text)
                if result:
                    return result
        except Exception:
            pass

    # --- OpenAI (fallback) ---
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
                result = _parse_llm_json(text)
                if result:
                    return result
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

    # Enhanced degraded mode: structural analysis without LLM
    # Instead of just splitting sentences, extract typed propositions
    # and basic causal/semantic structure from text patterns.
    sentences = re.split(r'[.;]\s+', claim_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    propositions = []
    implicit_assumptions = []
    key_entities = []
    causal_links = []

    # Causal keywords → typed propositions
    causal_keywords = {
        "because": "causal", "therefore": "causal", "hence": "causal",
        "thus": "causal", "consequently": "causal", "causes": "causal",
        "leads to": "causal", "results in": "causal", "due to": "causal",
        "since": "causal", "so ": "causal", "implies": "causal",
    }
    comparative_keywords = ["more", "less", "better", "worse", "greater",
                            "smaller", "higher", "lower", "than", "compared"]
    definitional_keywords = ["is a", "is an", "defined as", "refers to",
                             "means", "constitutes"]
    temporal_keywords = ["before", "after", "during", "when", "then",
                         "previously", "currently", "recently"]

    text_lower = claim_text.lower()
    for sent in sentences:
        sent_lower = sent.lower()

        # Classify proposition type
        ptype = "factual"  # default
        for kw, ctype in causal_keywords.items():
            if kw in sent_lower:
                ptype = ctype
                # Extract causal link
                parts = re.split(r'\b(?:because|therefore|hence|thus|since|causes|leads to|results in|due to)\b',
                                 sent, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    causal_links.append({
                        "cause": parts[0].strip()[:80],
                        "effect": parts[-1].strip()[:80],
                        "strength": "moderate",
                    })
                break
        if ptype == "factual":
            if any(kw in sent_lower for kw in comparative_keywords):
                ptype = "comparative"
            elif any(kw in sent_lower for kw in definitional_keywords):
                ptype = "definitional"

        propositions.append({"text": sent, "type": ptype})

    # Extract entities: capitalized words, numbers, quoted terms
    entity_pattern = re.compile(r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\d+(?:\.\d+)?(?:\s*%|\s*[A-Za-z]+)?|"[^"]+"|\'[^\']+\')')
    for match in entity_pattern.finditer(claim_text):
        entity = match.group().strip("\"'")
        if len(entity) > 1 and entity.lower() not in {"the", "a", "an", "is", "it"}:
            key_entities.append(entity)
    key_entities = list(dict.fromkeys(key_entities))[:10]  # dedupe, max 10

    # Implicit assumptions from quantifiers and conditionals
    if any(w in text_lower for w in ["all ", "every ", "always ", "never "]):
        implicit_assumptions.append("Universal quantifier implies no exceptions exist")
    if "if " in text_lower:
        implicit_assumptions.append("Conditional claim assumes antecedent can be true")
    if any(w in text_lower for w in ["should ", "must ", "need "]):
        implicit_assumptions.append("Normative claim assumes shared value framework")

    return {
        "mode": "degraded_enhanced",
        "propositions": propositions if propositions else [{"text": claim_text, "type": "factual"}],
        "implicit_assumptions": implicit_assumptions,
        "key_entities": key_entities,
        "causal_links": causal_links,
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
