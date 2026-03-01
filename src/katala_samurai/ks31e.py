"""
Katala_Samurai_31_d (KS31e) — Semantic-Augmented Cyclic Verification System

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Upgrade from KS31b:
  KS31b: L1-L4, content-blind (Issue #64), form-only verification
  KS31e: L1-L5, semantic bridge + causal graph + full evidence integration

Architecture (5 Layers):
  L1 (S01-S28)         — Formal verification axis (deterministic, non-LLM)
  L2 (A01-A05)         — Structural analysis (non-LLM)
  L3 (A06 Chain)       — Reasoning decomposition + causal graph
  L4 (M1+M2)           — Meta-verification (counter-factual + multi-source evidence)
  L5 (Semantic Bridge)  — LLM content understanding → formal proposition extraction
                          [NEW] Solves Issue #64: content-blindness

  ┌──────────────────────────────────────────────┐
  │                                              │
  ▼                                              │
  L5 (Semantic) ──▶ L1 (S01-S28) ──▶ L3 (Chain) ──▶ L2 (A-solvers)
                     ▲                              │
                     │                              │
                     └──────────────────────────────┘
                     │
                     ▼
                    L4 (Meta: M1+M2+Multi-Source)

Key principle:
  LLM is used for UNDERSTANDING (L5), never for JUDGING.
  All verdicts pass through S01-S28 (deterministic).
  L5 enriches what L1 sees, not what L1 decides.

Flow:
  Round 0: claim → L5 semantic extraction → propositions + causal links
  Round 1: claim + propositions → L1 direct verification
  Round 2: L1 result → L3 decomposition (with causal graph from L5)
  Round 3: each step → L2 analysis + L1 step verification
  Round 4: L3 synthesis (causal-aware)
  Round 5: L4 meta-verification (M1 counter-factual + M2 multi-source)
  Round 6: L5 enrichment delta (did semantic understanding change the verdict?)

Verdicts: VERIFIED / EXPLORING / PARTIALLY_VERIFIED / UNVERIFIED
Meta-verdicts: SUBSTANTIVE / FORM_ONLY / UNSUPPORTED / CONTESTED / HOLLOW
Semantic flags: CONTENT_AWARE / CONTENT_BLIND / DEGRADED_MODE
Causal flags: CAUSAL_VALID / CAUSAL_PARTIAL / CAUSAL_WEAK / NON_CAUSAL
"""

import os
import sys
import time
import hashlib

try:
    from .ks30d import KS30d, Claim
    from .analogy_solvers import run_analogy_solvers, a06_chain_decompose
    from .meta_verifier import run_meta_verification
    from .domain_bridge import bridge_domain
    from .analogical_transfer import run_analogical_transfer
    from .semantic_bridge import extract_semantics, analyze_causality, semantic_enrichment_delta
    from .stage_store import StageStore
except ImportError:
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from ks30d import KS30d, Claim
    from analogy_solvers import run_analogy_solvers, a06_chain_decompose
    from meta_verifier import run_meta_verification
    try:
        from .domain_bridge import bridge_domain
        from .analogical_transfer import run_analogical_transfer
    except ImportError:
        from domain_bridge import bridge_domain
        from analogical_transfer import run_analogical_transfer
    from semantic_bridge import extract_semantics, analyze_causality, semantic_enrichment_delta
    from stage_store import StageStore
try:
    from .temporal_context import temporal_score_for_ks31, verify_temporal_context
except ImportError:
    from temporal_context import temporal_score_for_ks31, verify_temporal_context


# ─── Layer Definitions ──────────────────────────────────────────────────────

class Layer1:
    """S01-S28 verification engine. The axis of KS31e."""

    def __init__(self):
        self._ks = KS30d()

    def verify_full(self, claim, store=None):
        """Full KS30d verification (all 28 solvers + C-1 through C-4 + D-1)."""
        return self._ks.verify(claim, store=store)

    def verify_lightweight(self, claim_text, evidence=None):
        """Lightweight verification: S01-S27 only, no D-1/C-1/papers."""
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
        return run_analogy_solvers(text, focus_words=focus_words, store=store)


