"""
KS30 Real LLM API Integration (#61)
Replaces hardcoded confidence stubs with actual LLM inference.

Each LLM evaluates a claim and returns:
- confidence: 0.0-1.0 (how likely the claim is true)
- reasoning: why
- cultural_note: any cultural/regulatory bias the LLM is aware of

Design: Youta Hilono
Implementation: Shirokuma
"""

import json
import os
import urllib.request
import time
from dataclasses import dataclass


@dataclass
class LLMVerdict:
    """Result of an LLM evaluating a claim."""
    llm_name: str
    confidence: float  # 0.0-1.0
    reasoning: str
    cultural_note: str
    raw_response: str
    latency_ms: float
    error: str | None = None


EVAL_PROMPT = """You are a claim verification system. Evaluate the following claim for truthfulness.

Claim: {claim_text}
Evidence provided: {evidence}

Respond in EXACTLY this JSON format (no markdown, no extra text):
{{"confidence": 0.XX, "reasoning": "...", "cultural_note": "..."}}

Rules:
- confidence: 0.0 = certainly false, 0.5 = uncertain, 1.0 = certainly true
- reasoning: brief explanation (1-2 sentences)
- cultural_note: note any cultural, political, or regulatory bias that might affect your judgment (or "none")
- Be honest about uncertainty. Do not default to 0.5."""


def _parse_llm_json(text):
    """Extract JSON from LLM response (handles markdown wrapping)."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in text
        import re
        m = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# API Backends
# ═══════════════════════════════════════════════════════════════════════════

def _call_openai(claim_text, evidence, model="gpt-4o", api_key=None, timeout=30):
    """OpenAI-compatible API call (GPT-5, GPT-4o, etc.)."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None, "No OPENAI_API_KEY"

    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": EVAL_PROMPT.format(
            claim_text=claim_text, evidence=json.dumps(evidence, ensure_ascii=False)
        )}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


