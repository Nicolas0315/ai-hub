from __future__ import annotations

from typing import Any


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
        try:
            import rust_kq_kernels as mod  # type: ignore

            self._mod = mod
            self.available = True
        except Exception:
            self.available = False

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
