"""
Katala_Samurai_31_a (KS31a) — Cyclic Three-Layer Verification System

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Architecture:
  Three layers in a cyclic, mutually complementary relationship.
  Layer 1 (S01-S28) is the axis — every cycle passes through it.
  Layer 3 (Chain Decomposer) is consulted at each transition.

  ┌──────────────────────────────────┐
  │                                  │
  ▼                                  │
  L1 (S01-S28) ──▶ L3 (Chain) ──▶ L2 (A-solvers)
  ▲                                  │
  │                                  │
  └──────────────────────────────────┘

Flow:
  Round 1: claim → L1 direct verification
    → if VERIFIED (high confidence): done
    → if UNVERIFIED/low: proceed to Round 2

  Round 2: L1 result → L3 decomposition
    → split into steps, detect gaps, identify failure points
    → each step → L2 structural analysis
    → each step+analysis → L1 individual verification

  Round 3: L1 step results → L3 synthesis
    → compose step verdicts into final judgment
    → detect which steps failed, where gaps exist

Principles:
  - L1 is always the axis: first and last verification passes through S01-S28
  - L3 is always consulted: every transition between layers goes via Chain Decomposer
  - No cross-run accumulation: StageStore records what happened, not what to believe
  - Max 2 cycles (bounded rationality)
"""

import os
import sys
import time
import hashlib

try:
    from .ks30d import KS30d, Claim
    from .analogy_solvers import run_analogy_solvers, a06_chain_decompose
    from .stage_store import StageStore
except ImportError:
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from ks30d import KS30d, Claim
    from analogy_solvers import run_analogy_solvers, a06_chain_decompose
    from stage_store import StageStore


# ─── Layer Definitions ──────────────────────────────────────────────────────

class Layer1:
    """S01-S28 verification engine. The axis of KS31a."""

    def __init__(self):
        self._ks = KS30d()

    def verify_full(self, claim, store=None):
        """Full KS30d verification (all 28 solvers + C-1 through C-4 + D-1)."""
        return self._ks.verify(claim, store=store)

    def verify_lightweight(self, claim_text, evidence=None):
        """Lightweight verification: S01-S27 only, no D-1/C-1/papers.
        Used for individual step verification in cyclic rounds."""
        claim = Claim(
            text=claim_text,
            evidence=evidence or [claim_text],
            source_llm=None,
            training_data_hash=hashlib.sha256(claim_text.encode()).hexdigest(),
        )
        results = {}
        for name, fn in self._ks.solvers:
            try:
                results[name] = bool(fn(claim))
            except Exception:
                results[name] = False

        passed = sum(results.values())
        total = len(results)
        pass_rate = passed / max(total, 1)

        return {
            "text": claim_text,
            "passed": passed,
            "total": total,
            "pass_rate": round(pass_rate, 4),
            "verdict": "PASS" if pass_rate >= 0.75 else "FAIL",
            "solver_results": results,
        }


class Layer2:
    """A-solvers (A01-A05): recognition structure analysis."""

    def analyze(self, text, focus_words=None, store=None):
        """Run A01-A05 on text. Returns structural analysis."""
        return run_analogy_solvers(text, focus_words=focus_words, store=store)


class Layer3:
    """Chain Decomposer: reasoning chain management."""

    def decompose(self, text):
        """Decompose text into reasoning steps."""
        return a06_chain_decompose(text)

    def synthesize(self, step_results, chain_info):
        """Synthesize step-level verdicts into a final judgment."""
        if not step_results:
            return {
                "composite_verdict": "UNVERIFIED",
                "reason": "no steps to verify",
                "step_count": 0, "passed_count": 0,
                "failed_steps": [], "gap_steps": [], "weakest_step": None,
            }

        passed_steps = [s for s in step_results if s["verdict"] == "PASS"]
        failed_steps = [s for s in step_results if s["verdict"] == "FAIL"]

        gap_indices = set()
        for step in chain_info.get("steps", []):
            if step.get("implicit_gap_flag"):
                gap_indices.add(step["index"])

        gap_steps = [s for i, s in enumerate(step_results) if i in gap_indices]
        weakest = min(step_results, key=lambda s: s["pass_rate"])

        all_pass = len(failed_steps) == 0
        has_gaps = len(gap_steps) > 0

        if all_pass and not has_gaps:
            composite = "VERIFIED"
            reason = f"all {len(step_results)} steps verified"
        elif all_pass and has_gaps:
            composite = "PARTIALLY_VERIFIED"
            reason = f"all steps pass but {len(gap_steps)} implicit gap(s) detected"
        else:
            composite = "UNVERIFIED"
            failed_indices = [i for i, s in enumerate(step_results) if s["verdict"] == "FAIL"]
            reason = f"{len(failed_steps)}/{len(step_results)} steps failed at indices {failed_indices}"

        return {
            "composite_verdict": composite,
            "reason": reason,
            "step_count": len(step_results),
            "passed_count": len(passed_steps),
            "failed_steps": [{"index": i, "text": s["text"][:80], "pass_rate": s["pass_rate"]}
                             for i, s in enumerate(step_results) if s["verdict"] == "FAIL"],
            "gap_steps": [{"index": i, "text": s["text"][:80]}
                          for i, s in enumerate(step_results) if i in gap_indices],
            "weakest_step": {"text": weakest["text"][:80], "pass_rate": weakest["pass_rate"]},
        }