def _call_gemini(claim_text, evidence, model="gemini-2.0-flash", api_key=None, timeout=30):
    """Google Gemini API call."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None, "No GEMINI_API_KEY"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": EVAL_PROMPT.format(
            claim_text=claim_text, evidence=json.dumps(evidence, ensure_ascii=False)
        )}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["candidates"][0]["content"]["parts"][0]["text"], None
    except Exception as e:
        return None, str(e)


def _call_mistral(claim_text, evidence, model="mistral-large-latest", api_key=None, timeout=30):
    """Mistral API call."""
    api_key = api_key or os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        return None, "No MISTRAL_API_KEY"

    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": EVAL_PROMPT.format(
            claim_text=claim_text, evidence=json.dumps(evidence, ensure_ascii=False)
        )}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


def _call_qwen(claim_text, evidence, model="qwen-plus", api_key=None, timeout=30):
    """Alibaba Qwen (DashScope) API call."""
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        return None, "No DASHSCOPE_API_KEY"

    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": EVAL_PROMPT.format(
            claim_text=claim_text, evidence=json.dumps(evidence, ensure_ascii=False)
        )}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════════
# Unified Evaluation Interface
# ═══════════════════════════════════════════════════════════════════════════

# Maps LLM names to their API call functions + models
LLM_REGISTRY = {
    "gpt-5":          {"fn": _call_openai,  "model": "gpt-4o",                 "key_env": "OPENAI_API_KEY"},
    "mistral-large":  {"fn": _call_mistral, "model": "mistral-large-latest",   "key_env": "MISTRAL_API_KEY"},
    "qwen-3":         {"fn": _call_qwen,    "model": "qwen-plus",             "key_env": "DASHSCOPE_API_KEY"},
    "gemini-3-pro":   {"fn": _call_gemini,  "model": "gemini-2.0-flash",      "key_env": "GEMINI_API_KEY"},
    # Open-weight models — use OpenAI-compatible endpoints (vLLM, Ollama, etc.)
    "sea-lion":       {"fn": _call_openai,  "model": "sea-lion-v3-7b",        "key_env": "SEALION_API_KEY",   "base_url": None},
    "jais-2":         {"fn": _call_openai,  "model": "jais-adapted-70b-chat", "key_env": "JAIS_API_KEY",      "base_url": None},
    "inkuba-lm":      {"fn": _call_openai,  "model": "inkuba-instruct",       "key_env": "INKUBA_API_KEY",    "base_url": None},
    "latam-gpt":      {"fn": _call_openai,  "model": "latam-gpt-50b",        "key_env": "LATAMGPT_API_KEY",  "base_url": None},
}


def evaluate_claim(llm_name, claim_text, evidence=None, api_key=None):
    """Evaluate a claim using a specific LLM.
    
    Returns LLMVerdict with real API confidence or fallback stub.
    """
    evidence = evidence or []
    registry = LLM_REGISTRY.get(llm_name)
    
    if not registry:
        return LLMVerdict(
            llm_name=llm_name, confidence=0.5,
            reasoning="Unknown LLM", cultural_note="none",
            raw_response="", latency_ms=0, error="LLM not in registry"
        )
    
    # Check API key availability
    key = api_key or os.environ.get(registry["key_env"], "")
    if not key:
        # Fallback to stub
        from .ks29b import LLMPipeline
        base = LLMPipeline.BIAS_PROFILES.get(llm_name, {}).get("confidence_base", 0.5)
        return LLMVerdict(
            llm_name=llm_name, confidence=base,
            reasoning="STUB — no API key available",
            cultural_note="Using hardcoded confidence_base",
            raw_response="", latency_ms=0,
            error=f"No {registry['key_env']} set"
        )
    
    # Real API call
    t0 = time.time()
    fn = registry["fn"]
    raw, err = fn(claim_text, evidence, model=registry["model"], api_key=key)
    latency = (time.time() - t0) * 1000
    
    if err or not raw:
        return LLMVerdict(
            llm_name=llm_name, confidence=0.5,
            reasoning=f"API error: {err}", cultural_note="none",
            raw_response=raw or "", latency_ms=latency, error=err
        )
    
    # Parse response
    parsed = _parse_llm_json(raw)
    if parsed:
        return LLMVerdict(
            llm_name=llm_name,
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            cultural_note=parsed.get("cultural_note", "none"),
            raw_response=raw, latency_ms=latency
        )
    
    return LLMVerdict(
        llm_name=llm_name, confidence=0.5,
        reasoning=f"Failed to parse: {raw[:100]}",
        cultural_note="none", raw_response=raw,
        latency_ms=latency, error="JSON parse failed"
    )


def evaluate_claim_all(claim_text, evidence=None, llm_names=None):
    """Evaluate a claim across all available LLMs.
    
    Returns dict of llm_name -> LLMVerdict.
    Reports which are real API vs stub.
    """
    names = llm_names or list(LLM_REGISTRY.keys())
    results = {}
    for name in names:
        results[name] = evaluate_claim(name, claim_text, evidence)
    return results


def check_available_llms():
    """Check which LLMs have API keys configured."""
    status = {}
    for name, reg in LLM_REGISTRY.items():
        key = os.environ.get(reg["key_env"], "")
        status[name] = {
            "available": bool(key),
            "key_env": reg["key_env"],
            "model": reg["model"],
        }
    return status


# ═══════════════════════════════════════════════════════════════════════════
# Ollama Backend (Local LLM via Tailscale)
# ═══════════════════════════════════════════════════════════════════════════

OLLAMA_HOSTS = {
    # Tailscale IPs for GPU machines running Ollama
    "ultra2025": "http://100.80.232.85:11434",    # RTX 5070 Ti 16GB
    "nicolas2025": "http://100.109.55.96:11434",   # RTX 3070 8GB (backup)
}

# Map KS30 LLM roles to local Ollama models
OLLAMA_MODEL_MAP = {
    "qwen-3":         {"model": "qwen3:8b",        "host": "ultra2025"},   # Chinese bias detection
    "mistral-large":  {"model": "gemma3:12b",       "host": "ultra2025"},   # EU proxy (multilingual)
    "jais-2":         {"model": "aya-expanse:8b",   "host": "ultra2025"},   # Arabic/multilingual proxy
    "sea-lion":       {"model": "gemma3:12b",       "host": "ultra2025"},   # SEA proxy
    "inkuba-lm":      {"model": "aya-expanse:8b",   "host": "ultra2025"},   # Africa proxy
    "latam-gpt":      {"model": "gemma3:12b",       "host": "ultra2025"},   # LatAm proxy
}


def _call_ollama(claim_text, evidence, model="gemma3:12b", host="ultra2025", timeout=60):
    """Call Ollama API via Tailscale for local LLM inference."""
    base_url = OLLAMA_HOSTS.get(host, f"http://{host}:11434")
    url = f"{base_url}/api/chat"
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": EVAL_PROMPT.format(
            claim_text=claim_text, evidence=json.dumps(evidence, ensure_ascii=False)
        )}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 500},
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result["message"]["content"], None
    except Exception as e:
        return None, str(e)


def evaluate_claim_local(llm_name, claim_text, evidence=None):
    """Evaluate a claim using local Ollama models via Tailscale.
    
    Falls back to cloud API if no local model mapping exists.
    """
    evidence = evidence or []
    mapping = OLLAMA_MODEL_MAP.get(llm_name)
    
    if not mapping:
        # No local model → try cloud API
        return evaluate_claim(llm_name, claim_text, evidence)
    
    t0 = time.time()
    raw, err = _call_ollama(claim_text, evidence, 
                            model=mapping["model"], host=mapping["host"])
    latency = (time.time() - t0) * 1000
    
    if err or not raw:
        # Fallback to cloud
        result = evaluate_claim(llm_name, claim_text, evidence)
        result.error = f"Ollama failed ({err}), fell back to cloud"
        return result
    
    parsed = _parse_llm_json(raw)
    if parsed:
        return LLMVerdict(
            llm_name=f"{llm_name}@ollama:{mapping['model']}",
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            cultural_note=parsed.get("cultural_note", "none"),
            raw_response=raw, latency_ms=latency
        )
    
    return LLMVerdict(
        llm_name=f"{llm_name}@ollama", confidence=0.5,
        reasoning=f"Parse failed: {raw[:100]}",
        cultural_note="none", raw_response=raw,
        latency_ms=latency, error="JSON parse failed"
    )


def evaluate_claim_hybrid(claim_text, evidence=None, llm_names=None):
    """Evaluate using best available: cloud API if key exists, else Ollama local.
    
    Priority: Cloud API > Ollama local > Stub
    """
    names = llm_names or list(LLM_REGISTRY.keys())
    results = {}
    for name in names:
        # Try cloud first
        reg = LLM_REGISTRY.get(name, {})
        key = os.environ.get(reg.get("key_env", ""), "")
        
        if key:
            results[name] = evaluate_claim(name, claim_text, evidence)
        elif name in OLLAMA_MODEL_MAP:
            results[name] = evaluate_claim_local(name, claim_text, evidence)
        else:
            results[name] = evaluate_claim(name, claim_text, evidence)  # stub
    
    return results


def check_ollama_status():
    """Check Ollama availability on all Tailscale hosts."""
    status = {}
    for host, url in OLLAMA_HOSTS.items():
        try:
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                status[host] = {"online": True, "models": models, "url": url}
        except Exception as e:
            status[host] = {"online": False, "error": str(e), "url": url}
    return status
