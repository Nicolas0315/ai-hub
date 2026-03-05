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
        return {"ok": True, "result": val, "type": type(val).__name__}
    except Exception as e:
        return {"ok": False, "error": str(e)}
