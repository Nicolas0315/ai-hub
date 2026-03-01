"""
KS Inline Filter — Real-time LLM output → KS40b verification pipeline.

Design: Shirokuma + Youta Hilono, 2026-03-01
Implements option B: inline verification of LLM output.

Architecture:
  LLM (Ollama) → sentence splitter → KS40b.verify() per sentence
  → aggregate confidence → filtered output with per-sentence annotations

Usage:
  filter = KSInlineFilter(ollama_url="http://localhost:11434")
  result = filter.generate_and_verify("your prompt here", model="qwen3:8b")
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Lazy imports for KS40b to avoid import chain issues at module level
_ks_instance = None


def _get_ks():
    global _ks_instance
    if _ks_instance is None:
        from katala_samurai.ks40b import KS40b
        _ks_instance = KS40b()
    return _ks_instance


@dataclass
class SentenceVerdict:
    text: str
    confidence: float
    status: str | None
    ks_time_ms: float
    htlf_loss: dict | None = None


@dataclass
class FilteredOutput:
    prompt: str
    model: str
    raw_response: str
    sentences: list[SentenceVerdict] = field(default_factory=list)
    llm_time_s: float = 0.0
    ks_time_s: float = 0.0
    total_time_s: float = 0.0
    llm_tok_per_s: float = 0.0
    avg_confidence: float = 0.0
    min_confidence: float = 0.0
    flagged_count: int = 0

    @property
    def filtered_response(self) -> str:
        """Return response with low-confidence sentences marked."""
        parts = []
        for s in self.sentences:
            if s.confidence < 0.3:
                parts.append(f"⚠️[conf={s.confidence:.2f}] {s.text}")
            else:
                parts.append(s.text)
        return " ".join(parts)

    def summary(self) -> str:
        lines = [
            f"Model: {self.model}",
            f"LLM: {self.llm_tok_per_s:.0f} tok/s, {self.llm_time_s:.1f}s",
            f"KS:  {self.ks_time_s:.1f}s ({len(self.sentences)} sentences)",
            f"Total: {self.total_time_s:.1f}s",
            f"Confidence: avg={self.avg_confidence:.3f}, min={self.min_confidence:.3f}",
            f"Flagged: {self.flagged_count}/{len(self.sentences)}",
            "",
            "=== Filtered Output ===",
            self.filtered_response,
        ]
        return "\n".join(lines)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences (Japanese + English aware)."""
    # Japanese sentence endings + English
    parts = re.split(r'(?<=[。．！？\.\!\?])\s*', text)
    # Filter empties and merge very short fragments
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if result and len(p) < 10 and not re.search(r'[。．！？\.\!\?]$', p):
            result[-1] += p
        else:
            result.append(p)
    return result if result else [text]


class KSInlineFilter:
    """
    LLM → KS40b inline verification filter.

    Generates text via Ollama, splits into sentences,
    verifies each with KS40b, returns annotated output.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 confidence_threshold: float = 0.3):
        self.ollama_url = ollama_url
        self.threshold = confidence_threshold

    def _ollama_generate(self, prompt: str, model: str = "qwen3:8b") -> dict:
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
        return resp

    def generate_and_verify(self, prompt: str, model: str = "qwen3:8b") -> FilteredOutput:
        t_start = time.time()

        # Step 1: LLM generation
        t0 = time.time()
        resp = self._ollama_generate(prompt, model)
        llm_time = time.time() - t0

        raw = resp.get("response", "")
        eval_count = resp.get("eval_count", 0)
        eval_dur = resp.get("eval_duration", 1)
        tok_per_s = eval_count / (eval_dur / 1e9) if eval_dur > 0 else 0

        # Step 2: Split into sentences
        sentences = split_sentences(raw)

        # Step 3: KS40b verify each sentence
        ks = _get_ks()
        verdicts = []
        t_ks_start = time.time()

        for sent in sentences:
            if len(sent.strip()) < 5:  # Skip tiny fragments
                verdicts.append(SentenceVerdict(
                    text=sent, confidence=1.0, status="SKIP", ks_time_ms=0
                ))
                continue

            t1 = time.time()
            try:
                result = ks.verify(sent)
                conf = result.get("confidence", 0.5) if isinstance(result, dict) else getattr(result, "confidence", 0.5)
                status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
                htlf = result.get("htlf_loss") if isinstance(result, dict) else None
            except Exception as e:
                conf = 0.0
                status = f"ERROR: {e}"
                htlf = None

            verdicts.append(SentenceVerdict(
                text=sent,
                confidence=conf,
                status=status,
                ks_time_ms=(time.time() - t1) * 1000,
                htlf_loss=htlf,
            ))

        ks_time = time.time() - t_ks_start
        total_time = time.time() - t_start

        # Aggregate
        confs = [v.confidence for v in verdicts if v.status != "SKIP"]
        avg_conf = sum(confs) / len(confs) if confs else 0
        min_conf = min(confs) if confs else 0
        flagged = sum(1 for c in confs if c < self.threshold)

        return FilteredOutput(
            prompt=prompt,
            model=model,
            raw_response=raw,
            sentences=verdicts,
            llm_time_s=llm_time,
            ks_time_s=ks_time,
            total_time_s=total_time,
            llm_tok_per_s=tok_per_s,
            avg_confidence=avg_conf,
            min_confidence=min_conf,
            flagged_count=flagged,
        )

    def verify_only(self, text: str) -> FilteredOutput:
        """Verify pre-existing text without LLM generation."""
        t_start = time.time()
        sentences = split_sentences(text)
        ks = _get_ks()
        verdicts = []

        for sent in sentences:
            if len(sent.strip()) < 5:
                verdicts.append(SentenceVerdict(text=sent, confidence=1.0, status="SKIP", ks_time_ms=0))
                continue
            t1 = time.time()
            try:
                result = ks.verify(sent)
                conf = result.get("confidence", 0.5) if isinstance(result, dict) else getattr(result, "confidence", 0.5)
                status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
            except Exception:
                conf = 0.0
                status = "ERROR"
            verdicts.append(SentenceVerdict(text=sent, confidence=conf, status=status, ks_time_ms=(time.time()-t1)*1000))

        confs = [v.confidence for v in verdicts if v.status != "SKIP"]
        return FilteredOutput(
            prompt="(verify_only)",
            model="none",
            raw_response=text,
            sentences=verdicts,
            ks_time_s=time.time() - t_start,
            total_time_s=time.time() - t_start,
            avg_confidence=sum(confs)/len(confs) if confs else 0,
            min_confidence=min(confs) if confs else 0,
            flagged_count=sum(1 for c in confs if c < 0.3),
        )


if __name__ == "__main__":
    f = KSInlineFilter()
    result = f.generate_and_verify(
        "日本の歴史について3つの事実を述べてください。/no_think",
        model="qwen3:8b"
    )
    print(result.summary())
    print("\n=== Per-sentence detail ===")
    for i, s in enumerate(result.sentences):
        flag = "⚠️" if s.confidence < 0.3 else "✅"
        print(f"  {flag} [{s.confidence:.3f}] ({s.ks_time_ms:.0f}ms) {s.text[:80]}")
