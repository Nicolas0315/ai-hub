from __future__ import annotations

from typing import Any

from .kq_symbolic_bridge import eval_symbolic, eval_modal, eval_predicate_lite, solve_constraint_lite, eval_ltl_lite, solve_smt_optional


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
