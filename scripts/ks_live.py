#!/usr/bin/env python3
"""
KS Live — Always-on Katala Samurai verification endpoint.

This script makes KS42c *actually run*, not just exist as importable code.

Three modes:
  1. CLI:    echo "claim text" | python3 ks_live.py
  2. Pipe:   python3 ks_live.py --pipe  (reads stdin line by line)
  3. Server: python3 ks_live.py --serve (HTTP JSON API on localhost:7842)

Design philosophy (Youta Hilono):
  "KSプログラムが常時稼働してない = Katalaをインストールしてるバイアスを
   かけて実質Katalaが機能してない = 設計思想と相反する"

This script exists to close that gap. If KS42c is built, it must run.

Usage from OpenClaw:
  exec: python3 /Users/nicolas/work/katala/scripts/ks_live.py "claim text"
  → returns JSON with verdict, confidence, axes, version

Dependencies: Only katala (src/) + ks_accel (Rust). No external API needed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Add katala src to path
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, _SRC)

# ── Constants ──
DEFAULT_PORT = 7842
VERSION = "KS-Live-1.0"
CONFIDENCE_WARN_THRESHOLD = 0.5
TIMEOUT_SECONDS = 30


def _get_ks():
    """Lazy-load KS42c (or fallback to KS42b, KS40b)."""
    for cls_path in [
        ("katala_samurai.ks42c", "KS42c"),
        ("katala_samurai.ks42b", "KS42b"),
        ("katala_samurai.ks40b", "KS40b"),
    ]:
        try:
            mod = __import__(cls_path[0], fromlist=[cls_path[1]])
            cls = getattr(mod, cls_path[1])
            return cls()
        except Exception:
            continue
    return None


def verify_claim(text: str, ks=None, fast: bool = False) -> dict:
    """Verify a single claim text. Returns structured result.

    Args:
        text: Claim text to verify.
        ks: Pre-loaded KS instance (optional, will lazy-load if None).
        fast: If True, skip LLM-dependent stages (no Ollama/Gemini calls).
              Uses KS31e-level verification (26 solvers + temporal) only.

    Returns:
        dict with keys: text, verdict, confidence, axes, version, time_ms, warnings
    """
    if not text or not text.strip():
        return {"text": "", "verdict": "EMPTY", "confidence": 0.0, "error": "empty input"}

    text = text.strip()
    start = time.time()

    if ks is None:
        ks = _get_ks()
    if ks is None:
        return {
            "text": text,
            "verdict": "KS_UNAVAILABLE",
            "confidence": 0.0,
            "error": "Could not load any KS module",
        }

    try:
        from katala_samurai.ks29 import Claim
        claim = Claim(text)

        if fast:
            # Fast path: L1 lightweight (S01-S27 only, ZERO network calls)
            # No semantic_bridge, no OpenAlex, no Gemini, no Ollama
            from katala_samurai.ks31e import KS31e
            ks_fast = KS31e()
            # verify_lightweight: runs 27 pure-logic solvers only
            l1_result = ks_fast.l1.verify_lightweight(
                text, evidence=[text]
            )
            # Add temporal context (pure Python, no LLM)
            try:
                from katala_samurai.temporal_context import temporal_score_for_ks31
                temporal = temporal_score_for_ks31(text)
            except Exception:
                temporal = {"temporal_freshness": 1.0, "temporal_risk": "unknown"}

            result = {
                "verdict": l1_result.get("verdict", "UNKNOWN"),
                "confidence": round(l1_result.get("pass_rate", 0.0), 3),
                "solvers_passed": l1_result.get("passed", 0),
                "solvers_total": l1_result.get("total", 0),
                "solver_results": l1_result.get("solver_results", {}),
                "temporal_freshness": temporal.get("temporal_freshness", 1.0),
                "temporal_risk": temporal.get("temporal_risk", "unknown"),
                "mode": "fast",
                "version": f"{getattr(ks, 'VERSION', '?')}:L1-fast",
            }
        else:
            # Full path: KS42c with all layers (may call LLM)
            # Set a short Ollama timeout to avoid hanging
            os.environ.setdefault("OLLAMA_TIMEOUT", "3")
            result = ks.verify(claim)
    except Exception as e:
        return {
            "text": text,
            "verdict": "ERROR",
            "confidence": 0.0,
            "error": str(e),
            "time_ms": round((time.time() - start) * 1000, 1),
        }

    elapsed_ms = round((time.time() - start) * 1000, 1)

    # Extract structured info from result
    if isinstance(result, dict):
        verdict = result.get("verdict", result.get("label", "UNKNOWN"))
        confidence = result.get("confidence", result.get("score", 0.0))
        version = result.get("version", getattr(ks, "VERSION", "?"))

        # Extract axes if available
        axes = {}
        for ax in ["r_struct", "r_context", "r_qualia", "r_cultural", "r_temporal"]:
            if ax in result:
                axes[ax] = round(result[ax], 3)

        # Semantic enrichment
        semantic = result.get("semantic_enrichment", {})
        acceleration = result.get("acceleration", {})

        warnings = []
        if confidence < CONFIDENCE_WARN_THRESHOLD:
            warnings.append(f"Low confidence ({confidence:.2f})")

        return {
            "text": text[:200],
            "verdict": str(verdict),
            "confidence": round(float(confidence), 3) if confidence else 0.0,
            "axes": axes,
            "version": version,
            "time_ms": elapsed_ms,
            "semantic": {
                "source": semantic.get("source", "none"),
                "propositions": semantic.get("prop_count", 0),
            } if semantic else {},
            "rust_functions": acceleration.get("rust_functions", 0) if acceleration else 0,
            "warnings": warnings,
        }
    else:
        return {
            "text": text[:200],
            "verdict": str(result),
            "confidence": 0.0,
            "version": getattr(ks, "VERSION", "?"),
            "time_ms": elapsed_ms,
        }


def verify_batch(texts: list[str], ks=None, fast: bool = False) -> list[dict]:
    """Verify multiple claims."""
    if ks is None:
        ks = _get_ks()
    return [verify_claim(t, ks=ks, fast=fast) for t in texts]


def serve(port: int = DEFAULT_PORT):
    """Start HTTP JSON API server."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    ks = _get_ks()
    print(f"KS Live Server starting on :{port} (version={getattr(ks, 'VERSION', '?')})")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {"text": body}

            fast = data.get("fast", False)
            if "texts" in data:
                result = verify_batch(data["texts"], ks=ks, fast=fast)
            else:
                result = verify_claim(data.get("text", ""), ks=ks, fast=fast)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

        def do_GET(self):
            status = {
                "status": "running",
                "version": getattr(ks, 'VERSION', '?'),
                "ks_live": VERSION,
            }
            if hasattr(ks, 'rust_status'):
                rs = ks.rust_status()
                status["rust_functions"] = rs.get("rust_function_count", 0)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())

        def log_message(self, format, *args):
            pass  # Suppress request logs

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Listening on http://127.0.0.1:{port}")
    print(f"  POST /  → {'{'}\"text\": \"...\"{'}'}  or  {'{'}\"texts\": [...]{'}'}")
    print(f"  GET  /  → status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


def main():
    parser = argparse.ArgumentParser(description="KS Live — Always-on verification")
    parser.add_argument("claim", nargs="?", help="Claim text to verify")
    parser.add_argument("--pipe", action="store_true", help="Read claims from stdin")
    parser.add_argument("--serve", action="store_true", help="Start HTTP server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--fast", action="store_true", help="Fast mode (no LLM, core solvers only)")
    args = parser.parse_args()

    if args.serve:
        serve(args.port)
        return

    if args.pipe:
        ks = _get_ks()
        for line in sys.stdin:
            line = line.strip()
            if line:
                r = verify_claim(line, ks=ks, fast=args.fast)
                print(json.dumps(r, ensure_ascii=False))
        return

    if args.claim:
        text = args.claim
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        parser.print_help()
        return

    r = verify_claim(text, fast=args.fast)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        # Human-readable output
        v = r.get("verdict", "?")
        c = r.get("confidence", 0)
        t = r.get("time_ms", 0)
        ver = r.get("version", "?")
        print(f"[{ver}] {v} (confidence={c:.3f}) in {t:.0f}ms")
        if r.get("axes"):
            axes_str = " ".join(f"{k}={v:.2f}" for k, v in r["axes"].items())
            print(f"  Axes: {axes_str}")
        for w in r.get("warnings", []):
            print(f"  ⚠️  {w}")


if __name__ == "__main__":
    main()