class Layer3:
    """Chain Decomposer: reasoning chain + causal graph management."""

    def decompose(self, text):
        return a06_chain_decompose(text)

    def decompose_with_causality(self, text, causal_info):
        """Enhanced decomposition: merge chain steps with causal graph from L5."""
        chain = a06_chain_decompose(text)

        # Annotate steps with causal metadata from L5
        causal_chain = causal_info.get("causal_chain", [])
        missing_links = causal_info.get("missing_links", [])
        confounders = causal_info.get("confounders", [])

        for step in chain.get("steps", []):
            step_lower = step["text"].lower()
            # Match causal links to steps
            step["causal_links"] = []
            for link in causal_chain:
                if (link.get("from", "").lower() in step_lower or
                        link.get("to", "").lower() in step_lower):
                    step["causal_links"].append(link)
            # Flag steps that overlap with missing links
            step["has_missing_link"] = any(
                ml.lower() in step_lower for ml in missing_links
            )
            # Flag potential confounders
            step["confounders"] = [
                c for c in confounders if c.lower() in step_lower
            ]

        chain["causal_analysis"] = {
            "causal_chain_length": len(causal_chain),
            "missing_links": missing_links,
            "confounders": confounders,
            "overall_validity": causal_info.get("overall_causal_validity", "unknown"),
        }

        return chain

    def synthesize(self, step_results, chain_info):
        """Synthesize step-level verdicts into final judgment (causal-aware)."""
        if not step_results:
            return {
                "composite_verdict": "UNVERIFIED",
                "reason": "no steps to verify",
                "step_count": 0, "passed_count": 0,
                "failed_steps": [], "gap_steps": [], "weakest_step": None,
                "causal_assessment": None,
            }

        passed_steps = [s for s in step_results if s["verdict"] == "PASS"]
        failed_steps = [s for s in step_results if s["verdict"] == "FAIL"]

        gap_indices = set()
        causal_gap_indices = set()
        for i, step in enumerate(chain_info.get("steps", [])):
            if step.get("implicit_gap_flag"):
                gap_indices.add(i)
            if step.get("has_missing_link"):
                causal_gap_indices.add(i)

        gap_steps = [s for i, s in enumerate(step_results) if i in gap_indices]
        weakest = min(step_results, key=lambda s: s["pass_rate"])

        all_pass = len(failed_steps) == 0
        has_gaps = len(gap_steps) > 0
        has_causal_gaps = len(causal_gap_indices) > 0

        pass_rates = [s["pass_rate"] for s in step_results]
        rate_variance = max(pass_rates) - min(pass_rates) if pass_rates else 0
        avg_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0
        has_borderline = any(0.70 <= r <= 0.80 for r in pass_rates)

        # Causal assessment from L5
        causal_analysis = chain_info.get("causal_analysis", {})
        causal_validity = causal_analysis.get("overall_validity", "unknown")

        if all_pass and not has_gaps and not has_causal_gaps and avg_rate >= 0.85:
            composite = "VERIFIED"
            reason = f"all {len(step_results)} steps verified"
        elif all_pass and has_causal_gaps:
            composite = "EXPLORING"
            reason = f"all steps pass but {len(causal_gap_indices)} causal gap(s) detected by L5"
        elif all_pass and not has_gaps and avg_rate < 0.85:
            composite = "EXPLORING"
            reason = f"all steps pass but average rate {avg_rate:.2f} suggests deeper analysis needed"
        elif all_pass and has_gaps:
            composite = "EXPLORING"
            reason = f"all steps pass but {len(gap_steps)} implicit gap(s) — exploring missing links"
        elif has_borderline or rate_variance >= 0.15:
            composite = "EXPLORING"
            borderline_indices = [i for i, r in enumerate(pass_rates) if 0.70 <= r <= 0.80]
            reason = f"mixed signals: borderline steps at {borderline_indices}, variance={rate_variance:.2f}"
        else:
            composite = "UNVERIFIED"
            failed_indices = [i for i, s in enumerate(step_results) if s["verdict"] == "FAIL"]
            reason = f"{len(failed_steps)}/{len(step_results)} steps failed at indices {failed_indices}"

        # Causal downgrade: if causal structure is weak/unfounded, can't trust VERIFIED
        if composite == "VERIFIED" and causal_validity in ("weak", "unfounded"):
            composite = "EXPLORING"
            reason += f" | causal validity={causal_validity}, downgraded"

        return {
            "composite_verdict": composite,
            "reason": reason,
            "step_count": len(step_results),
            "passed_count": len(passed_steps),
            "failed_steps": [{"index": i, "text": s["text"][:80], "pass_rate": s["pass_rate"]}
                             for i, s in enumerate(step_results) if s["verdict"] == "FAIL"],
            "gap_steps": [{"index": i, "text": s["text"][:80]}
                          for i, s in enumerate(step_results) if i in gap_indices],
            "causal_gap_steps": [{"index": i} for i in sorted(causal_gap_indices)],
            "weakest_step": {"text": weakest["text"][:80], "pass_rate": weakest["pass_rate"]},
            "causal_assessment": {
                "validity": causal_validity,
                "missing_links": causal_analysis.get("missing_links", []),
                "confounders": causal_analysis.get("confounders", []),
            },
        }


