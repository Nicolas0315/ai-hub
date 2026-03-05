from __future__ import annotations

from typing import Any

from .kq_symbolic_bridge import eval_symbolic, eval_modal, eval_predicate_lite, solve_constraint_lite, eval_ltl_lite, solve_smt_optional, verify_lean_proof, verify_coq_proof, verify_isabelle_proof, solve_sat_lite, solve_bitvec_lite, solve_array_lite, solve_uf_lite, solve_nra_lite


class RustKQBridge:
    """Rust kernel adapter scaffold for r18 migration.

    Current status:
    - Interface fixed
    - Runtime fallback behavior intentionally explicit
    - Actual rust module wiring to be enabled in phase-2+
    """

    def __init__(self) -> None:
        self.available = False
        self._mod = None
        self.backend = "none"
        try:
            import rust_kq_kernels_native as mod  # type: ignore

            self._mod = mod
            self.available = True
            self.backend = "rust-native"
            return
        except Exception:
            pass

        try:
            import rust_kq_kernels as mod  # type: ignore

            self._mod = mod
            self.available = True
            self.backend = "python-kernel-module"
        except Exception:
            self.available = False
            self.backend = "none"

    def mini_solver_kernel(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.available and self._mod is not None:
            return self._mod.mini_solver_kernel(payload)
        raise RuntimeError("rust_kq_kernels unavailable")

    def spml_kernel(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.available and self._mod is not None:
            return self._mod.spml_kernel(payload)
        raise RuntimeError("rust_kq_kernels unavailable")

    def triadic_kernel(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.available and self._mod is not None:
            return self._mod.triadic_kernel(payload)
        raise RuntimeError("rust_kq_kernels unavailable")

    def symbolic_kernel(self, expr: str) -> dict[str, Any]:
        """Evaluate arithmetic/logical expression via native kernel when available.
        Falls back to KQ safe symbolic evaluator.
        """
        if self.available and self._mod is not None and hasattr(self._mod, "symbolic_kernel"):
            try:
                return self._mod.symbolic_kernel({"expr": expr})
            except Exception:
                pass
        return eval_symbolic(expr)

    def modal_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "modal_kernel"):
            try:
                return self._mod.modal_kernel({"expr": expr})
            except Exception:
                pass
        return eval_modal(expr)

    def predicate_lite_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "predicate_lite_kernel"):
            try:
                return self._mod.predicate_lite_kernel({"expr": expr})
            except Exception:
                pass
        return eval_predicate_lite(expr)

    def constraint_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "constraint_kernel"):
            try:
                return self._mod.constraint_kernel({"expr": expr})
            except Exception:
                pass
        return solve_constraint_lite(expr)

    def ltl_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "ltl_kernel"):
            try:
                return self._mod.ltl_kernel({"expr": expr})
            except Exception:
                pass
        return eval_ltl_lite(expr)

    def smt_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "smt_kernel"):
            try:
                return self._mod.smt_kernel({"expr": expr})
            except Exception:
                pass
        return solve_smt_optional(expr)

    def lean_kernel(self, script: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "lean_kernel"):
            try:
                return self._mod.lean_kernel({"script": script})
            except Exception:
                pass
        return verify_lean_proof(script)

    def coq_kernel(self, script: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "coq_kernel"):
            try:
                return self._mod.coq_kernel({"script": script})
            except Exception:
                pass
        return verify_coq_proof(script)

    def isabelle_kernel(self, script: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "isabelle_kernel"):
            try:
                return self._mod.isabelle_kernel({"script": script})
            except Exception:
                pass
        return verify_isabelle_proof(script)

    def sat_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "sat_kernel"):
            try:
                return self._mod.sat_kernel({"expr": expr})
            except Exception:
                pass
        return solve_sat_lite(expr)

    def bitvec_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "bitvec_kernel"):
            try:
                return self._mod.bitvec_kernel({"expr": expr})
            except Exception:
                pass
        return solve_bitvec_lite(expr)

    def uf_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "uf_kernel"):
            try:
                return self._mod.uf_kernel({"expr": expr})
            except Exception:
                pass
        return solve_uf_lite(expr)

    def array_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "array_kernel"):
            try:
                return self._mod.array_kernel({"expr": expr})
            except Exception:
                pass
        return solve_array_lite(expr)

    def nra_kernel(self, expr: str) -> dict[str, Any]:
        if self.available and self._mod is not None and hasattr(self._mod, "nra_kernel"):
            try:
                return self._mod.nra_kernel({"expr": expr})
            except Exception:
                pass
        return solve_nra_lite(expr)