# ─── KS31a Orchestrator ────────────────────────────────────────────────────

class KS31a:
    """Katala_Samurai_31_a: Cyclic Three-Layer Verification System.

    L1 (S01-S28) is the axis.
    L3 (Chain Decomposer) is consulted at every transition.
    L2 (A-solvers) provides structural analysis.
    Max 2 cycles (bounded rationality).
    """

    VERSION = "KS31a"

    def __init__(self):
        self.l1 = Layer1()
        self.l2 = Layer2()
        self.l3 = Layer3()

    def verify(self, claim, store=None):
        """Run cyclic 3-layer verification."""
        t0 = time.time()
        trace = []

        # ── Round 1: L1 direct verification ──────────────────────────
        r1 = self.l1.verify_full(claim, store=store)
        trace.append({"round": 1, "layer": "L1", "action": "full_verify",
                       "verdict": r1["verdict"], "score": r1["final_score"]})

        if store:
            store.write("KS31a_R1_L1", {
                "verdict": r1["verdict"], "score": r1["final_score"],
                "solvers_passed": r1["solvers_passed"],
            })

        # If L1 gives high confidence VERIFIED, accept
        if r1["verdict"] == "VERIFIED" and r1["final_score"] >= 0.90:
            elapsed = time.time() - t0
            return self._build_output(
                verdict=r1["verdict"], final_score=r1["final_score"],
                r1_result=r1, trace=trace, elapsed=elapsed,
                store=store, cycle_count=1,
            )

        # ── Round 2: L3 decomposition ────────────────────────────────
        chain = self.l3.decompose(claim.text)
        trace.append({"round": 2, "layer": "L3", "action": "decompose",
                       "chain_length": chain["chain_length"],
                       "has_gaps": chain["has_implicit_gaps"]})

        if store:
            store.write("KS31a_R2_L3", chain)

        # If single step, no decomposition possible
        if chain["chain_length"] <= 1:
            elapsed = time.time() - t0
            return self._build_output(
                verdict=r1["verdict"], final_score=r1["final_score"],
                r1_result=r1, trace=trace, elapsed=elapsed,
                store=store, cycle_count=1, note="single_step_no_decomposition",
            )

        # ── Round 3: L2 analysis + L1 per-step verification ─────────
        step_results = []
        step_analyses = []

        for step in chain["steps"]:
            analysis = self.l2.analyze(step["text"])
            step_analyses.append(analysis)

            step_verdict = self.l1.verify_lightweight(
                step["text"], evidence=claim.evidence,
            )
            step_results.append(step_verdict)

            trace.append({
                "round": 3, "layer": "L2+L1", "action": "step_verify",
                "step_index": step["index"],
                "step_text": step["text"][:60],
                "step_verdict": step_verdict["verdict"],
                "step_pass_rate": step_verdict["pass_rate"],
                "a_candidates": analysis["candidates_generated"],
            })

        if store:
            store.write("KS31a_R3_steps", {
                "count": len(step_results),
                "results": [{"text": s["text"][:80], "verdict": s["verdict"],
                              "pass_rate": s["pass_rate"]} for s in step_results],
            })

        # ── Round 4: L3 synthesis ────────────────────────────────────
        synthesis = self.l3.synthesize(step_results, chain)
        trace.append({"round": 4, "layer": "L3", "action": "synthesize",
                       "composite_verdict": synthesis["composite_verdict"],
                       "reason": synthesis["reason"]})

        if store:
            store.write("KS31a_R4_synthesis", synthesis)

        # ── Final verdict: combine R1 and R4 ─────────────────────────
        final_verdict, final_score = self._combine_verdicts(r1, synthesis)

        elapsed = time.time() - t0
        return self._build_output(
            verdict=final_verdict, final_score=final_score,
            r1_result=r1, synthesis=synthesis, trace=trace,
            elapsed=elapsed, store=store, cycle_count=2,
        )

    def _combine_verdicts(self, r1_result, synthesis):
        """Combine direct (R1) and compositional (R4) verdicts."""
        r1_score = r1_result["final_score"]
        comp = synthesis["composite_verdict"]

        if comp == "VERIFIED":
            return "VERIFIED", min(r1_score * 1.05, 1.0)
        elif comp == "PARTIALLY_VERIFIED":
            return "PARTIALLY_VERIFIED", round(r1_score * 0.9, 4)
        else:  # UNVERIFIED
            if r1_result["verdict"] == "VERIFIED":
                return "PARTIALLY_VERIFIED", round(r1_score * 0.7, 4)
            else:
                weakest_rate = synthesis["weakest_step"]["pass_rate"] if synthesis["weakest_step"] else 0
                return "UNVERIFIED", round(max(r1_score, weakest_rate), 4)

    def _build_output(self, verdict, final_score, r1_result, trace, elapsed,
                      store=None, cycle_count=1, synthesis=None, note=None):
        """Build final output dict."""
        output = {
            "version": self.VERSION,
            "verdict": verdict,
            "final_score": round(final_score, 4),
            "cycle_count": cycle_count,
            "r1_verdict": r1_result["verdict"],
            "r1_score": r1_result["final_score"],
            "solvers_passed": r1_result["solvers_passed"],
            "elapsed_sec": round(elapsed, 3),
            "trace": trace,
        }

        if synthesis:
            output["synthesis"] = {
                "composite_verdict": synthesis["composite_verdict"],
                "reason": synthesis["reason"],
                "step_count": synthesis["step_count"],
                "passed_count": synthesis["passed_count"],
                "failed_steps": synthesis["failed_steps"],
                "gap_steps": synthesis["gap_steps"],
                "weakest_step": synthesis["weakest_step"],
            }

        if note:
            output["note"] = note

        if store:
            store.write("KS31a_final", output)
            store.finalize()

        return output


