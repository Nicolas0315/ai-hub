from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tempfile
from itertools import product, combinations
from typing import Any


try:
    from katala_quantum.emulator_lite import QuantumCircuit  # type: ignore
    _HAS_QEMU = True
except Exception:
    QuantumCircuit = None  # type: ignore
    _HAS_QEMU = False


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


class _EnvSafeEval(_SafeEval):
    def __init__(self, env: dict[str, Any]):
        self.env = env or {}

    def visit_Name(self, node: ast.Name):
        if node.id in self.env:
            v = self.env[node.id]
            if isinstance(v, (int, float, bool)):
                return v
        return super().visit_Name(node)


def _eval_symbolic_env(expr: str, env: dict[str, Any]) -> dict[str, Any]:
    try:
        tree = ast.parse(expr, mode="eval")
        val = _EnvSafeEval(env).visit(tree)
        return {"ok": True, "result": val, "type": type(val).__name__}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    out, cur, depth = [], [], 0
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            tok = "".join(cur).strip()
            if tok:
                out.append(tok)
            cur = []
            continue
        cur.append(ch)
    tok = "".join(cur).strip()
    if tok:
        out.append(tok)
    return out


def _rank_envs_quantum_emu(names: list[str], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _HAS_QEMU or not names or not candidates:
        return candidates
    ranked: list[tuple[float, dict[str, Any]]] = []
    for env in candidates:
        try:
            q = QuantumCircuit(max(1, min(8, len(names))))
            for i, k in enumerate(names[:8]):
                v = 1 if bool(env.get(k, False)) else 0
                if v:
                    q.h(i).rz(i, 0.7)
                else:
                    q.rx(i, 0.3)
            m = q.measure_all().run(shots=64).measurements
            score = float(m.get("1" * max(1, min(8, len(names))), 0)) / 64.0
        except Exception:
            score = 0.0
        ranked.append((score, env))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in ranked]


def _nn_qemu_score_env(names: list[str], env: dict[str, Any], feature_bias: dict[str, float] | None = None) -> float:
    """Tiny standalone neural-like scorer (no external deps).

    This is intentionally lightweight: a single-layer logistic scoring over booleanized features,
    designed to prioritize promising assignments before strict solver checks.
    """
    if not names:
        return 0.0
    fb = feature_bias or {}
    z = -0.15
    for i, k in enumerate(names):
        v = 1.0 if bool(env.get(k, False)) else 0.0
        w = 0.55 + ((i % 5) * 0.07) + float(fb.get(k, 0.0))
        z += w * v
    # logistic
    try:
        import math
        return 1.0 / (1.0 + math.exp(-z))
    except Exception:
        return max(0.0, min(1.0, z / (1.0 + abs(z))))


def _rank_envs_nn_qemu(names: list[str], candidates: list[dict[str, Any]], feature_bias: dict[str, float] | None = None) -> list[dict[str, Any]]:
    if not names or not candidates:
        return candidates

    # First, quantum-emu ordering (if available), then neural re-score.
    base = _rank_envs_quantum_emu(names, candidates)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for env in base:
        s = _nn_qemu_score_env(names, env, feature_bias=feature_bias)
        ranked.append((s, env))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in ranked]


def _rank_bool_assignments_nn(names: list[str]) -> list[dict[str, bool]]:
    if not names:
        return []
    cand = [{k: bool(v) for k, v in zip(names, bits)} for bits in product([False, True], repeat=len(names))]
    return _rank_envs_nn_qemu(names, cand)


def _smt_prefix_to_infix(formula: str) -> str:
    s = (formula or "").strip()
    low = s.lower()
    for fn, op in (("and", "and"), ("or", "or")):
        if low.startswith(fn + "(") and s.endswith(")"):
            inner = s[len(fn) + 1 : -1]
            args = _split_top_level(inner, ",")
            return "(" + f" {op} ".join(_smt_prefix_to_infix(a) for a in args) + ")"
    if low.startswith("not(") and s.endswith(")"):
        inner = s[4:-1]
        return f"(not ({_smt_prefix_to_infix(inner)}))"
    return s


def _parse_smt_lite(expr: str) -> tuple[dict[str, tuple[int, int]], str]:
    s = (expr or "").strip()
    if "formula:" in s and "vars:" in s:
        left = s.split("formula:", 1)
        vars_part = left[0].split("vars:", 1)[1].strip().rstrip(";")
        formula = left[1].strip()
        var_defs = _split_top_level(vars_part, ",")
        doms: dict[str, tuple[int, int]] = {}
        for v in var_defs:
            m = re.match(r"^([A-Za-z_]\w*)\s+in\s*\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]$", v)
            if not m:
                continue
            doms[m.group(1)] = (int(m.group(2)), int(m.group(3)))
        return doms, _smt_prefix_to_infix(formula)

    # backward compatible single-var format: x in [a,b]: constraint
    if " in " in s and ":" in s:
        var, rest = s.split(" in ", 1)
        dom_txt, cons_txt = rest.split(":", 1)
        lo, hi = ast.literal_eval(dom_txt.strip())
        return {var.strip(): (int(lo), int(hi))}, cons_txt.strip()

    return {}, s


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


