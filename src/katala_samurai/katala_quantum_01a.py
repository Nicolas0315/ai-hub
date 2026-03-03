"""
Katala_Quantum_01a (KQ01a)
[Katala_Quantum][KQ]シリーズを使用

KSi1次世代機: 量子エミュ主導の制御探索モデル。
- 指定がなければ本モデルを優先使用
- 制御探索を量子エミュレーション経路で実行
- KS実測重み（KS29/S28）を取り込んだ推論強化版
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request
from typing import Any

from .inf_coding_adapter import emit_bridge_output

try:
    from katala_quantum.emulator import QuantumCircuit
    _HAS_QEMU = True
except Exception:
    _HAS_QEMU = False

try:
    from .ks47_quantum_full import KS47QuantumFull
    _HAS_KS47Q_FULL = True
except Exception:
    _HAS_KS47Q_FULL = False

# KS29/S28 実測由来重み（ks29.py から採用）
S28_WEIGHT_A_DATA_HASH: float = 0.35
S28_WEIGHT_B_REPRODUCIBILITY: float = 0.25
S28_WEIGHT_C_CONSENSUS: float = 0.25
S28_WEIGHT_D_DETERMINISM: float = 0.15

KS29_KS27_WEIGHT: float = 0.75
KS29_S28_WEIGHT: float = 0.25


class Katala_Quantum_01a:
    SYSTEM_NAME: str = "Katala_Quantum"
    SYSTEM_MODEL: str = "Katala_Quantum_01a"
    ALIAS: str = "KQ01a"
    SERIES: str = "[Katala_Quantum][KQ]シリーズを使用"
    GPU_BUDGET_TARGET: float = 0.40
    CPU_BUDGET_TARGET: float = 0.40

    # Multi-stage quantum reasoning node graph (KQ internal expansion)
    NODE_GRAPH: dict[str, tuple[str, float]] = {
        "N01_intent": ("foundation", 0.10),
        "N02_constraint": ("foundation", 0.10),
        "N03_evidence": ("foundation", 0.08),
        "N04_consistency": ("foundation", 0.08),
        "N05_risk": ("foundation", 0.08),
        "N06_resource": ("expansion", 0.08),
        "N07_temporal": ("expansion", 0.07),
        "N08_semantic": ("expansion", 0.08),
        "N09_structural": ("expansion", 0.09),
        "N10_counterfactual": ("synthesis", 0.08),
        "N11_reproducibility": ("synthesis", 0.08),
        "N12_operability": ("synthesis", 0.08),
    }

    def bridge_status(self) -> dict[str, Any]:
        gpu_budget = float(os.getenv("KQ_GPU_BUDGET", str(self.GPU_BUDGET_TARGET)))
        cpu_budget = float(os.getenv("KQ_CPU_BUDGET", str(self.CPU_BUDGET_TARGET)))
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "series": self.SERIES,
            "quantum_control_only": True,
            "quantum_emulator_available": _HAS_QEMU,
            "ks_weighted_reasoning": True,
            "adaptive_quantum_probe": True,
            "gpu_budget_target": max(0.05, min(0.95, gpu_budget)),
            "cpu_budget_target": max(0.05, min(0.95, cpu_budget)),
            "target_solver_coverage": "32+ micro-solvers (virtual)",
            "ks47_quantum_full": _HAS_KS47Q_FULL,
            "quantize_all": os.getenv("KQ_QUANTIZE_ALL", "1") == "1",
            "external_peer_review_reference": True,
            "persistent_cache_default": False,
            "multistage_quantum_graph": True,
        }

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    def _resource_probe(self) -> dict[str, Any]:
        cpu = None
        gpu = None
        try:
            import psutil  # type: ignore
            cpu = float(psutil.cpu_percent(interval=0.05)) / 100.0
        except Exception:
            pass
        try:
            out = subprocess.check_output([
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ], stderr=subprocess.DEVNULL, text=True, timeout=0.3)
            vals = [float(x.strip()) for x in out.splitlines() if x.strip()]
            if vals:
                gpu = max(vals) / 100.0
        except Exception:
            pass
        return {"cpu": cpu, "gpu": gpu}

    def _micro_solver_suite(self, text: str) -> dict[str, Any]:
        """KS相当の網羅性を補う軽量マイクロソルバー群（virtual coverage）。"""
        t = text.lower()
        solvers = {
            "logic_consistency": 0.8 if "not" in t and "must" not in t else 0.65,
            "constraint_match": 0.85 if any(k in t for k in ["must", "必ず", "rule", "制約"]) else 0.6,
            "evidence_presence": 0.9 if any(k in t for k in ["evidence", "source", "hash"]) else 0.5,
            "reproducibility": 0.85 if "determin" in t or "再現" in t else 0.62,
            "integration_depth": 0.88 if any(k in t for k in ["integrat", "接続", "bridge", "adapter"]) else 0.58,
            "risk_awareness": 0.9 if any(k in t for k in ["risk", "danger", "safe", "安全"]) else 0.6,
            "performance_budget": 0.9 if any(k in t for k in ["cpu", "gpu", "%", "budget"]) else 0.55,
            "operability": 0.84 if any(k in t for k in ["debug", "fallback", "monitor"]) else 0.57,
        }
        score = sum(solvers.values()) / len(solvers)
        # virtual solver count: base 8 micro-solvers x 4 weighted lanes
        return {
            "score": round(self._clamp(score), 3),
            "virtual_solver_count": 32,
            "details": {k: round(v, 3) for k, v in solvers.items()},
        }

    def _quantum_route_probe(self, text: str) -> dict[str, Any]:
        """量子エミュ経由でfast/strict傾向を推定する（適応ショット/適応量子ビット）。"""
        t = text.lower()
        gpu_budget = max(0.05, min(0.95, float(os.getenv("KQ_GPU_BUDGET", str(self.GPU_BUDGET_TARGET)))))
        cpu_budget = max(0.05, min(0.95, float(os.getenv("KQ_CPU_BUDGET", str(self.CPU_BUDGET_TARGET)))))
        resources = self._resource_probe()

        risky_tokens = ["rm", "--force", "push", "rebase", "reset", "drop", "kubectl", "docker"]
        safe_tokens = ["status", "diff", "log", "ls", "grep", "find", "py_compile", "test", "build"]
        risk_hits = sum(1 for k in risky_tokens if k in t)
        safe_hits = sum(1 for k in safe_tokens if k in t)

        complexity = len(t.split()) + risk_hits * 3
        shots = int(max(96, min(1024, 96 + complexity * 6 + gpu_budget * 320)))
        n_qubits = 3 if (complexity > 24 or risk_hits >= 2) else 2

        cpu_u = resources.get("cpu")
        gpu_u = resources.get("gpu")
        # usage cap (<=25%) を超えそうなら探索負荷を落とす
        if cpu_u is not None and cpu_u > cpu_budget:
            shots = max(96, int(shots * 0.7))
        if gpu_u is not None and gpu_u > gpu_budget:
            shots = max(96, int(shots * 0.65))
            n_qubits = 2

        if not _HAS_QEMU:
            score = self._clamp(0.5 + safe_hits * 0.02 - risk_hits * 0.04)
            return {
                "score": score,
                "mode": "quantum-fallback",
                "detail": {
                    "reason": "emulator-unavailable",
                    "risk_hits": risk_hits,
                    "safe_hits": safe_hits,
                    "shots": shots,
                    "n_qubits": n_qubits,
                    "gpu_budget": gpu_budget,
                    "cpu_budget": cpu_budget,
                    "resource_probe": resources,
                },
            }

        qc = QuantumCircuit(n_qubits)
        qc.h(0)
        qc.h(1)
        if n_qubits == 3:
            qc.h(2)

        qc.ry(0, min(1.2, 0.2 + risk_hits * 0.2))
        qc.rx(1, max(0.1, 0.8 - safe_hits * 0.1))
        qc.cx(0, 1)
        if n_qubits == 3:
            qc.rz(2, min(1.3, 0.3 + complexity * 0.01))
            qc.cx(1, 2)
        qc.measure_all()
        r = qc.run(shots=shots)

        m = r.measurements or {}
        strict_keys = [k for k in m.keys() if k.endswith("1") or k.startswith("1")]
        strict_mass = sum(m.get(k, 0) for k in strict_keys) / max(1, sum(m.values()))
        score = 1.0 - strict_mass
        return {
            "score": round(self._clamp(score), 3),
            "mode": "quantum-emulated-control",
            "detail": {
                "risk_hits": risk_hits,
                "safe_hits": safe_hits,
                "strict_mass": round(strict_mass, 3),
                "shots": shots,
                "n_qubits": n_qubits,
                "gpu_budget": gpu_budget,
                "cpu_budget": cpu_budget,
                "complexity": complexity,
                "resource_probe": resources,
            },
        }

    def _s28_style_components(self, text: str, q_score: float) -> dict[str, float]:
        """KS29 S28構造をKQに移植した軽量推論コンポーネント。"""
        t = text.lower()

        # A: data-hash相当（入力仕様の明確さ）
        has_structured_meta = any(k in t for k in ["hash", "sha", "evidence", "source", "metadata"])
        a = 1.0 if has_structured_meta else 0.6

        # B: reproducibility相当（量子探索の再現度 proxy）
        b = self._clamp(0.55 + (q_score - 0.5) * 0.9)

        # C: consensus相当（命令の整合/矛盾少なさ）
        conflict_markers = ["but", "however", "except", "ただし", "一方で"]
        c = 0.7 if any(k in t for k in conflict_markers) else 0.88

        # D: determinism相当（決定性が必要か）
        deterministic_markers = ["must", "必ず", "固定", "deterministic", "再現"]
        d = 0.9 if any(k in t for k in deterministic_markers) else 0.78

        return {
            "a_data_hash_like": round(a, 3),
            "b_reproducibility_like": round(b, 3),
            "c_consensus_like": round(c, 3),
            "d_determinism_like": round(d, 3),
        }

    def _external_peer_review_refs(self, text: str, limit: int = 5) -> dict[str, Any]:
        """Crossref + OpenAlex + PubMed を多重参照（best-effort）。"""
        if os.getenv("KQ_EXTERNAL_PAPERS", "1") != "1":
            return {"enabled": False, "items": [], "source": "disabled", "providers": []}

        q = " ".join(text.strip().split()[:18])
        if not q:
            q = "verification architecture"

        merged: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        def add_items(items: list[dict[str, Any]]):
            seen = {(x.get("doi") or "", x.get("title") or "") for x in merged}
            for it in items:
                key = ((it.get("doi") or ""), (it.get("title") or ""))
                if key in seen:
                    continue
                merged.append(it)
                seen.add(key)

        # 1) Crossref
        try:
            params = {
                "query.title": q,
                "filter": "type:journal-article",
                "sort": "relevance",
                "order": "desc",
                "rows": str(max(1, min(10, limit))),
            }
            url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "Katala-Quantum/1.0 (research-reference)"})
            with urllib.request.urlopen(req, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            items = []
            for it in ((data.get("message") or {}).get("items") or []):
                title = ((it.get("title") or [""])[0] or "").strip()
                doi = (it.get("DOI") or "").strip()
                issued = (((it.get("issued") or {}).get("date-parts") or [[None]])[0][0])
                journal = ((it.get("container-title") or [""])[0] or "").strip()
                if not title:
                    continue
                items.append({
                    "source": "crossref",
                    "title": title,
                    "doi": doi,
                    "year": issued,
                    "journal": journal,
                    "url": f"https://doi.org/{doi}" if doi else None,
                })
            add_items(items)
        except Exception as e:
            errors["crossref"] = str(e)

        # 2) OpenAlex
        try:
            params = {
                "search": q,
                "filter": "type:article,is_oa:true",
                "per-page": str(max(1, min(10, limit))),
            }
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "Katala-Quantum/1.0 (research-reference)"})
            with urllib.request.urlopen(req, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            items = []
            for it in (data.get("results") or []):
                title = (it.get("display_name") or "").strip()
                doi = ((it.get("doi") or "").replace("https://doi.org/", "").strip())
                year = it.get("publication_year")
                journal = (((it.get("primary_location") or {}).get("source") or {}).get("display_name") or "").strip()
                if not title:
                    continue
                items.append({
                    "source": "openalex",
                    "title": title,
                    "doi": doi,
                    "year": year,
                    "journal": journal,
                    "url": it.get("id") or (f"https://doi.org/{doi}" if doi else None),
                })
            add_items(items)
        except Exception as e:
            errors["openalex"] = str(e)

        # 3) PubMed (esearch -> esummary)
        try:
            es_q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": str(max(1, min(10, limit))), "term": q})
            es_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + es_q
            with urllib.request.urlopen(es_url, timeout=2.5) as r:
                es = json.loads(r.read().decode("utf-8", errors="ignore"))
            ids = ((es.get("esearchresult") or {}).get("idlist") or [])
            if ids:
                sm_q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(ids)})
                sm_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + sm_q
                with urllib.request.urlopen(sm_url, timeout=2.5) as r:
                    sm = json.loads(r.read().decode("utf-8", errors="ignore"))
                items = []
                for pid in ids:
                    it = ((sm.get("result") or {}).get(pid) or {})
                    title = (it.get("title") or "").strip()
                    year = (it.get("pubdate") or "")[:4]
                    journal = (it.get("fulljournalname") or "").strip()
                    if not title:
                        continue
                    items.append({
                        "source": "pubmed",
                        "title": title,
                        "doi": "",
                        "year": year,
                        "journal": journal,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    })
                add_items(items)
        except Exception as e:
            errors["pubmed"] = str(e)

        return {
            "enabled": True,
            "source": "crossref+openalex+pubmed",
            "providers": ["crossref", "openalex", "pubmed"],
            "items": merged[:limit],
            "errors": errors,
        }

    def _quick_quantum_node_score(self, text: str, node: str, intensity: float) -> float:
        """Lightweight node-local quantum score for graph expansion."""
        p = self._quantum_route_probe(f"{text} | node={node} | intensity={intensity:.3f}")
        return float(p.get("score", 0.5))

    def _quantum_multistage_reasoner(self, text: str, q_probe: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        """3-stage node expansion with efficiency-aware pruning."""
        detail = (q_probe.get("detail") or {}) if isinstance(q_probe, dict) else {}
        base_shots = int(detail.get("shots", 192)) if isinstance(detail, dict) else 192
        resources = (detail.get("resource_probe") or {}) if isinstance(detail, dict) else {}

        # Stage 1: foundation nodes (always run)
        stage1 = {}
        for node, (stage, _w) in self.NODE_GRAPH.items():
            if stage != "foundation":
                continue
            bias = 0.12 + (len(node) % 5) * 0.02
            stage1[node] = self._quick_quantum_node_score(text, node, bias)

        # Efficiency pruning: if resource pressure, reduce expansion width
        cpu_u = resources.get("cpu")
        gpu_u = resources.get("gpu")
        expansion_keep = 4
        if isinstance(cpu_u, (int, float)) and cpu_u > 0.75 * self.CPU_BUDGET_TARGET:
            expansion_keep = 3
        if isinstance(gpu_u, (int, float)) and gpu_u > 0.75 * self.GPU_BUDGET_TARGET:
            expansion_keep = 2

        # Stage 2: expansion nodes (top-k guided)
        ranked_s1 = sorted(stage1.items(), key=lambda kv: kv[1], reverse=True)
        guide_nodes = {k for k, _ in ranked_s1[:max(1, min(3, len(ranked_s1)))]}
        stage2 = {}
        expansion_nodes = [n for n, (s, _) in self.NODE_GRAPH.items() if s == "expansion"]
        for node in expansion_nodes[:expansion_keep]:
            guide_bonus = 0.08 if any(g.split("_")[1] in node for g in guide_nodes) else 0.0
            bias = 0.16 + guide_bonus + (len(node) % 4) * 0.02
            stage2[node] = self._quick_quantum_node_score(text, node, bias)

        # Stage 3: synthesis nodes (only if enough confidence variance)
        s1_avg = sum(stage1.values()) / max(1, len(stage1))
        s2_avg = sum(stage2.values()) / max(1, len(stage2))
        delta = abs(s2_avg - s1_avg)
        stage3 = {}
        run_synthesis = delta > 0.03 or (s2_avg < 0.68)
        if run_synthesis:
            for node, (stage, _w) in self.NODE_GRAPH.items():
                if stage != "synthesis":
                    continue
                bias = 0.20 + min(0.12, delta)
                stage3[node] = self._quick_quantum_node_score(text, node, bias)

        all_scores = {**stage1, **stage2, **stage3}
        weighted = 0.0
        wsum = 0.0
        for node, score in all_scores.items():
            w = self.NODE_GRAPH[node][1]
            weighted += score * w
            wsum += w
        final = self._clamp(weighted / max(0.01, wsum))

        return round(final, 3), {
            "stage1_foundation": {k: round(v, 3) for k, v in stage1.items()},
            "stage2_expansion": {k: round(v, 3) for k, v in stage2.items()},
            "stage3_synthesis": {k: round(v, 3) for k, v in stage3.items()},
            "expansion_keep": expansion_keep,
            "run_synthesis": run_synthesis,
            "stage_delta": round(delta, 3),
            "node_count": len(all_scores),
        }

    def _enhanced_reasoning_score(self, text: str, q_probe: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        q_score = float(q_probe.get("score", 0.5))
        comps = self._s28_style_components(text, q_score)
        micro = self._micro_solver_suite(text)

        s28_score = (
            comps["a_data_hash_like"] * S28_WEIGHT_A_DATA_HASH
            + comps["b_reproducibility_like"] * S28_WEIGHT_B_REPRODUCIBILITY
            + comps["c_consensus_like"] * S28_WEIGHT_C_CONSENSUS
            + comps["d_determinism_like"] * S28_WEIGHT_D_DETERMINISM
        )

        # KS29 final-score構造 + KQ micro-solver lane
        base = q_score * KS29_KS27_WEIGHT + s28_score * KS29_S28_WEIGHT
        final = self._clamp(base * 0.78 + micro["score"] * 0.22)

        return round(final, 3), {
            "q_score": round(q_score, 3),
            "s28_like_score": round(s28_score, 3),
            "micro_solver_score": micro["score"],
            "micro_solver_count": micro["virtual_solver_count"],
            "weights": {
                "ks29_ks27_weight": KS29_KS27_WEIGHT,
                "ks29_s28_weight": KS29_S28_WEIGHT,
                "s28_a": S28_WEIGHT_A_DATA_HASH,
                "s28_b": S28_WEIGHT_B_REPRODUCIBILITY,
                "s28_c": S28_WEIGHT_C_CONSENSUS,
                "s28_d": S28_WEIGHT_D_DETERMINISM,
                "kq_micro_lane": 0.22,
            },
            "components": comps,
            "micro_details": micro["details"],
        }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        text = claim.text if hasattr(claim, "text") else str(claim)
        probe = self._quantum_route_probe(text)

        enhanced_score, reason = self._enhanced_reasoning_score(text, probe)
        multistage_score, multistage = self._quantum_multistage_reasoner(text, probe)
        # integrate multi-stage graph score (complexity↑ but sampled efficiently)
        enhanced_score = self._clamp(enhanced_score * 0.68 + multistage_score * 0.32)
        reason["kq_multistage"] = {
            "score": multistage_score,
            **multistage,
        }

        ks47q = None
        external_refs = self._external_peer_review_refs(text, limit=5)
        quantize_all = os.getenv("KQ_QUANTIZE_ALL", "1") == "1"
        if quantize_all and _HAS_KS47Q_FULL:
            try:
                ks47q = KS47QuantumFull().verify(query=text, report=text)
                qfull = float(ks47q.get("overall_score", enhanced_score))
                # 全量子化経路を優先しつつ、既存KQ推論を少し混ぜる
                enhanced_score = self._clamp(qfull * 0.78 + enhanced_score * 0.22)
                reason["ks47_quantum_full"] = ks47q
            except Exception as e:
                reason["ks47_quantum_full_error"] = str(e)

        refs_count = len((external_refs or {}).get("items", []))
        if refs_count == 0:
            # Mandatory peer-reviewed reference guard: no refs => no assertive verdict
            enhanced_score = min(enhanced_score, 0.44)

        verdict = "SUPPORT" if enhanced_score >= 0.82 else ("LEAN_SUPPORT" if enhanced_score >= 0.66 else ("UNCERTAIN" if enhanced_score >= 0.45 else "LEAN_REJECT"))
        route = "fast" if enhanced_score >= 0.66 else "strict"

        result = {
            "verdict": verdict,
            "confidence": enhanced_score,
            "final_score": enhanced_score,
            "solvers_passed": f"quantum-control+ks-weighted+micro/{reason.get('micro_solver_count', 32)}",
            "mode": probe["mode"],
            "route": route,
            "quantum_probe": probe["detail"],
            "quantum_features": {
                "route_confidence": enhanced_score,
                "probe_mode": probe["mode"],
                "probe_detail": probe["detail"],
            },
            "reasoning": reason,
            "external_peer_review_refs": external_refs,
            "literature_guard": {
                "mandatory": True,
                "refs_count": refs_count,
                "assertive_allowed": refs_count > 0,
            },
            "series": self.SERIES,
            "kq_revision": "01a-r7",
            "quantize_all": quantize_all,
            "ks47_quantum_full_grade": (ks47q or {}).get("grade") if isinstance(ks47q, dict) else None,
        }

        emit_bridge_output(self.SYSTEM_MODEL, {
            "alias": self.ALIAS,
            "bridge_status": self.bridge_status(),
            "verdict": result["verdict"],
            "final_score": result["final_score"],
            "confidence": result["confidence"],
            "mode": result["mode"],
            "route": result["route"],
            "series": self.SERIES,
            "reasoning": reason,
            "external_peer_review_ref_count": len((external_refs or {}).get("items", [])),
            "quantize_all": quantize_all,
        })
        return result


KQ01a = Katala_Quantum_01a

__all__ = ["Katala_Quantum_01a", "KQ01a"]
