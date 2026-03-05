from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tempfile
from itertools import product
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


def _ltl_eval_formula(formula: str, trace: list[set[str]], i: int = 0) -> bool:
    s = (formula or "").strip().lower()
    if s in {"true", "⊤"}:
        return True
    if s in {"false", "⊥"}:
        return False
    if s.startswith("g(") and s.endswith(")"):
        inner = s[2:-1]
        return all(_ltl_eval_formula(inner, trace, k) for k in range(i, len(trace)))
    if s.startswith("f(") and s.endswith(")"):
        inner = s[2:-1]
        return any(_ltl_eval_formula(inner, trace, k) for k in range(i, len(trace)))
    if s.startswith("x(") and s.endswith(")"):
        inner = s[2:-1]
        return (i + 1 < len(trace)) and _ltl_eval_formula(inner, trace, i + 1)
    if s.startswith("not(") and s.endswith(")"):
        inner = s[4:-1]
        return not _ltl_eval_formula(inner, trace, i)
    if s.startswith("and(") and s.endswith(")"):
        a, b = _split_top_level(s[4:-1], ",")[:2]
        return _ltl_eval_formula(a, trace, i) and _ltl_eval_formula(b, trace, i)
    if s.startswith("or(") and s.endswith(")"):
        a, b = _split_top_level(s[3:-1], ",")[:2]
        return _ltl_eval_formula(a, trace, i) or _ltl_eval_formula(b, trace, i)
    if s.startswith("u(") and s.endswith(")"):
        a, b = _split_top_level(s[2:-1], ",")[:2]
        for k in range(i, len(trace)):
            if _ltl_eval_formula(b, trace, k):
                return all(_ltl_eval_formula(a, trace, j) for j in range(i, k))
        return False
    # atom
    return i < len(trace) and s in trace[i]