def _ltl_norm_trace(trace_raw: Any) -> list[set[str]]:
    if not isinstance(trace_raw, (list, tuple)):
        raise ValueError("trace must be list")
    out: list[set[str]] = []
    for step in trace_raw:
        if isinstance(step, str):
            out.append({step.strip().lower()})
        elif isinstance(step, (list, tuple, set)):
            out.append({str(x).strip().lower() for x in step})
        else:
            out.append({str(step).strip().lower()})
    return out


def _tok_formula(s: str) -> list[str]:
    return [t for t in re.findall(r"EX|AX|EF|AF|EG|AG|->|\(|\)|\!|\&|\||U|[A-Za-z_][A-Za-z0-9_]*", (s or '').upper()) if t]


def _parse_temporal_formula(s: str):
    toks = _tok_formula(s)
    i = 0

    def peek():
        return toks[i] if i < len(toks) else None

    def take(v=None):
        nonlocal i
        t = peek()
        if v is not None and t != v:
            raise ValueError(f"expected {v}, got {t}")
        i += 1
        return t

    def parse_imp():
        n = parse_or()
        while peek() == '->':
            take('->')
            n = ('or', ('not', n), parse_or())
        return n

    def parse_or():
        n = parse_and()
        while peek() in {'|', 'OR'}:
            take(peek())
            n = ('or', n, parse_and())
        return n

    def parse_and():
        n = parse_until()
        while peek() in {'&', 'AND'}:
            take(peek())
            n = ('and', n, parse_until())
        return n

    def parse_until():
        n = parse_unary()
        while peek() == 'U':
            take('U')
            n = ('u', n, parse_unary())
        return n

    def parse_unary():
        t = peek()
        if t in {'!', 'NOT'}:
            take(t)
            return ('not', parse_unary())
        if t in {'G', 'F', 'X', 'EX', 'AX', 'EF', 'AF', 'EG', 'AG'}:
            take(t)
            return (t.lower(), parse_unary())
        if t == '(':
            take('(')
            n = parse_imp()
            take(')')
            return n
        if t is None:
            raise ValueError('unexpected end of formula')
        take()
        if t in {'TRUE', 'TOP'}:
            return ('const', True)
        if t in {'FALSE', 'BOT'}:
            return ('const', False)
        return ('atom', t.lower())

    astn = parse_imp()
    if i != len(toks):
        raise ValueError('trailing tokens')
    return astn


def _eval_temporal_ast(node, trace: list[set[str]], i: int = 0) -> bool:
    k = node[0]
    if k == 'const':
        return bool(node[1])
    if k == 'atom':
        return i < len(trace) and node[1] in trace[i]
    if k == 'not':
        return not _eval_temporal_ast(node[1], trace, i)
    if k == 'and':
        return _eval_temporal_ast(node[1], trace, i) and _eval_temporal_ast(node[2], trace, i)
    if k == 'or':
        return _eval_temporal_ast(node[1], trace, i) or _eval_temporal_ast(node[2], trace, i)
    if k in {'x', 'ex', 'ax'}:
        return (i + 1 < len(trace)) and _eval_temporal_ast(node[1], trace, i + 1)
    if k in {'f', 'ef', 'af'}:
        return any(_eval_temporal_ast(node[1], trace, j) for j in range(i, len(trace)))
    if k in {'g', 'eg', 'ag'}:
        return all(_eval_temporal_ast(node[1], trace, j) for j in range(i, len(trace)))
    if k == 'u':
        a, b = node[1], node[2]
        for j in range(i, len(trace)):
            if _eval_temporal_ast(b, trace, j):
                return all(_eval_temporal_ast(a, trace, t) for t in range(i, j))
        return False
    raise ValueError(f'unsupported node: {k}')


def eval_ltl_lite(expr: str) -> dict[str, Any]:
    """Finite-trace LTL model checker.

    Syntax:
    - <formula> @ <trace>
    Example:
    - G(p -> F q) @ [["p"],["q"]]
    - X p U q @ ["p","q"]
    """
    s = (expr or "").strip()
    try:
        if "@" not in s:
            return {"ok": False, "error": "ltl syntax requires '@ trace'", "proof_status": "failed"}
        head, trace_txt = [x.strip() for x in s.split("@", 1)]
        trace = _ltl_norm_trace(ast.literal_eval(trace_txt))
        astn = _parse_temporal_formula(head)
        ok = _eval_temporal_ast(astn, trace, 0)
        return {"ok": True, "result": ok, "operator": "MC", "proof_status": "checked", "mode": "model-check", "ast": str(astn)}
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


def _interval_propagate(formula: str, doms: dict[str, tuple[int, int]]) -> tuple[dict[str, tuple[int, int]], list[str]]:
    cur = dict(doms)
    notes: list[str] = []
    parts = _split_top_level((formula or "").strip().strip("()"), ",")
    atoms = []
    if (formula or "").strip().lower().startswith("and(") and (formula or "").strip().endswith(")"):
        atoms = parts
    else:
        atoms = re.split(r"\band\b", formula)
    for a in atoms:
        t = a.strip().strip("() ")
        m = re.match(r"^([A-Za-z_]\w*)\s*(<=|>=|<|>)\s*(-?\d+)$", t)
        if not m:
            continue
        v, op, c = m.group(1), m.group(2), int(m.group(3))
        if v not in cur:
            continue
        lo, hi = cur[v]
        if op == ">=":
            lo = max(lo, c)
        elif op == ">":
            lo = max(lo, c + 1)
        elif op == "<=":
            hi = min(hi, c)
        elif op == "<":
            hi = min(hi, c - 1)
        cur[v] = (lo, hi)
        notes.append(f"{v}{op}{c} -> [{lo},{hi}]")
    return cur, notes