class Layer5:
    """Semantic Bridge: LLM-powered content understanding.
    
    Extracts meaning → converts to formal propositions → feeds to L1.
    LLM understands, S01-S28 judges. Never the reverse.
    """

    def extract(self, claim_text, evidence=None):
        """Extract structured semantics from claim."""
        return extract_semantics(claim_text, evidence)

    def analyze_causality(self, claim_text):
        """Extract causal graph from claim."""
        return analyze_causality(claim_text)

    def measure_enrichment(self, original_l1, enriched_l1_list):
        """Measure whether semantic enrichment changed L1 verification."""
        return semantic_enrichment_delta(original_l1, enriched_l1_list)


# ─── KS31e Orchestrator ────────────────────────────────────────────────────

class KS31e:
    """Katala_Samurai_31_d: Semantic-Augmented Cyclic Verification System.

    L1 (S01-S28) is the axis.
    L3 (Chain Decomposer) is consulted at every transition.
    L2 (A-solvers) provides structural analysis.
    L4 (Meta) verifies the verification.
    L5 (Semantic Bridge) provides content understanding.
    Max 2 cycles (bounded rationality).
    """

    VERSION = "KS31e"

    def __init__(self):
        self.l1 = Layer1()
        self.l2 = Layer2()
        self.l3 = Layer3()
        self.l5 = Layer5()

    def verify(self, claim, store=None, skip_s28=True):
        """Run semantic-augmented cyclic verification."""
        t0 = time.time()
        trace = []

        # ── Round 0: L5 Semantic Extraction ──────────────────────────
        semantics = self.l5.extract(claim.text, evidence=claim.evidence)
        causal = self.l5.analyze_causality(claim.text)
        trace.append({
            "round": 0, "layer": "L5", "action": "semantic_extraction",
            "mode": semantics["mode"],
            "propositions": len(semantics["propositions"]),
            "causal_links": len(causal.get("causal_chain", [])),
            "causal_validity": causal.get("overall_causal_validity", "unknown"),
        })

        if store:
            store.write("KS31e_R0_L5_semantics", semantics)
            store.write("KS31e_R0_L5_causal", causal)

        # ── Round 0b: Temporal Context Verification ──────────────────
        temporal = temporal_score_for_ks31(
            claim.text,
            source_llm=claim.source_llm,
            evidence=claim.evidence,
        )
        trace.append({
            "round": "0b", "layer": "L5_temporal", "action": "temporal_context",
            "freshness": temporal["temporal_freshness"],
            "risk": temporal["temporal_risk"],
            "domain": temporal["temporal_domain"],
            "knowledge_year": temporal.get("knowledge_year"),
        })

        if store:
            store.write("KS31e_R0b_temporal", temporal)

        # ── Round 1: L1 direct verification ──────────────────────────
        r1 = self.l1.verify_full(claim, store=store)
        trace.append({"round": 1, "layer": "L1", "action": "full_verify",
                       "verdict": r1["verdict"], "score": r1["final_score"]})

        if store:
            store.write("KS31e_R1_L1", {
                "verdict": r1["verdict"], "score": r1["final_score"],
                "solvers_passed": r1["solvers_passed"],
            })

        # ── Round 1b: L1 verify each L5 proposition ─────────────────
        proposition_results = []
        for prop in semantics["propositions"]:
            pr = self.l1.verify_lightweight(prop["text"], evidence=claim.evidence)
            pr["proposition_type"] = prop.get("type", "unknown")
            proposition_results.append(pr)

        enrichment = self.l5.measure_enrichment(
            {"pass_rate": r1["final_score"]}, proposition_results,
        )
        trace.append({
            "round": "1b", "layer": "L5+L1", "action": "proposition_verify",
            "proposition_count": len(proposition_results),
            "semantic_impact": enrichment["semantic_impact"],
            "delta": enrichment["delta"],
        })

        if store:
            store.write("KS31e_R1b_propositions", {
                "results": [{"text": p["text"][:80], "verdict": p["verdict"],
                              "pass_rate": p["pass_rate"], "type": p.get("proposition_type")}
                             for p in proposition_results],
                "enrichment": enrichment,
            })

        # If L1 gives high confidence VERIFIED AND semantic enrichment confirms
        if (r1["verdict"] == "VERIFIED" and r1["final_score"] >= 0.90
                and enrichment["semantic_impact"] != "HIGH"):
            elapsed = time.time() - t0
            return self._build_output(
                verdict=r1["verdict"], final_score=r1["final_score"],
                r1_result=r1, trace=trace, elapsed=elapsed,
                store=store, cycle_count=1,
                semantics=semantics, causal=causal, enrichment=enrichment,
                temporal=temporal,
            )

        # ── Round 2: L3 causal-aware decomposition ──────────────────
        chain = self.l3.decompose_with_causality(claim.text, causal)
        trace.append({"round": 2, "layer": "L3", "action": "causal_decompose",
                       "chain_length": chain["chain_length"],
                       "has_gaps": chain["has_implicit_gaps"],
                       "causal_validity": causal.get("overall_causal_validity", "unknown")})

        if store:
            store.write("KS31e_R2_L3", chain)

        if chain["chain_length"] <= 1:
            elapsed = time.time() - t0
            return self._build_output(
                verdict=r1["verdict"], final_score=r1["final_score"],
                r1_result=r1, trace=trace, elapsed=elapsed,
                store=store, cycle_count=1, note="single_step_no_decomposition",
                semantics=semantics, causal=causal, enrichment=enrichment,
                temporal=temporal,
            )

        # ── Round 3: L2 analysis + L1 per-step verification ─────────
        step_results = []
        for step in chain["steps"]:
            analysis = self.l2.analyze(step["text"])
            step_verdict = self.l1.verify_lightweight(
                step["text"], evidence=claim.evidence,
            )
            # Annotate with causal metadata
            step_verdict["causal_links"] = step.get("causal_links", [])
            step_verdict["has_missing_link"] = step.get("has_missing_link", False)
            step_results.append(step_verdict)

            trace.append({
                "round": 3, "layer": "L2+L1", "action": "step_verify",
                "step_index": step["index"],
                "step_text": step["text"][:60],
                "step_verdict": step_verdict["verdict"],
                "step_pass_rate": step_verdict["pass_rate"],
                "causal_links": len(step_verdict["causal_links"]),
                "has_missing_link": step_verdict["has_missing_link"],
            })

        if store:
            store.write("KS31e_R3_steps", {
                "count": len(step_results),
                "results": [{"text": s["text"][:80], "verdict": s["verdict"],
                              "pass_rate": s["pass_rate"],
                              "causal_links": len(s.get("causal_links", [])),
                              "has_missing_link": s.get("has_missing_link")}
                             for s in step_results],
            })

        # ── Round 4: L3 causal-aware synthesis ───────────────────────
        synthesis = self.l3.synthesize(step_results, chain)
        trace.append({"round": 4, "layer": "L3", "action": "causal_synthesize",
                       "composite_verdict": synthesis["composite_verdict"],
                       "reason": synthesis["reason"],
                       "causal_validity": synthesis["causal_assessment"]["validity"]
                       if synthesis.get("causal_assessment") else "N/A"})

        if store:
            store.write("KS31e_R4_synthesis", synthesis)

        # ── Round 5: L4 meta-verification ────────────────────────────
        meta = run_meta_verification(
            claim.text,
            lambda x: self.l1.verify_lightweight(x, evidence=claim.evidence),
            r1["final_score"],
            evidence_list=claim.evidence,
            store=store,
        )
        trace.append({"round": 5, "layer": "L4", "action": "meta_verify",
                       "meta_verdict": meta["meta_verdict"],
                       "flags": meta["flags"],
                       "confidence_modifier": meta["confidence_modifier"]})

        # Step-level meta for borderline steps
        step_meta = []
        for i, sr in enumerate(step_results):
            if sr["pass_rate"] <= 0.85:
                sm = run_meta_verification(
                    sr["text"],
                    lambda x: self.l1.verify_lightweight(x, evidence=claim.evidence),
                    sr["pass_rate"],
                )
                step_meta.append({"step": i, "meta": sm["meta_verdict"], "flags": sm["flags"]})

        if store and step_meta:
            store.write("KS31e_R5_step_meta", step_meta)

        # ── Round 6: L5 enrichment delta ─────────────────────────────
        # Did semantic understanding actually change anything?
        trace.append({
            "round": 6, "layer": "L5", "action": "enrichment_assessment",
            "semantic_impact": enrichment["semantic_impact"],
            "delta": enrichment["delta"],
            "mode": semantics["mode"],
        })

        # ── Final verdict: combine all layers ────────────────────────
        final_verdict, final_score = self._combine_verdicts(r1, synthesis, causal, enrichment)

        # Apply L4 modifier
        final_score = round(final_score * meta["confidence_modifier"], 4)
        if meta["meta_verdict"] == "HOLLOW" and final_verdict in ("VERIFIED", "EXPLORING"):
            final_verdict = "EXPLORING"
        elif meta["meta_verdict"] == "FORM_ONLY" and final_verdict == "VERIFIED":
            # But check L5: if semantic enrichment shows HIGH impact, L1 IS content-aware now
            if enrichment["semantic_impact"] == "HIGH":
                pass  # L5 rescued it — keep VERIFIED
            else:
                final_verdict = "EXPLORING"

        # ── Temporal modifier ────────────────────────────────────────
        temporal_freshness = temporal.get("temporal_freshness", 1.0)
        if temporal_freshness < 0.5:
            # Outdated knowledge: downgrade confidence
            final_score = round(final_score * (0.5 + temporal_freshness), 4)
            if final_verdict == "VERIFIED" and temporal.get("temporal_risk") in ("high", "critical"):
                final_verdict = "EXPLORING"

        elapsed = time.time() - t0
        return self._build_output(
            verdict=final_verdict, final_score=final_score,
            r1_result=r1, synthesis=synthesis, trace=trace,
            elapsed=elapsed, store=store, cycle_count=2,
            meta=meta, step_meta=step_meta,
            semantics=semantics, causal=causal, enrichment=enrichment,
            temporal=temporal,
        )

    def _combine_verdicts(self, r1_result, synthesis, causal, enrichment):
        """Combine direct (R1), compositional (R4), causal (L5), and semantic verdicts."""
        r1_score = r1_result["final_score"]
        comp = synthesis["composite_verdict"]
        causal_validity = causal.get("overall_causal_validity", "unknown")

        # Base combination (same as KS31b)
        if comp == "VERIFIED":
            base_verdict = "VERIFIED"
            base_score = min(r1_score * 1.05, 1.0)
        elif comp == "EXPLORING":
            base_verdict = "EXPLORING"
            base_score = round(r1_score, 4)
        elif comp == "PARTIALLY_VERIFIED":
            base_verdict = "PARTIALLY_VERIFIED"
            base_score = round(r1_score * 0.9, 4)
        else:
            if r1_result["verdict"] == "VERIFIED":
                base_verdict = "EXPLORING"
                base_score = round(r1_score * 0.85, 4)
            else:
                weakest_rate = synthesis["weakest_step"]["pass_rate"] if synthesis.get("weakest_step") else 0
                base_verdict = "UNVERIFIED"
                base_score = round(max(r1_score, weakest_rate), 4)

        # Causal modifier: weak causality degrades confidence
        if causal_validity == "unfounded" and base_verdict == "VERIFIED":
            base_verdict = "EXPLORING"
            base_score *= 0.7
        elif causal_validity == "weak":
            base_score *= 0.85
        elif causal_validity == "valid":
            base_score = min(base_score * 1.05, 1.0)  # causal confirmation bonus

        # Semantic impact modifier
        # When semantic enrichment reveals significant divergence between
        # raw text verification and meaning-level verification, the enriched
        # score should influence the final score proportionally.
        enrichment_delta = enrichment.get("delta", 0)
        enriched_avg = enrichment.get("enriched_avg_rate", base_score)

        if enrichment["semantic_impact"] == "HIGH":
            # HIGH impact: enrichment revealed meaningful content structure.
            # Blend base_score with enriched_avg (weight toward enriched).
            base_score = round(base_score * 0.4 + enriched_avg * 0.6, 4)
            if enriched_avg > 0.8 and base_verdict in ("UNVERIFIED", "EXPLORING"):
                base_verdict = "PARTIALLY_VERIFIED"
            elif enriched_avg < 0.3 and base_verdict in ("VERIFIED", "PARTIALLY_VERIFIED"):
                base_verdict = "EXPLORING"
        elif enrichment["semantic_impact"] == "MODERATE":
            # MODERATE: some content signal, gentle blend
            base_score = round(base_score * 0.7 + enriched_avg * 0.3, 4)

        return base_verdict, round(base_score, 4)

    def _build_output(self, verdict, final_score, r1_result, trace, elapsed,
                      store=None, cycle_count=1, synthesis=None, note=None,
                      meta=None, step_meta=None,
                      semantics=None, causal=None, enrichment=None,
                      temporal=None):
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

        # L5 Semantic info
        if semantics:
            output["semantic"] = {
                "mode": semantics["mode"],
                "propositions_extracted": len(semantics["propositions"]),
                "implicit_assumptions": len(semantics.get("implicit_assumptions", [])),
                "key_entities": semantics.get("key_entities", []),
            }
        if causal:
            output["causal"] = {
                "mode": causal.get("mode", "unknown"),
                "chain_length": len(causal.get("causal_chain", [])),
                "missing_links": causal.get("missing_links", []),
                "confounders": causal.get("confounders", []),
                "validity": causal.get("overall_causal_validity", "unknown"),
            }
        if enrichment:
            output["enrichment"] = enrichment

        # L4 Meta
        if meta:
            output["meta_verification"] = {
                "meta_verdict": meta["meta_verdict"],
                "flags": meta["flags"],
                "confidence_modifier": meta["confidence_modifier"],
                "multi_source": meta.get("m2_multi_source", {}),
            }
        if step_meta:
            output["step_meta"] = step_meta

        # Synthesis
        if synthesis:
            output["synthesis"] = {
                "composite_verdict": synthesis["composite_verdict"],
                "reason": synthesis["reason"],
                "step_count": synthesis["step_count"],
                "passed_count": synthesis["passed_count"],
                "failed_steps": synthesis["failed_steps"],
                "gap_steps": synthesis["gap_steps"],
                "causal_gap_steps": synthesis.get("causal_gap_steps", []),
                "weakest_step": synthesis["weakest_step"],
                "causal_assessment": synthesis.get("causal_assessment"),
            }

        # Temporal context
        if temporal:
            output["temporal"] = {
                "freshness": temporal["temporal_freshness"],
                "risk": temporal["temporal_risk"],
                "domain": temporal["temporal_domain"],
                "knowledge_year": temporal.get("knowledge_year"),
                "recommendation": temporal["recommendation"],
                "warnings": temporal.get("warnings", []),
            }

        # Flags summary
        flags = []
        if semantics and semantics["mode"] == "llm":
            flags.append("CONTENT_AWARE")
        elif semantics and semantics["mode"] == "degraded_enhanced":
            flags.append("CONTENT_PARTIAL")
        elif semantics:
            flags.append("DEGRADED_MODE")
        if causal:
            cv = causal.get("overall_causal_validity", "unknown")
            flag_map = {"valid": "CAUSAL_VALID", "partial": "CAUSAL_PARTIAL",
                        "weak": "CAUSAL_WEAK", "unfounded": "CAUSAL_WEAK",
                        "non_causal": "NON_CAUSAL"}
            flags.append(flag_map.get(cv, "CAUSAL_UNKNOWN"))
        if meta and "FORMAL_ONLY" in meta.get("flags", []):
            if enrichment and enrichment["semantic_impact"] == "HIGH":
                flags.append("FORM_ONLY_RESCUED_BY_L5")
            else:
                flags.append("FORMAL_ONLY")
        if temporal:
            risk = temporal.get("temporal_risk", "none")
            if risk in ("high", "critical"):
                flags.append("TEMPORAL_RISK")
            elif risk == "medium":
                flags.append("TEMPORAL_CAUTION")
        output["flags"] = flags

        if note:
            output["note"] = note

        if store:
            store.write("KS31e_final", output)
            store.finalize()

        return output