def eval_ltl_lite(expr: str) -> dict[str, Any]:
    """Finite-trace LTL-lite evaluator (KQ-native).

    Supported:
    - legacy: always p @ ["p","p"]
    - model-check style: G(p) @ [["p"],["p"]]
    - operators: G,F,X,U,not,and,or
    """
    s = (expr or "").strip()
    try:
        if "@" not in s:
            return {"ok": False, "error": "ltl syntax requires '@ trace'", "proof_status": "failed"}
        head, trace_txt = [x.strip() for x in s.split("@", 1)]
        trace = _ltl_norm_trace(ast.literal_eval(trace_txt))

        low = head.lower()
        if low.startswith("always "):
            prop = low.replace("always ", "", 1).strip()
            ok = all(prop in step for step in trace)
            return {"ok": True, "result": ok, "operator": "G", "proof_status": "checked", "mode": "legacy"}
        if low.startswith("eventually "):
            prop = low.replace("eventually ", "", 1).strip()
            ok = any(prop in step for step in trace)
            return {"ok": True, "result": ok, "operator": "F", "proof_status": "checked", "mode": "legacy"}
        if " until " in low:
            p, q = [x.strip() for x in low.split(" until ", 1)]
            idx = next((k for k, st in enumerate(trace) if q in st), None)
            ok = False if idx is None else all(p in trace[j] for j in range(idx))
            return {"ok": True, "result": ok, "operator": "U", "proof_status": "checked", "mode": "legacy"}

        ok = _ltl_eval_formula(head, trace, 0)
        return {"ok": True, "result": ok, "operator": "MC", "proof_status": "checked", "mode": "model-check-lite"}
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
    """KQ-native SMT-lite solver (z3-independent).

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
        sols: list[dict[str, int]] = []
        checks = 0
        cand_envs = [{k: int(v) for k, v in zip(names, values)} for values in product(*ranges)]
        cand_envs = _rank_envs_quantum_emu(names, cand_envs)
        for env in cand_envs:
            checks += 1
            ev = _eval_symbolic_env(formula, env)
            if ev.get("ok") and bool(ev.get("result")):
                sols.append(env)
                if len(sols) >= 128:
                    break

        total_space = 1
        for r in ranges:
            total_space *= len(r)
        coverage = min(1.0, checks / max(1, total_space))
        status = "checked" if coverage >= 0.999 else "inconclusive"
        return {
            "ok": True,
            "solver": "smt-kq-native-qemu" if _HAS_QEMU else "smt-kq-native",
            "proof_status": status,
            "solutions": sols,
            "solution_count": len(sols),
            "proof_trace": {
                "mode": "quantum-emu-priority+enumeration+interval-propagation+env-safe-eval" if _HAS_QEMU else "enumeration+interval-propagation+env-safe-eval",
                "variables": names,
                "search_space": int(total_space),
                "checked_points": int(checks),
                "coverage": round(float(coverage), 4),
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

        trace = {"decisions": 0, "conflicts": 0, "backjumps": 0, "checked_points": 0}
        learned_clauses: list[str] = []

        ranked_vars = vars_list[:]
        if _HAS_QEMU:
            probe = [{k: False for k in vars_list}, {k: True for k in vars_list}]
            ranked_env = _rank_envs_quantum_emu(vars_list, probe)
            ranked_vars = [k for k in vars_list if ranked_env and ranked_env[0].get(k, False)] + [k for k in vars_list if not (ranked_env and ranked_env[0].get(k, False))]

        def dpll(env: dict[str, bool], level: int = 0):
            trace["checked_points"] += 1
            # unit propagation
            changed = True
            while changed:
                changed = False
                for cl in clauses:
                    st = _clause_state(cl, env)
                    if st == -1:
                        trace["conflicts"] += 1
                        return None
                    if st == 0:
                        un = [(v, sign) for v, sign in cl if v not in env]
                        if len(un) == 1:
                            v, sign = un[0]
                            env[v] = sign
                            changed = True

            if all(_clause_state(cl, env) == 1 for cl in clauses):
                return dict(env)

            # pick next variable
            v = next((x for x in ranked_vars if x not in env), None)
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
                "solver": "sat-lite-qemu" if _HAS_QEMU else "sat-lite",
                "satisfiable": True,
                "model": sat_model,
                "proof_trace": {
                    "variables": vars_list,
                    "mode": "cdcl-lite+qemu-priority" if _HAS_QEMU else "cdcl-lite",
                    "watched_literals_init": watched_literals,
                    "learned_clauses": learned_clauses,
                    **trace,
                },
            }

        core = clauses[:]
        changed = True
        while changed and len(core) > 1:
            changed = False
            i = 0
            while i < len(core):
                trial = core[:i] + core[i + 1 :]
                sat = False
                for bits in product([False, True], repeat=len(vars_list)):
                    env = {k: b for k, b in zip(vars_list, bits)}
                    if all(any((env.get(v, False) is sign) for v, sign in cl) for cl in trial):
                        sat = True
                        break
                if not sat:
                    core = trial
                    changed = True
                else:
                    i += 1
        core_txt = [" or ".join([(v if sign else f"not {v}") for v, sign in cl]) for cl in core]

        unit_pos = {cl[0][0] for cl in core if len(cl) == 1 and cl[0][1] is True}
        unit_neg = {cl[0][0] for cl in core if len(cl) == 1 and cl[0][1] is False}
        for v in sorted(unit_pos & unit_neg):
            learned_clauses.append(f"conflict({v})")

        return {
            "ok": True,
            "proof_status": "checked",
            "solver": "sat-lite-qemu" if _HAS_QEMU else "sat-lite",
            "satisfiable": False,
            "unsat_core_lite": core_txt,
            "proof_trace": {
                "variables": vars_list,
                "core_size": len(core_txt),
                "mode": "cdcl-lite+qemu-priority" if _HAS_QEMU else "cdcl-lite",
                "watched_literals_init": watched_literals,
                "learned_clauses": learned_clauses,
                **trace,
            },
        }
    except Exception as e:
        return {"ok": False, "proof_status": "failed", "error": str(e), "solver": "sat-lite"}