def solve_smt_optional(expr: str) -> dict[str, Any]:
    """KQ-native standalone SMT solver (external solver independent).

    Supported examples:
    - x in [-3,3]: x*x-1==0
    - vars: x in [-3,3], y in [0,3]; formula: and(x+y==2, x>=0, y>=0)
    """
    try:
        doms, formula = _parse_smt_lite(expr)
        if not doms:
            r = solve_constraint_lite(expr)
            r["solver"] = "smt-kq-native-fallback"
            r["proof_trace"] = {"mode": "fallback", "reason": "no_domain_declaration"}
            return r

        doms2, prune_notes = _interval_propagate(formula, doms)
        names = list(doms2.keys())
        ranges = [range(lo, hi + 1) for (lo, hi) in doms2.values()]
        total_space = 1
        for r in ranges:
            total_space *= len(r)

        # Standalone-complete mode on bounded problems; partial mode only for very large spaces.
        exhaustive_limit = int(os.getenv("KQ_SMT_EXHAUSTIVE_LIMIT", "200000"))
        max_solutions = int(os.getenv("KQ_SMT_MAX_SOLUTIONS", "512"))

        sols: list[dict[str, int]] = []
        checks = 0
        cand_envs = [{k: int(v) for k, v in zip(names, values)} for values in product(*ranges)]
        cand_envs = _rank_envs_nn_qemu(names, cand_envs)

        for env in cand_envs:
            if total_space > exhaustive_limit and checks >= exhaustive_limit:
                break
            checks += 1
            ev = _eval_symbolic_env(formula, env)
            if ev.get("ok") and bool(ev.get("result")):
                sols.append(env)
                if len(sols) >= max_solutions:
                    break

        exhaustive = (total_space <= exhaustive_limit and checks >= total_space)
        coverage = min(1.0, checks / max(1, total_space))
        status = "checked" if exhaustive else "inconclusive"
        return {
            "ok": True,
            "solver": "smt-kq-native-nn-qemu" if _HAS_QEMU else "smt-kq-native-nn",
            "proof_status": status,
            "solutions": sols,
            "solution_count": len(sols),
            "proof_trace": {
                "mode": "nn-qemu-priority+standalone-enumeration+interval-propagation+env-safe-eval" if _HAS_QEMU else "nn-priority+standalone-enumeration+interval-propagation+env-safe-eval",
                "variables": names,
                "search_space": int(total_space),
                "checked_points": int(checks),
                "coverage": round(float(coverage), 4),
                "exhaustive": bool(exhaustive),
                "exhaustive_limit": int(exhaustive_limit),
                "interval_pruning": prune_notes,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "solver": "smt-kq-native",
            "proof_status": "failed",
            "error": str(e),
            "proof_trace": {"mode": "error"},
        }


def _verify_external_proof(script: str, bin_name: str, args: list[str]) -> dict[str, Any]:
    if shutil.which(bin_name) is None:
        return {"ok": False, "proof_status": "unavailable", "assistant": bin_name, "error": "binary not found"}
    tmp = None
    try:
        suffix = ".lean" if bin_name == "lean" else ".v"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="w", encoding="utf-8") as f:
            f.write(script or "")
            tmp = f.name
        proc = subprocess.run([bin_name, *args, tmp], capture_output=True, text=True)
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "proof_status": "machine-verified" if ok else "failed",
            "assistant": bin_name,
            "stdout": (proc.stdout or "")[:400],
            "stderr": (proc.stderr or "")[:400],
        }
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "assistant": bin_name, "error": str(e)}
    finally:
        try:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def verify_lean_proof(script: str) -> dict[str, Any]:
    return _verify_external_proof(script, "lean", [])


def verify_coq_proof(script: str) -> dict[str, Any]:
    return _verify_external_proof(script, "coqc", [])


def verify_isabelle_proof(script: str) -> dict[str, Any]:
    if shutil.which("isabelle") is None:
        return {"ok": False, "proof_status": "unavailable", "assistant": "isabelle", "error": "binary not found"}
    try:
        proc = subprocess.run(["isabelle", "process", "-q"], input=(script or ""), capture_output=True, text=True, timeout=20)
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "proof_status": "machine-verified" if ok else "failed",
            "assistant": "isabelle",
            "stdout": (proc.stdout or "")[:400],
            "stderr": (proc.stderr or "")[:400],
        }
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "assistant": "isabelle", "error": str(e)}


