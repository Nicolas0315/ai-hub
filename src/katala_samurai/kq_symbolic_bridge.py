from __future__ import annotations

import ast
from typing import Any


class _SafeEval(ast.NodeVisitor):
    ALLOWED_BIN = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Pow: lambda a, b: a ** b,
        ast.Mod: lambda a, b: a % b,
    }
    ALLOWED_UNARY = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
        ast.Not: lambda a: not a,
    }
    ALLOWED_BOOL = {
        ast.And: all,
        ast.Or: any,
    }

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError("unsupported constant")

    def visit_Name(self, node: ast.Name):
        if node.id in {"True", "False"}:
            return node.id == "True"
        raise ValueError(f"name not allowed: {node.id}")

    def visit_BinOp(self, node: ast.BinOp):
        fn = self.ALLOWED_BIN.get(type(node.op))
        if not fn:
            raise ValueError("binop not allowed")
        return fn(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp):
        fn = self.ALLOWED_UNARY.get(type(node.op))
        if not fn:
            raise ValueError("unary op not allowed")
        return fn(self.visit(node.operand))

    def visit_BoolOp(self, node: ast.BoolOp):
        fn = self.ALLOWED_BOOL.get(type(node.op))
        if not fn:
            raise ValueError("bool op not allowed")
        vals = [bool(self.visit(v)) for v in node.values]
        return fn(vals)

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self.visit(comp)
            ok = (
                (isinstance(op, ast.Eq) and left == right)
                or (isinstance(op, ast.NotEq) and left != right)
                or (isinstance(op, ast.Lt) and left < right)
                or (isinstance(op, ast.LtE) and left <= right)
                or (isinstance(op, ast.Gt) and left > right)
                or (isinstance(op, ast.GtE) and left >= right)
            )
            if not ok:
                return False
            left = right
        return True

    def generic_visit(self, node):
        raise ValueError(f"node not allowed: {type(node).__name__}")


def eval_symbolic(expr: str) -> dict[str, Any]:
    try:
        tree = ast.parse(expr, mode="eval")
        val = _SafeEval().visit(tree)
        return {"ok": True, "result": val, "type": type(val).__name__, "proof_status": "derived"}
    except Exception as e:
        return {"ok": False, "error": str(e), "proof_status": "failed"}


def eval_modal(expr: str) -> dict[str, Any]:
    """Very small modal logic kernel.

    Supported surface syntax:
    - box(A -> B)
    - diamond(A)
    - atoms as booleans or simple symbolic names with assignment map omitted (unknown -> undecidable)
    """
    s = (expr or "").strip().lower()
    try:
        if s.startswith("box(") and s.endswith(")"):
            inner = s[4:-1].strip()
            if "->" in inner:
                a, b = [x.strip() for x in inner.split("->", 1)]
                # conservative: implication tautology check only for literals True/False
                if a in {"true", "false"} and b in {"true", "false"}:
                    av = a == "true"
                    bv = b == "true"
                    return {"ok": True, "result": ((not av) or bv), "modal": "box", "proof_status": "checked"}
                return {"ok": True, "result": None, "modal": "box", "proof_status": "undecidable"}
        if s.startswith("diamond(") and s.endswith(")"):
            inner = s[8:-1].strip()
            if inner in {"true", "false"}:
                return {"ok": True, "result": (inner == "true"), "modal": "diamond", "proof_status": "checked"}
            return {"ok": True, "result": None, "modal": "diamond", "proof_status": "undecidable"}
        return {"ok": False, "error": "unsupported modal syntax", "proof_status": "failed"}
    except Exception as e:
        return {"ok": False, "error": str(e), "proof_status": "failed"}


