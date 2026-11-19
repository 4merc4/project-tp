"""Перетворення дерева виводу (конкретний синтаксис) у AST."""
from __future__ import annotations

from . import ast as A
from .parse_tree import PNode


def _expr(n: PNode) -> A.Expr:
    r = n.rule
    if r == "NA1":
        return A.Num(int(n.children[0].children[0].symbol), n.span)
    if r == "NA2":
        return A.Var(n.children[0].children[0].symbol, n.span)
    if r in ("NA3", "NA4", "NA5", "NA7"):
        op = {"NA3": "+", "NA4": "-", "NA5": "*", "NA7": "div"}[r]
        return A.BinOp(op, _expr(n.children[0]), _expr(n.children[2]), n.span)
    if r == "NA6":
        return A.ParenExpr(_expr(n.children[1]), n.span)
    raise ValueError(f"невідоме правило виразу {r}")


def _cond(n: PNode) -> A.Cond:
    r = n.rule
    if r in ("NB1", "NB2"):
        op = "=" if r == "NB1" else ">"
        return A.Compare(op, _expr(n.children[0]), _expr(n.children[2]), n.span)
    if r == "NB3":
        return A.Or(_cond(n.children[0]), _cond(n.children[2]), n.span)
    if r == "NB4":
        return A.Not(_cond(n.children[1]), n.span)
    if r == "NB5":
        return A.ParenCond(_cond(n.children[1]), n.span)
    raise ValueError(f"невідоме правило умови {r}")


def _stmt(n: PNode) -> A.Stmt:
    r = n.rule
    c = n.children
    if r == "NS1":
        return A.Assign(c[0].children[0].symbol, _expr(c[2]), n.span)
    if r == "NS2":
        return A.Seq(_stmt(c[0]), _stmt(c[2]), n.span)
    if r == "NS3":
        return A.If(_cond(c[1]), _stmt(c[3]), _stmt(c[5]), n.span)
    if r == "NS4":
        return A.While(_cond(c[1]), _stmt(c[3]), n.span)
    if r == "NS5":
        return A.Block(_stmt(c[1]), n.span)
    if r == "NS6":
        return A.Skip(n.span)
    raise ValueError(f"невідоме правило оператора {r}")


def build_ast(tree: PNode) -> A.Program:
    """AST програми з дерева виводу (корінь — правило NP1)."""
    if tree.rule != "NP1":
        raise ValueError("очікувався корінь <програма>")
    return A.Program(_stmt(tree.children[1]), tree.span)