def solve_sat_lite(expr: str) -> dict[str, Any]:
    """SAT-lite (CDCL-lite flavored) + UNSAT core-lite."""
    try:
        s = (expr or "").strip().lower()
        clause_txts = [x.strip() for x in re.split(r"\)\s*and\s*\(", s.strip().strip("()")) if x.strip()]
        clauses: list[list[tuple[str, bool]]] = []
        vars_set: set[str] = set()
        for c in clause_txts:
            lits = [x.strip() for x in re.split(r"\s+or\s+", c) if x.strip()]
            row = []
            for lit in lits:
                neg = lit.startswith("not ")
                v = lit.replace("not ", "", 1).strip().strip("()")
                if not re.match(r"^[a-z_]\w*$", v):
                    return {"ok": False, "proof_status": "failed", "error": f"invalid literal: {lit}", "solver": "sat-lite"}
                vars_set.add(v)
                row.append((v, not neg))
            if row:
                clauses.append(row)
        vars_list = sorted(vars_set)
        if not vars_list:
            return {"ok": False, "proof_status": "failed", "error": "no variables", "solver": "sat-lite"}

        watched_literals = [[(v if sign else f"not {v}") for v, sign in (cl[:2] if len(cl) >= 2 else cl[:1])] for cl in clauses]

        def _clause_state(cl, env):
            any_unassigned = False
            for v, sign in cl:
                if v in env:
                    if env[v] is sign:
                        return 1
                else:
                    any_unassigned = True
            return 0 if any_unassigned else -1

        trace = {"decisions": 0, "conflicts": 0, "backjumps": 0, "checked_points": 0, "watch_updates": 0}
        learned_clauses: list[str] = []

        def _refresh_watches(env: dict[str, bool]):
            updated = []
            for cl in clauses:
                sats = [(v, sign) for v, sign in cl if (v in env and env[v] is sign)]
                unks = [(v, sign) for v, sign in cl if v not in env]
                picks = sats[:2] if len(sats) >= 2 else (sats + unks)[:2]
                if not picks and cl:
                    picks = cl[:1]
                updated.append([(v if sign else f"not {v}") for v, sign in picks])
            trace["watch_updates"] += 1
            return updated

        ranked_vars = vars_list[:]
        # NN-QEMU assisted variable salience estimate
        probe = [{k: False for k in vars_list}, {k: True for k in vars_list}]
        ranked_env = _rank_envs_nn_qemu(vars_list, probe)
        ranked_vars = [k for k in vars_list if ranked_env and ranked_env[0].get(k, False)] + [k for k in vars_list if not (ranked_env and ranked_env[0].get(k, False))]

        # frequency/activity heuristic (CDCL-lite flavor)
        var_activity = {v: 0 for v in vars_list}
        for cl in clauses:
            for v, _ in cl:
                var_activity[v] = var_activity.get(v, 0) + 1

        def dpll(env: dict[str, bool], level: int = 0):
            nonlocal watched_literals
            trace["checked_points"] += 1
            current_watches = _refresh_watches(env)
            watched_literals = current_watches
            # unit propagation
            changed = True
            while changed:
                changed = False
                for cl in clauses:
                    st = _clause_state(cl, env)
                    if st == -1:
                        trace["conflicts"] += 1
                        # tiny clause-learning surrogate: learn negation of current decision frontier
                        if env:
                            learnt = " or ".join([f"not {k}" if v else k for k, v in sorted(env.items())[:4]])
                            learned_clauses.append(f"conflict_clause({learnt})")
                        return None
                    if st == 0:
                        un = [(v, sign) for v, sign in cl if v not in env]
                        if len(un) == 1:
                            v, sign = un[0]
                            env[v] = sign
                            changed = True

                # pure literal elimination in remaining unresolved clauses
                unresolved = [cl for cl in clauses if _clause_state(cl, env) == 0]
                if unresolved:
                    pol = {}
                    for cl in unresolved:
                        for v, sign in cl:
                            if v in env:
                                continue
                            pol.setdefault(v, set()).add(sign)
                    for v, sset in pol.items():
                        if len(sset) == 1 and v not in env:
                            env[v] = list(sset)[0]
                            changed = True

            if all(_clause_state(cl, env) == 1 for cl in clauses):
                return dict(env)

            # pick next variable by activity among unresolved clauses
            unresolved = [cl for cl in clauses if _clause_state(cl, env) == 0]
            cand = [x for x in ranked_vars if x not in env]
            if unresolved:
                score = {v: 0 for v in cand}
                for cl in unresolved:
                    for vv, _ in cl:
                        if vv in score:
                            score[vv] += 1
                cand.sort(key=lambda x: (score.get(x, 0), var_activity.get(x, 0)), reverse=True)
            v = cand[0] if cand else None
            if v is None:
                return None

            for val in (True, False):
                trace["decisions"] += 1
                env2 = dict(env)
                env2[v] = val
                m = dpll(env2, level + 1)
                if m is not None:
                    return m
            trace["backjumps"] += 1
            learned_clauses.append(f"backjump({v})")
            return None

        sat_model = dpll({})

        if sat_model is not None:
            return {
                "ok": True,
                "proof_status": "checked",
                "solver": "sat-lite-nn-qemu" if _HAS_QEMU else "sat-lite-nn",
                "satisfiable": True,
                "model": sat_model,
                "proof_trace": {
                    "variables": vars_list,
                    "mode": "cdcl-lite+nn-qemu-priority" if _HAS_QEMU else "cdcl-lite+nn-priority",
                    "watched_literals_init": watched_literals,
                    "learned_clauses": learned_clauses,
                    **trace,
                },
            }

        def _sat_for(subset: list[list[tuple[str, bool]]]) -> bool:
            ranked_envs = _rank_bool_assignments_nn(vars_list)
            for env in ranked_envs:
                if all(any((env.get(v, False) is sign) for v, sign in cl) for cl in subset):
                    return True
            return False

        # First shrink greedily, then exact-minimize (for manageable clause counts)
        core = clauses[:]
        changed = True
        while changed and len(core) > 1:
            changed = False
            i = 0
            while i < len(core):
                trial = core[:i] + core[i + 1 :]
                if not _sat_for(trial):
                    core = trial
                    changed = True
                else:
                    i += 1

        exact_min_applied = False
        if len(core) <= 18:
            n = len(core)
            found = None
            for k in range(1, n + 1):
                for idxs in combinations(range(n), k):
                    trial = [core[i] for i in idxs]
                    if not _sat_for(trial):
                        found = trial
                        break
                if found is not None:
                    break
            if found is not None:
                core = found
                exact_min_applied = True

        core_txt = [" or ".join([(v if sign else f"not {v}") for v, sign in cl]) for cl in core]

        unit_pos = {cl[0][0] for cl in core if len(cl) == 1 and cl[0][1] is True}
        unit_neg = {cl[0][0] for cl in core if len(cl) == 1 and cl[0][1] is False}
        for v in sorted(unit_pos & unit_neg):
            learned_clauses.append(f"conflict({v})")

        core_minimal = True
        if len(core) > 1:
            for i in range(len(core)):
                trial = core[:i] + core[i + 1 :]
                if not trial:
                    continue
                if not _sat_for(trial):
                    core_minimal = False
                    break

        return {
            "ok": True,
            "proof_status": "checked",
            "solver": "sat-lite-nn-qemu" if _HAS_QEMU else "sat-lite-nn",
            "satisfiable": False,
            "unsat_core_lite": core_txt,
            "proof_trace": {
                "variables": vars_list,
                "core_size": len(core_txt),
                "mode": "cdcl-lite+nn-qemu-priority" if _HAS_QEMU else "cdcl-lite+nn-priority",
                "watched_literals_init": watched_literals,
                "learned_clauses": learned_clauses,
                "unsat_core_exact_minimized": exact_min_applied,
                "unsat_core_minimal_verified": core_minimal,
                "unsat_core_quality": "high" if core_minimal else "medium",
                **trace,
            },
        }
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "error": str(e), "solver": "sat-lite"}


