"""Генерація умов верифікації (VC) для програм SIPL.

Метод — найслабша передумова (wp) з анотованими інваріантами циклів.
Для циклу `while b do S` з інваріантом I і (необов'язковою) мірою V:

* preserve:  I ∧ b ⇒ wp(S, I)            — інваріант зберігається тілом;
* exit:      I ∧ ¬b ⇒ Q                  — вихід з циклу дає післяумову;
* defined:   I ⇒ def(b)                  — умова циклу визначена;
* variant-nonneg:    I ∧ b ⇒ V ≥ 0        — міра невід'ємна;
* variant-decrease:  I ∧ b ∧ V = v₀ ⇒ wp(S, V < v₀) — міра строго спадає.

Ініціалізація: `p ⇒ wp(програма до циклу, I)`. Разом preserve, exit та init
дають часткову коректність, а з мірою — повну (теореми 1 і 2 лаби 3).
Визначеність ділення: для `a div d` вимагається d > 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import ast as A
from .assertions import (PAnd, PCmp, PImp, PNot, PTrue, Pred, conj, norm_expr, simplify,
                         subst)

V0 = "_v0"  


@dataclass
class VC:
    kind: str                    
    title: str
    formula: Pred
    loop_index: Optional[int] = None
    loop: Optional[A.While] = None
    
    antecedent: Optional[Pred] = None
    consequent: Optional[Pred] = None
    invariant: Optional[Pred] = None


class SpecError(ValueError):
    """Помилка в специфікації (наприклад, не вистачає інваріанта)."""




def cond_to_pred(c: A.Cond) -> Pred:
    from .assertions import POr
    if isinstance(c, A.Compare):
        return PCmp(c.op, norm_expr(c.left), norm_expr(c.right))
    if isinstance(c, A.Or):
        return POr(cond_to_pred(c.left), cond_to_pred(c.right))
    if isinstance(c, A.Not):
        return PNot(cond_to_pred(c.operand))
    return cond_to_pred(c.inner)


def expr_defs(e: A.Expr) -> list[Pred]:
    """Умови визначеності виразу: дільники div мають бути додатними."""
    if isinstance(e, A.BinOp):
        out = expr_defs(e.left) + expr_defs(e.right)
        if e.op == "div":
            out.append(PCmp(">", norm_expr(e.right), A.Num(0)))
        return out
    if isinstance(e, A.ParenExpr):
        return expr_defs(e.inner)
    return []


def cond_defs(c: A.Cond) -> list[Pred]:
    if isinstance(c, A.Compare):
        return expr_defs(c.left) + expr_defs(c.right)
    if isinstance(c, A.Or):
        return cond_defs(c.left) + cond_defs(c.right)
    if isinstance(c, A.Not):
        return cond_defs(c.operand)
    return cond_defs(c.inner)


def loops_in_order(node: A.Node) -> list[A.While]:
    """Цикли програми в порядку появи в тексті (зовнішній — перед вкладеним)."""
    return [n for n in A.walk(node) if isinstance(n, A.While)]


class VCGen:
    def __init__(self, program: A.Program, invariants: list[Pred],
                 variants: list[Optional[A.Expr]]) -> None:
        self.loops = loops_in_order(program)
        if len(invariants) != len(self.loops):
            raise SpecError(
                f"у програмі {len(self.loops)} цикл(ів), а інваріантів задано {len(invariants)}: "
                "для кожного циклу (в порядку появи в тексті) потрібен інваріант")
        self.inv = {id(l): invariants[i] for i, l in enumerate(self.loops)}
        self.index = {id(l): i for i, l in enumerate(self.loops)}
        padded = list(variants) + [None] * (len(self.loops) - len(variants))
        self.var = {id(l): padded[i] for i, l in enumerate(self.loops)}
        self.vcs: list[VC] = []

    def _add(self, kind: str, title: str, ante: Pred, cons: Pred, loop: A.While) -> None:
        self.vcs.append(VC(kind, title, PImp(ante, cons), self.index[id(loop)], loop, ante, cons,
                           self.inv[id(loop)]))

    def wp(self, s: A.Stmt, q: Pred, emit: bool = True) -> Pred:
        if isinstance(s, A.Skip):
            return q
        if isinstance(s, A.Assign):
            body = subst(q, s.target, norm_expr(s.value))
            return conj([*expr_defs(s.value), body])
        if isinstance(s, A.Seq):
            return self.wp(s.first, self.wp(s.second, q, emit), emit)
        if isinstance(s, A.Block):
            return self.wp(s.body, q, emit)
        if isinstance(s, A.If):
            c = cond_to_pred(s.cond)
            then = self.wp(s.then, q, emit)
            els = self.wp(s.orelse, q, emit)
            return conj([*cond_defs(s.cond), PAnd(PImp(c, then), PImp(PNot(c), els))])
        if isinstance(s, A.While):
            i = self.inv[id(s)]
            b = cond_to_pred(s.cond)
            if emit:
                n = self.index[id(s)] + 1
                body_wp = self.wp(s.body, i, True)
                self._add("preserve", f"Цикл {n}: інваріант зберігається тілом циклу",
                          PAnd(i, b), body_wp, s)
                self._add("exit", f"Цикл {n}: вихід з циклу дає післяумову",
                          PAnd(i, PNot(b)), q, s)
                defs = conj(cond_defs(s.cond))
                if not isinstance(defs, PTrue):
                    self._add("defined", f"Цикл {n}: умова циклу визначена", i, defs, s)
                v = self.var[id(s)]
                if v is not None:
                    v = norm_expr(v)
                    self._add("variant-nonneg", f"Цикл {n}: міра невід'ємна",
                              PAnd(i, b), PCmp(">=", v, A.Num(0)), s)
                    dec = self.wp(s.body, PCmp("<", v, A.Var(V0)), False)
                    self._add("variant-decrease", f"Цикл {n}: міра строго спадає на кожній ітерації",
                              PAnd(PAnd(i, b), PCmp("=", v, A.Var(V0))), dec, s)
            return i
        raise TypeError(s)


def generate(program: A.Program, pre: Pred, post: Pred, invariants: list[Pred],
             variants: Optional[list[Optional[A.Expr]]] = None) -> list[VC]:
    """Усі умови верифікації для трійки {pre} програма {post}."""
    gen = VCGen(program, invariants, variants or [])
    w = gen.wp(program.body, post, True)
    first = VC("init", "Ініціалізація: передумова встановлює інваріант (і визначеність)",
               PImp(pre, w), None, None, pre, w)
    
    gen.vcs.insert(0, first)
    order = ["init", "preserve", "exit", "defined", "variant-nonneg", "variant-decrease"]
    gen.vcs.sort(key=lambda v: (-1 if v.loop_index is None else v.loop_index, order.index(v.kind)))
    for vc in gen.vcs:
        vc.formula = simplify(vc.formula)
        if vc.antecedent is not None:
            vc.antecedent = simplify(vc.antecedent)
        if vc.consequent is not None:
            vc.consequent = simplify(vc.consequent)
    return gen.vcs