# ─── Test ───────────────────────────────────────────────────────────────────

def run_tests():
    import tempfile

    ks = KS31e()

    tests = [
        ("Factual (1-cycle expected)",
         Claim(
             "Water boils at 100 degrees Celsius at standard pressure",
             evidence=["Physics textbook", "Thermodynamics"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"physics").hexdigest(),
         )),
        ("Multi-step syllogism",
         Claim(
             "All mammals are warm-blooded. Whales are mammals. Therefore whales are warm-blooded.",
             evidence=["Biology", "Zoology classification"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"biology").hexdigest(),
         )),
        ("Causal claim (L5 should detect causal structure)",
         Claim(
             "The economy is growing rapidly. Therefore unemployment will decrease significantly.",
             evidence=["Economic theory"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"economics").hexdigest(),
         )),
        ("Transitive chain",
         Claim(
             "Iron is denser than aluminum. Aluminum is denser than wood. Wood is denser than paper. Therefore iron is denser than paper.",
             evidence=["Material science", "Density tables"],
             source_llm="claude-opus-4-6",
             training_data_hash=hashlib.sha256(b"density").hexdigest(),
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
    print(f"KS31e — Semantic-Augmented Cyclic Verification")
    print("=" * 70)

    for label, claim in tests:
        with tempfile.TemporaryDirectory() as d:
            store = StageStore("ks31e_test", base_dir=d)
            result = ks.verify(claim, store=store)

            v = "V" if "VERIFIED" in result["verdict"] else "X"
            print(f"\n[{label}]")
            print(f"  Claim: {claim.text[:65]}...")
            print(f"  [{v}] {result['verdict']} | Score: {result['final_score']}")
            print(f"  Cycles: {result['cycle_count']} | Time: {result['elapsed_sec']}s")
            print(f"  Flags: {result.get('flags', [])}")

            if result.get("semantic"):
                s = result["semantic"]
                print(f"  L5 Semantic: mode={s['mode']}, propositions={s['propositions_extracted']}")
            if result.get("causal"):
                c = result["causal"]
                print(f"  L5 Causal: validity={c['validity']}, chain={c['chain_length']}, missing={len(c['missing_links'])}")
            if result.get("enrichment"):
                e = result["enrichment"]
                print(f"  Enrichment: impact={e['semantic_impact']}, delta={e['delta']}")

            if result.get("synthesis"):
                s = result["synthesis"]
                print(f"  Synthesis: {s['composite_verdict']} ({s['reason'][:80]})")
                if s.get("causal_assessment"):
                    ca = s["causal_assessment"]
                    print(f"  Causal Assessment: validity={ca['validity']}, missing={len(ca['missing_links'])}")

            stages = store.list_stages()
            print(f"  Stages: {len(stages)}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_tests()