def solve_bitvec_lite(expr: str) -> dict[str, Any]:
    """BitVec-lite over fixed width integers.

    Syntax:
    - width=8; x=250; y=10; op=add
    - width=8; x=7; y=3; op=and
    """
    try:
        parts = [x.strip() for x in (expr or '').split(';') if x.strip()]
        kv = {}
        for p2 in parts:
            if '=' in p2:
                k,v = p2.split('=',1)
                kv[k.strip().lower()] = v.strip().lower()
        w = int(kv.get('width','8'))
        mod = 1 << max(1,min(64,w))
        x = int(kv.get('x','0'),0) % mod
        y = int(kv.get('y','0'),0) % mod
        op = kv.get('op','add')
        if op == 'add': r = (x + y) % mod
        elif op == 'sub': r = (x - y) % mod
        elif op == 'and': r = x & y
        elif op == 'or': r = x | y
        elif op == 'xor': r = x ^ y
        elif op == 'shl': r = (x << y) % mod
        elif op == 'lshr': r = (x >> y) % mod
        else:
            return {'ok': False, 'proof_status': 'failed', 'solver': 'smt-bitvec-lite', 'error': f'unsupported op: {op}'}
        return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-bitvec-lite', 'width': w, 'result': int(r)}
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'smt-bitvec-lite', 'error': str(e)}


