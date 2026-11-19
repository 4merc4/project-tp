"""Типізоване абстрактне синтаксичне дерево SIPL.

Вузли — власні незмінні dataclass-и. Позиція (`span`) не бере участі в
порівнянні, тому дерева можна порівнювати за структурою.
Дужки (`ParenExpr`, `ParenCond`) збережені, щоб відповідати правилам
NS_A_Par / NS_B_Par із таблиці 1.6 посібника.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from .errors import SourceSpan


def _span() -> Optional[SourceSpan]:
    return field(default=None, compare=False, repr=False)




@dataclass(frozen=True)
class Num:
    value: int
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Var:
    name: str
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class BinOp:
    op: str  
    left: "Expr"
    right: "Expr"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class ParenExpr:
    inner: "Expr"
    span: Optional[SourceSpan] = _span()


Expr = Union[Num, Var, BinOp, ParenExpr]




@dataclass(frozen=True)
class Compare:
    op: str  
    left: Expr
    right: Expr
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Or:
    left: "Cond"
    right: "Cond"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Not:
    operand: "Cond"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class ParenCond:
    inner: "Cond"
    span: Optional[SourceSpan] = _span()


Cond = Union[Compare, Or, Not, ParenCond]




@dataclass(frozen=True)
class Assign:
    target: str
    value: Expr
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Seq:
    first: "Stmt"
    second: "Stmt"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class If:
    cond: Cond
    then: "Stmt"
    orelse: "Stmt"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class While:
    cond: Cond
    body: "Stmt"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Block:
    body: "Stmt"
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Skip:
    span: Optional[SourceSpan] = _span()


Stmt = Union[Assign, Seq, If, While, Block, Skip]


@dataclass(frozen=True)
class Program:
    body: Stmt
    span: Optional[SourceSpan] = _span()


Node = Union[Program, Stmt, Expr, Cond]


def children(node: Node) -> list[Node]:
    """Прямі нащадки вузла (в порядку тексту)."""
    if isinstance(node, Program):
        return [node.body]
    if isinstance(node, Assign):
        return [node.value]
    if isinstance(node, Seq):
        return [node.first, node.second]
    if isinstance(node, If):
        return [node.cond, node.then, node.orelse]
    if isinstance(node, While):
        return [node.cond, node.body]
    if isinstance(node, Block):
        return [node.body]
    if isinstance(node, BinOp):
        return [node.left, node.right]
    if isinstance(node, (ParenExpr, ParenCond)):
        return [node.inner]
    if isinstance(node, Compare):
        return [node.left, node.right]
    if isinstance(node, Or):
        return [node.left, node.right]
    if isinstance(node, Not):
        return [node.operand]
    return []


def walk(node: Node):
    """Обхід у глибину (спочатку батько)."""
    yield node
    for c in children(node):
        yield from walk(c)


def variables(node: Node) -> list[str]:
    """Імена змінних у порядку першої появи."""
    seen: list[str] = []
    for n in walk(node):
        name = n.name if isinstance(n, Var) else n.target if isinstance(n, Assign) else None
        if name is not None and name not in seen:
            seen.append(name)
    return seen


def to_dict(node: Node) -> dict:
    """Серіалізація AST у JSON-подібну структуру."""
    d: dict = {"type": type(node).__name__}
    if isinstance(node, Num):
        d["value"] = node.value
    elif isinstance(node, Var):
        d["name"] = node.name
    elif isinstance(node, Assign):
        d["target"] = node.target
    elif isinstance(node, (BinOp, Compare)):
        d["op"] = node.op
    if node.span is not None:
        d["span"] = node.span.to_dict()
    kids = children(node)
    if kids:
        d["children"] = [to_dict(k) for k in kids]
    return d
