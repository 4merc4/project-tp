"""Семантичні терми програмної алгебри A_SIPL.

Композиції: суперпозиція Sⁿ, присвоєння ASˣ, послідовне виконання •,
умовний оператор IF, цикл WH, розіменування x⇒, тотожна функція id,
функції-константи n̄. Базові функції: add, sub, mult, div (розширення),
or, neg, eq, gr.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from ..errors import SourceSpan


def _src() -> Optional[SourceSpan]:
    return field(default=None, compare=False, repr=False)


BASIC_ARITY = {"add": 2, "sub": 2, "mult": 2, "div": 2,
               "or": 2, "neg": 1, "eq": 2, "gr": 2}


@dataclass(frozen=True)
class Const:
    """n̄ — функція-константа."""
    value: int
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class Deref:
    """x⇒ — розіменування змінної."""
    name: str
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class Basic:
    """Базова n-арна функція (add, sub, mult, div, or, neg, eq, gr)."""
    name: str
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class Sup:
    """Sⁿ(f, g₁, …, gₙ) — суперпозиція."""
    func: Basic
    args: tuple
    source: Optional[SourceSpan] = _src()

    @property
    def n(self) -> int:
        return len(self.args)


@dataclass(frozen=True)
class Assign:
    """ASˣ(f) — присвоєння."""
    var: str
    func: "Term"
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class Seq:
    """f • g — послідовне виконання."""
    first: "Term"
    second: "Term"
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class If:
    """IF(p, f, g)."""
    cond: "Term"
    then: "Term"
    orelse: "Term"
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class While:
    """WH(p, f)."""
    cond: "Term"
    body: "Term"
    source: Optional[SourceSpan] = _src()


@dataclass(frozen=True)
class Id:
    """id — тотожна функція."""
    source: Optional[SourceSpan] = _src()


Term = Union[Const, Deref, Basic, Sup, Assign, Seq, If, While, Id]


def children(t: Term) -> list:
    if isinstance(t, Sup):
        return [t.func, *t.args]
    if isinstance(t, Assign):
        return [t.func]
    if isinstance(t, Seq):
        return [t.first, t.second]
    if isinstance(t, If):
        return [t.cond, t.then, t.orelse]
    if isinstance(t, While):
        return [t.cond, t.body]
    return []


def to_dict(t: Term) -> dict:
    d: dict = {"type": type(t).__name__}
    if isinstance(t, Const):
        d["value"] = t.value
    elif isinstance(t, (Deref, Basic)):
        d["name"] = t.name
    elif isinstance(t, Assign):
        d["var"] = t.var
    if t.source is not None:
        d["source"] = t.source.to_dict()
    kids = children(t)
    if kids:
        d["children"] = [to_dict(k) for k in kids]
    return d