def solve_zfc_lite(expr: str) -> dict[str, Any]:
    """ZFC-lite set reasoning checks.

    Syntax:
    - A={1,2}; B={2,3}; check=subset(A,A)
    - A={1,2}; B={2,3}; check=member(2,A)
    - A={1,2}; B={2,3}; check=union(A,B)
    """
    try:
        parts = [x.strip() for x in (expr or "").split(";") if x.strip()]
        sets: dict[str, set[Any]] = {}
        check = ""
        for p in parts:
            if p.lower().startswith("check="):
                check = p.split("=", 1)[1].strip()
                continue
            if "=" in p:
                k, v = p.split("=", 1)
                k = k.strip()
                if v.strip().startswith("{"):
                    vals = ast.literal_eval(v.strip().replace("{", "[").replace("}", "]"))
                    sets[k] = set(vals)
        if not check:
            return {"ok": False, "proof_status": "failed", "solver": "zfc-lite", "error": "missing check"}
        low = check.lower()
        if low.startswith("subset(") and low.endswith(")"):
            a, b = [x.strip() for x in check[7:-1].split(",", 1)]
            r = sets.get(a, set()).issubset(sets.get(b, set()))
            return {"ok": True, "proof_status": "checked", "solver": "zfc-lite", "result": r}
        if low.startswith("member(") and low.endswith(")"):
            x, a = [x.strip() for x in check[7:-1].split(",", 1)]
            xv = ast.literal_eval(x) if x[:1].isdigit() or x[:1] in "'-\"" else x
            r = xv in sets.get(a, set())
            return {"ok": True, "proof_status": "checked", "solver": "zfc-lite", "result": r}
        if low.startswith("union(") and low.endswith(")"):
            a, b = [x.strip() for x in check[6:-1].split(",", 1)]
            r = sorted(list(sets.get(a, set()) | sets.get(b, set())))
            return {"ok": True, "proof_status": "checked", "solver": "zfc-lite", "result": r}
        if low.startswith("inter(") and low.endswith(")"):
            a, b = [x.strip() for x in check[6:-1].split(",", 1)]
            r = sorted(list(sets.get(a, set()) & sets.get(b, set())))
            return {"ok": True, "proof_status": "checked", "solver": "zfc-lite", "result": r}
        return {"ok": False, "proof_status": "failed", "solver": "zfc-lite", "error": "unsupported check"}
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "solver": "zfc-lite", "error": str(e)}


def _strip_outer_paren(s: str) -> str:
    t = (s or '').strip()
    while t.startswith('(') and t.endswith(')'):
        depth = 0
        ok = True
        for i, ch in enumerate(t):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and i != len(t) - 1:
                    ok = False
                    break
        if ok:
            t = t[1:-1].strip()
        else:
            break
    return t


def _split_top_expr(s: str, token: str) -> tuple[str, str] | None:
    t = s
    depth = 0
    i = 0
    while i < len(t):
        ch = t[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        if depth == 0 and t.startswith(token, i):
            return t[:i].strip(), t[i + len(token):].strip()
        i += 1
    return None


def _parse_hol_expr(s: str):
    t = _strip_outer_paren((s or '').strip())
    low = t.lower()

    # quantifiers
    m = re.match(r'^(forall|exists)\s+([A-Za-z_]\w*)\s+in\s*(\[[^\]]*\]|\([^\)]*\))\s*\.\s*(.+)$', t, re.I)
    if m:
        q, var, dom_txt, body = m.group(1).lower(), m.group(2), m.group(3), m.group(4)
        dom = ast.literal_eval(dom_txt)
        if not isinstance(dom, (list, tuple)):
            raise ValueError('quantifier domain must be list/tuple')
        return ('quant', q, var, list(dom), _parse_hol_expr(body))

    # lambda abstraction
    m = re.match(r'^lambda\s+([A-Za-z_]\w*)\s*\.\s*(.+)$', t, re.I)
    if m:
        return ('lambda', m.group(1), _parse_hol_expr(m.group(2)))

    # implication
    sp = _split_top_expr(t, '->')
    if sp:
        a, b = sp
        return ('or', ('not', _parse_hol_expr(a)), _parse_hol_expr(b))

    # boolean connectives
    for tok, k in [(' and ', 'and'), (' or ', 'or')]:
        sp = _split_top_expr(t, tok)
        if sp:
            a, b = sp
            return (k, _parse_hol_expr(a), _parse_hol_expr(b))

    if low.startswith('not '):
        return ('not', _parse_hol_expr(t[4:].strip()))

    # application: f @ x
    sp = _split_top_expr(t, '@')
    if sp:
        f, a = sp
        return ('app', _parse_hol_expr(f), _parse_hol_expr(a))

    return ('leaf', t)


def _eval_hol_ast(node, env: dict[str, Any]):
    k = node[0]
    if k == 'quant':
        _, q, var, dom, body = node
        vals = []
        for v in dom:
            e2 = dict(env)
            e2[var] = v
            vals.append(bool(_eval_hol_ast(body, e2)))
        return all(vals) if q == 'forall' else any(vals)

    if k == 'lambda':
        _, var, body = node
        return ('closure', var, body, dict(env))

    if k == 'app':
        _, fn, arg = node
        fv = _eval_hol_ast(fn, env)
        av = _eval_hol_ast(arg, env)
        if isinstance(fv, tuple) and len(fv) == 4 and fv[0] == 'closure':
            _, var, body, cenv = fv
            e2 = dict(cenv)
            e2[var] = av
            return _eval_hol_ast(body, e2)
        raise ValueError('application target is not lambda closure')

    if k == 'and':
        return bool(_eval_hol_ast(node[1], env)) and bool(_eval_hol_ast(node[2], env))
    if k == 'or':
        return bool(_eval_hol_ast(node[1], env)) or bool(_eval_hol_ast(node[2], env))
    if k == 'not':
        return not bool(_eval_hol_ast(node[1], env))

    if k == 'leaf':
        t = node[1]
        if re.fullmatch(r'-?\d+', t):
            return int(t)
        if re.fullmatch(r'-?\d+\.\d+', t):
            return float(t)
        tl = t.lower()
        if tl in {'true', 'false'}:
            return tl == 'true'
        if t in env:
            return env[t]
        ev = _eval_symbolic_env(t, env)
        if ev.get('ok'):
            return ev.get('result')
        raise ValueError(ev.get('error', 'leaf eval failed'))

    raise ValueError(f'unsupported hol ast node: {k}')


def solve_hol_lite(expr: str) -> dict[str, Any]:
    """HOL-lite general formula evaluator (typed-lambda style surface).

    Supported:
    - forall x in [1,2,3]. x > 0
    - exists x in [1,2,3]. (x % 2 == 0)
    - (lambda x. x+1) @ 3
    - ((lambda x. lambda y. x+y) @ 2) @ 5
    - forall x in [1,2,3]. ((lambda z. z>0) @ x)
    - formula=(forall x in [1,2,3]. x > 0)
    """
    s = (expr or '').strip()
    try:
        if s.lower().startswith('formula='):
            s = s.split('=', 1)[1].strip()
        astn = _parse_hol_expr(s)
        val = _eval_hol_ast(astn, {})
        return {
            'ok': True,
            'proof_status': 'checked',
            'solver': 'hol-lite',
            'result': val if not (isinstance(val, tuple) and val and val[0] == 'closure') else '<lambda>',
            'ast': str(astn),
            'mode': 'general-formula',
        }
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'hol-lite', 'error': str(e)}