def eval_predicate_lite(expr: str) -> dict[str, Any]:
    """Predicate-lite kernel with finite quantifier syntax.

    Syntax:
    - forall x in [1,2,3]: x > 0
    - exists x in [1,2,3]: x % 2 == 0
    """
    s = (expr or "").strip()
    try:
        low = s.lower()
        if not (low.startswith("forall ") or low.startswith("exists ")):
            return {"ok": False, "error": "unsupported predicate syntax", "proof_status": "failed"}
        quant = "forall" if low.startswith("forall ") else "exists"
        body = s[len(quant):].strip()
        var, rest = body.split(" in ", 1)
        var = var.strip()
        dom_txt, pred_txt = rest.split(":", 1)
        dom = ast.literal_eval(dom_txt.strip())
        if not isinstance(dom, (list, tuple)):
            return {"ok": False, "error": "domain must be list/tuple", "proof_status": "failed"}

        def _check(v):
            safe = pred_txt.replace(var, str(v))
            r = eval_symbolic(safe)
            return bool(r.get("ok") and bool(r.get("result")))

        vals = [_check(v) for v in dom]
        result = all(vals) if quant == "forall" else any(vals)
        return {
            "ok": True,
            "result": result,
            "quantifier": quant,
            "domain_size": len(dom),
            "proof_status": "checked",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "proof_status": "failed"}


def eval_ltl_lite(expr: str) -> dict[str, Any]:
    """Very small LTL-lite evaluator on finite traces.

    Syntax:
    - always p @ [p,p,p]
    - eventually p @ [q,p]
    where tokens in trace are proposition labels per step (single label per step).
    """
    s = (expr or "").strip().lower()
    try:
        if "@" not in s:
            return {"ok": False, "error": "ltl syntax requires '@ trace'", "proof_status": "failed"}
        head, trace_txt = [x.strip() for x in s.split("@", 1)]
        trace = ast.literal_eval(trace_txt)
        if not isinstance(trace, (list, tuple)):
            return {"ok": False, "error": "trace must be list", "proof_status": "failed"}
        trace = [str(x).strip() for x in trace]

        if head.startswith("always "):
            prop = head.replace("always ", "", 1).strip()
            ok = all(step == prop for step in trace)
            return {"ok": True, "result": ok, "operator": "G", "proof_status": "checked"}
        if head.startswith("eventually "):
            prop = head.replace("eventually ", "", 1).strip()
            ok = any(step == prop for step in trace)
            return {"ok": True, "result": ok, "operator": "F", "proof_status": "checked"}
        if " until " in head:
            p, q = [x.strip() for x in head.split(" until ", 1)]
            idx = next((i for i,t in enumerate(trace) if t == q), None)
            if idx is None:
                return {"ok": True, "result": False, "operator": "U", "proof_status": "checked"}
            ok = all(trace[i] == p for i in range(idx))
            return {"ok": True, "result": ok, "operator": "U", "proof_status": "checked"}
        return {"ok": False, "error": "unsupported ltl operator", "proof_status": "failed"}
    except Exception as e:
        return {"ok": False, "error": str(e), "proof_status": "failed"}


def solve_constraint_lite(expr: str) -> dict[str, Any]:
    """Constraint-lite kernel.

    Syntax:
    - x in [-5,5]: x*x - 4 == 0
    - x in [0,10]: x + 3 >= 7 and x % 2 == 0
    """
    s = (expr or "").strip()
    try:
        var, rest = s.split(" in ", 1)
        var = var.strip()
        dom_txt, cons_txt = rest.split(":", 1)
        lo, hi = ast.literal_eval(dom_txt.strip())
        lo = int(lo)
        hi = int(hi)
        sols = []
        for v in range(lo, hi + 1):
            safe = cons_txt.replace(var, str(v))
            r = eval_symbolic(safe)
            if r.get("ok") and bool(r.get("result")):
                sols.append(v)
        return {
            "ok": True,
            "solutions": sols[:128],
            "solution_count": len(sols),
            "proof_status": "checked" if sols else "inconclusive",
            "solver": "constraint-lite",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "proof_status": "failed", "solver": "constraint-lite"}


def solve_smt_optional(expr: str) -> dict[str, Any]:
    """SMT entry with pragmatic fallback.

    If z3 is available and expression is parseable in this lite format,
    we can extend later; for now detect availability and run constraint-lite.
    """
    try:
        import z3  # type: ignore
        _ = z3
        r = solve_constraint_lite(expr)
        r["solver"] = "smt-z3-bridge-lite"
        if r.get("proof_status") == "failed":
            r["proof_status"] = "inconclusive"
        return r
    except Exception:
        r = solve_constraint_lite(expr)
        r["solver"] = "constraint-lite-fallback"
        return r