# ─── Test ───────────────────────────────────────────────────────────────────

def run_tests():
    import tempfile

    ks = KS31a()

    tests = [
        ("Single claim (1-cycle)",
         Claim(
             "Water boils at 100 degrees Celsius at standard pressure",
             evidence=["Physics textbook", "Thermodynamics"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"physics").hexdigest(),
         )),
        ("Multi-step syllogism (2-cycle)",
         Claim(
             "All mammals are warm-blooded. Whales are mammals. Therefore whales are warm-blooded.",
             evidence=["Biology", "Zoology classification"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"biology").hexdigest(),
         )),
        ("Transitive chain (4 steps)",
         Claim(
             "Iron is denser than aluminum. Aluminum is denser than wood. Wood is denser than paper. Therefore iron is denser than paper.",
             evidence=["Material science", "Density tables"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"density").hexdigest(),
         )),
        ("Implicit gap",
         Claim(
             "The economy is growing rapidly. Therefore unemployment will decrease significantly.",
             evidence=["Economic theory"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"economics").hexdigest(),
         )),
        ("No evidence (gate)",
         Claim(
             "Unverifiable claim with no evidence.",
             evidence=[],
             source_llm=None,
             training_data_hash=None,
         )),
    ]

    print("=" * 70)
    print(f"KS31a — Cyclic Three-Layer Verification")
    print("=" * 70)

    for label, claim in tests:
        with tempfile.TemporaryDirectory() as d:
            store = StageStore("ks31a_test", base_dir=d)
            result = ks.verify(claim, store=store)

            v = "V" if "VERIFIED" in result["verdict"] else "X"
            print(f"\n[{label}]")
            print(f"  Claim: {claim.text[:65]}...")
            print(f"  [{v}] {result['verdict']} | Score: {result['final_score']}")
            print(f"  Cycles: {result['cycle_count']} | Time: {result['elapsed_sec']}s")

            if result.get("synthesis"):
                s = result["synthesis"]
                print(f"  Synthesis: {s['composite_verdict']} ({s['reason']})")
                for fs in s.get("failed_steps", []):
                    print(f"    FAIL Step {fs['index']}: {fs['text'][:50]}... (rate={fs['pass_rate']})")
                for gs in s.get("gap_steps", []):
                    print(f"    GAP  Step {gs['index']}: {gs['text'][:50]}...")
                if s.get("weakest_step"):
                    print(f"    Weakest: {s['weakest_step']['text'][:50]}... (rate={s['weakest_step']['pass_rate']})")

            if result.get("note"):
                print(f"  Note: {result['note']}")

            stages = store.list_stages()
            print(f"  Stages: {len(stages)}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_tests()
