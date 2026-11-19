"""Динамічний пошук контрприкладів: виконуємо програму на малих вхідних даних.

На відміну від умов верифікації, тут контрприклад *справжній*: програма
реально запускається (через семантичний терм) на стані, що задовольняє
передумову, і або дає результат, що порушує післяумову (спростовує часткову
коректність), або не завершується / не визначена (спростовує повну).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Optional

from .. import ast as A
from ..semantics import evaluate, semantic_term
from .assertions import Pred, eval_pred, pred_vars


@dataclass
class Counterexample:
    kind: str                 
    state_in: dict
    state_out: Optional[dict] = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "state_in": self.state_in,
                "state_out": self.state_out, "reason": self.reason}


@dataclass
class TestOutcome:
    cases: int                
    bound: int
    post_violation: Optional[Counterexample] = None  
    no_termination: Optional[Counterexample] = None  

    def to_dict(self) -> dict:
        return {
            "cases": self.cases, "bound": self.bound,
            "post_violation": self.post_violation.to_dict() if self.post_violation else None,
            "no_termination": self.no_termination.to_dict() if self.no_termination else None,
        }


def input_variables(program: A.Program, pre: Pred) -> list[str]:
    """Змінні, значення яких задає користувач: згадані в передумові
    та ті, що читаються програмою без попереднього присвоєння."""
    assigned = {n.target for n in A.walk(program) if isinstance(n, A.Assign)}
    read: list[str] = []
    for n in A.walk(program):
        if isinstance(n, A.Var) and n.name not in assigned and n.name not in read:
            read.append(n.name)
    for v in pred_vars(pre):
        if v not in read:
            read.append(v)
    return sorted(read)


def _norm(st: dict) -> int:
    return sum(abs(v) for v in st.values())


def find_counterexamples(program: A.Program, pre: Pred, post: Pred, bound: int = 5,
                         run_limit: int = 5_000, max_cases: int = 50_000) -> TestOutcome:
    names = input_variables(program, pre)
    while bound > 1 and (2 * bound + 1) ** len(names) > max_cases:
        bound -= 1
    term = semantic_term(program)
    out = TestOutcome(0, bound)
    for values in itertools.product(range(-bound, bound + 1), repeat=len(names)):
        st = dict(zip(names, values))
        try:
            if not eval_pred(pre, st):
                continue
        except (ZeroDivisionError, KeyError):
            continue
        out.cases += 1
        res = evaluate(term, st, limit=run_limit, trace=False)
        if res.defined:
            try:
                ok = eval_pred(post, res.state)
            except (ZeroDivisionError, KeyError):
                continue
            if not ok and (out.post_violation is None
                           or _norm(st) < _norm(out.post_violation.state_in)):
                out.post_violation = Counterexample("post-violated", st, res.state,
                                                    "програма завершилась, але післяумова хибна")
        else:
            kind = "nonterminating" if res.reason_kind == "limit" else "undefined"
            reason = ("цикл не завершується (перевищено ліміт ітерацій)"
                      if kind == "nonterminating" else (res.reason or "значення не визначене"))
            if out.no_termination is None or _norm(st) < _norm(out.no_termination.state_in):
                out.no_termination = Counterexample(kind, st, None, reason)
    return out