def solve_ctl_lite(expr: str) -> dict[str, Any]:
    """CTL-lite finite model checker (linear Kripke path semantics).

    Supported inputs:
    - formula=AG (p -> AF q); trace=[p,q,q]
    - AG (p -> AF q) @ [p,q,q]
    - legacy: op=AG; atom=p; trace=[p,p,p]
    """
    try:
        s = (expr or '').strip()

        # legacy compatibility
        if 'op=' in s and 'trace=' in s:
            parts = {k.strip().lower(): v.strip() for k, v in [x.split('=', 1) for x in s.split(';') if '=' in x]}
            op = parts.get('op', '').upper()
            atom = parts.get('atom', 'p').strip().lower()
            trace_txt = parts.get('trace', '[]')
            formula = f"{op} {atom}"
        elif '@' in s:
            formula, trace_txt = [x.strip() for x in s.split('@', 1)]
        else:
            parts = {k.strip().lower(): v.strip() for k, v in [x.split('=', 1) for x in s.split(';') if '=' in x]}
            formula = parts.get('formula', parts.get('f', '')).strip()
            trace_txt = parts.get('trace', '[]').strip()
            if not formula:
                return {'ok': False, 'proof_status': 'failed', 'solver': 'ctl-lite', 'error': 'missing formula'}

        trace = _ltl_norm_trace(ast.literal_eval(trace_txt))
        astn = _parse_temporal_formula(formula)
        r = _eval_temporal_ast(astn, trace, 0)
        return {
            'ok': True,
            'proof_status': 'checked',
            'solver': 'ctl-lite',
            'result': bool(r),
            'formula': formula,
            'ast': str(astn),
            'mode': 'model-check',
        }
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'ctl-lite', 'error': str(e)}


