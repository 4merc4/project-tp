
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import ast as A
from .. import unparse
from . import terms as T
from .printer import show


@dataclass
class DerivationStep:
    rule: str         
    depth: int
    fragment: str      
    scheme: str      
    term: str = ""    

    def to_dict(self) -> dict:
        return {"rule": self.rule, "depth": self.depth, "fragment": self.fragment,
                "scheme": self.scheme, "term": self.term}


_ARITH = {"+": ("add", "NS_A_Add"), "-": ("sub", "NS_A_Sub"),
          "*": ("mult", "NS_A_Mult"), "div": ("div", "NS_A_Div")}


class Builder:
    def __init__(self) -> None:
        self.steps: list[DerivationStep] = []

    def _step(self, rule: str, depth: int, node: A.Node, scheme: str) -> DerivationStep:
        s = DerivationStep(rule, depth, unparse.short(node), scheme)
        self.steps.append(s)
        return s

    
    def program(self, p: A.Program) -> T.Term:
        step = self._step("NS_Prog", 0, p, "sem_P(begin S end) = sem_S(S)")
        term = self.stmt(p.body, 1)
        step.term = show(term)
        return term

    
    def stmt(self, s: A.Stmt, d: int) -> T.Term:
        if isinstance(s, A.Assign):
            step = self._step("NS_Stm_As", d, s, "sem_S(x := a) = ASˣ(sem_A(a))")
            term: T.Term = T.Assign(s.target, self.expr(s.value, d + 1), s.span)
        elif isinstance(s, A.Seq):
            step = self._step("NS_Stm_Seq", d, s, "sem_S(S₁; S₂) = sem_S(S₁) • sem_S(S₂)")
            term = T.Seq(self.stmt(s.first, d + 1), self.stmt(s.second, d + 1), s.span)
        elif isinstance(s, A.If):
            step = self._step("NS_Stm_If", d, s,
                              "sem_S(if b then S₁ else S₂) = IF(sem_B(b), sem_S(S₁), sem_S(S₂))")
            term = T.If(self.cond(s.cond, d + 1), self.stmt(s.then, d + 1),
                        self.stmt(s.orelse, d + 1), s.span)
        elif isinstance(s, A.While):
            step = self._step("NS_Stm_Wh", d, s, "sem_S(while b do S) = WH(sem_B(b), sem_S(S))")
            term = T.While(self.cond(s.cond, d + 1), self.stmt(s.body, d + 1), s.span)
        elif isinstance(s, A.Block):
            step = self._step("NS_Stm_BE", d, s, "sem_S(begin S end) = sem_S(S)")
            term = self.stmt(s.body, d + 1)
        elif isinstance(s, A.Skip):
            step = self._step("NS_Stm_skip", d, s, "sem_S(skip) = id")
            term = T.Id(s.span)
        else:
            raise TypeError(s)
        step.term = show(term)
        return term

    
    def expr(self, e: A.Expr, d: int) -> T.Term:
        if isinstance(e, A.Num):
            step = self._step("NS_A_Num", d, e, "sem_A(n) = n̄")
            term: T.Term = T.Const(e.value, e.span)
        elif isinstance(e, A.Var):
            step = self._step("NS_A_Var", d, e, "sem_A(x) = x⇒")
            term = T.Deref(e.name, e.span)
        elif isinstance(e, A.BinOp):
            fn, rule = _ARITH[e.op]
            step = self._step(rule, d, e, f"sem_A(a₁ {e.op} a₂) = S²({fn}, sem_A(a₁), sem_A(a₂))")
            term = T.Sup(T.Basic(fn), (self.expr(e.left, d + 1), self.expr(e.right, d + 1)), e.span)
        elif isinstance(e, A.ParenExpr):
            step = self._step("NS_A_Par", d, e, "sem_A((a)) = sem_A(a)")
            term = self.expr(e.inner, d + 1)
        else:
            raise TypeError(e)
        step.term = show(term)
        return term

    
    def cond(self, c: A.Cond, d: int) -> T.Term:
        if isinstance(c, A.Compare):
            fn, rule = ("eq", "NS_B_eq") if c.op == "=" else ("gr", "NS_B_gr")
            step = self._step(rule, d, c, f"sem_B(a₁ {c.op} a₂) = S²({fn}, sem_A(a₁), sem_A(a₂))")
            term: T.Term = T.Sup(T.Basic(fn), (self.expr(c.left, d + 1), self.expr(c.right, d + 1)), c.span)
        elif isinstance(c, A.Or):
            step = self._step("NS_B_or", d, c, "sem_B(b₁ ∨ b₂) = S²(or, sem_B(b₁), sem_B(b₂))")
            term = T.Sup(T.Basic("or"), (self.cond(c.left, d + 1), self.cond(c.right, d + 1)), c.span)
        elif isinstance(c, A.Not):
            step = self._step("NS_B_neg", d, c, "sem_B(¬b) = S¹(neg, sem_B(b))")
            term = T.Sup(T.Basic("neg"), (self.cond(c.operand, d + 1),), c.span)
        elif isinstance(c, A.ParenCond):
            step = self._step("NS_B_Par", d, c, "sem_B((b)) = sem_B(b)")
            term = self.cond(c.inner, d + 1)
        else:
            raise TypeError(c)
        step.term = show(term)
        return term


def build_term(program: A.Program) -> tuple[T.Term, list[DerivationStep]]:
    """Семантичний терм програми """
    b = Builder()
    term = b.program(program)
    return term, b.steps


def semantic_term(program: A.Program) -> T.Term:
    return build_term(program)[0]


def render_derivation(steps: list[DerivationStep]) -> str:
    lines = []
    for s in steps:
        lines.append(f"{'  ' * s.depth}{s.rule}: {s.scheme}")
        lines.append(f"{'  ' * s.depth}    ⟨{s.fragment}⟩  ⇒  {s.term}")
    return "\n".join(lines)