def solve_mu_lite(expr: str) -> dict[str, Any]:
    """mu-calculus-lite strict fixed-point checker over finite traces.

    Supported body grammar (lowercase):
    - p | x | ex x | ax x
    - (A and B) | (A or B) | not A
    Example:
    - mu X. (p or ex x); trace=[q,p,p]
    - nu X. (p and ax x); trace=[p,p,p]
    """
    try:
        raw = (expr or '').strip()
        parts = [x.strip() for x in raw.split(';') if x.strip()]
        core = parts[0].lower() if parts else ''
        atom = 'p'
        trace = []
        for p in parts[1:]:
            if '=' not in p:
                continue
            k, v = p.split('=', 1)
            k = k.strip().lower()
            v = v.strip()
            if k == 'atom':
                atom = v.strip().strip('"\'').lower()
            elif k == 'trace':
                if v.startswith('[') and v.endswith(']'):
                    body = v[1:-1].strip()
                    trace = [x.strip().strip('"\'').lower() for x in body.split(',') if x.strip()]
        if not trace:
            return {'ok': False, 'proof_status': 'failed', 'solver': 'mu-lite', 'error': 'trace required'}

        m = re.match(r'^(mu|nu)\s+([a-z_]\w*)\s*\.\s*(.+)$', core)
        if not m:
            return {'ok': False, 'proof_status': 'failed', 'solver': 'mu-lite', 'error': 'unsupported syntax'}
        q, var, body = m.group(1), m.group(2), m.group(3)
        n = len(trace)
        pset = {i for i, x in enumerate(trace) if x == atom}

        def eval_body(X: set[int]) -> set[int]:
            b = body
            # very small evaluator: replace terminals then resolve ex/ax over linear trace
            out = set()
            for i in range(n):
                ctx = b
                ctx = re.sub(rf'\b{re.escape(var)}\b', 'X', ctx)
                ctx = re.sub(r'\bp\b', 'P', ctx)
                # normalize whitespace
                ctx = re.sub(r'\s+', ' ', ctx).strip()

                def atom_val(tok: str) -> bool:
                    t = tok.strip().lower()
                    if t == 'p':
                        return i in pset
                    if t == 'x':
                        return i in X
                    if t == 'ex x':
                        return (i + 1) < n and ((i + 1) in X)
                    if t == 'ax x':
                        return (i + 1) < n and ((i + 1) in X)
                    return False

                # handle simple binary forms first
                t = ctx
                t = t.replace('(', '').replace(')', '')
                if ' and ' in t:
                    a, b2 = [z.strip() for z in t.split(' and ', 1)]
                    v = atom_val(a) and atom_val(b2)
                elif ' or ' in t:
                    a, b2 = [z.strip() for z in t.split(' or ', 1)]
                    v = atom_val(a) or atom_val(b2)
                elif t.startswith('not '):
                    v = not atom_val(t[4:].strip())
                else:
                    v = atom_val(t)
                if v:
                    out.add(i)
            return out

        if q == 'mu':
            X = set()
            while True:
                Xn = eval_body(X)
                if Xn == X:
                    break
                X = Xn
        else:
            X = set(range(n))
            while True:
                Xn = eval_body(X)
                if Xn == X:
                    break
                X = Xn

        return {
            'ok': True,
            'proof_status': 'checked',
            'solver': 'mu-lite',
            'result': (0 in X),
            'fixpoint': q,
            'witness_set': sorted(list(X)),
            'atom': atom,
        }
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'mu-lite', 'error': str(e)}
def solve_nra_lite(expr: str) -> dict[str, Any]:
    """Non-linear arithmetic lite over bounded integer domains.

    Syntax:
    - vars: x in [-5,5], y in [-5,5]; formula: x*x + y*y == 25
    """
    try:
        doms, formula = _parse_smt_lite(expr)
        if not doms:
            return {"ok": False, "proof_status": "failed", "solver": "smt-nra-lite", "error": "no vars/domain"}
        names = list(doms.keys())
        ranges = [range(lo, hi + 1) for (lo, hi) in doms.values()]
        sols = []
        checks = 0
        cand_envs = [{k: int(v) for k, v in zip(names, values)} for values in product(*ranges)]
        cand_envs = _rank_envs_nn_qemu(names, cand_envs)
        for env in cand_envs:
            checks += 1
            ev = _eval_symbolic_env(formula, env)
            if ev.get("ok") and bool(ev.get("result")):
                sols.append(env)
                if len(sols) >= 128:
                    break
        return {
            "ok": True,
            "proof_status": "checked" if checks > 0 else "inconclusive",
            "solver": "smt-nra-lite",
            "solutions": sols,
            "solution_count": len(sols),
            "proof_trace": {"variables": names, "checked_points": checks},
        }
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "solver": "smt-nra-lite", "error": str(e)}


def solve_array_lite(expr: str) -> dict[str, Any]:
    """Array-lite read/write simulation.

    Syntax:
    - size=4; store=1:7,2:9; select=2
    """
    try:
        parts = [x.strip() for x in (expr or '').split(';') if x.strip()]
        kv = {}
        for p2 in parts:
            if '=' in p2:
                k,v = p2.split('=',1)
                kv[k.strip().lower()] = v.strip()
        size = int(kv.get('size','8'))
        arr = [0 for _ in range(max(1,min(1024,size)))]
        for st in [x.strip() for x in kv.get('store','').split(',') if x.strip()]:
            if ':' not in st:
                continue
            i,v = st.split(':',1)
            idx = int(i.strip())
            if 0 <= idx < len(arr):
                arr[idx] = int(v.strip(),0)
        if 'select' in kv:
            idx = int(kv.get('select','0'))
            if 0 <= idx < len(arr):
                return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-array-lite', 'result': arr[idx], 'index': idx}
            return {'ok': False, 'proof_status': 'failed', 'solver': 'smt-array-lite', 'error': 'select out of range'}
        return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-array-lite', 'array_preview': arr[:16]}
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'smt-array-lite', 'error': str(e)}


def solve_uf_lite(expr: str) -> dict[str, Any]:
    """UF-lite consistency checker.

    Syntax example:
    - eq: f(a)=b, f(a)=c, b!=c
    """
    try:
        s = (expr or '').strip().lower()
        if s.startswith('eq:'):
            s = s[3:].strip()
        atoms = [x.strip() for x in s.split(',') if x.strip()]
        fun_map = {}
        neq = []
        for a in atoms:
            if '!=' in a:
                l,r = [x.strip() for x in a.split('!=',1)]
                neq.append((l,r))
                continue
            if '=' in a:
                l,r = [x.strip() for x in a.split('=',1)]
                m = re.match(r'^([a-z_]\w*)\(([^\)]*)\)$', l)
                if m:
                    key = f"{m.group(1)}({m.group(2).strip()})"
                    if key in fun_map and fun_map[key] != r:
                        return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-uf-lite', 'consistent': False, 'conflict': f'{key} -> {fun_map[key]} vs {r}'}
                    fun_map[key] = r
        for l,r in neq:
            if l == r:
                return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-uf-lite', 'consistent': False, 'conflict': f'{l}!={r} impossible'}
        return {'ok': True, 'proof_status': 'checked', 'solver': 'smt-uf-lite', 'consistent': True, 'mapping': fun_map}
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': 'smt-uf-lite', 'error': str(e)}
