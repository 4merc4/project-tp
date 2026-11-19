"""Перевірка загальнозначущості умов верифікації.

Основний бекенд — SMT-розв'язувач Z3 (цілочисельна арифметика): він або
доводить формулу, або видає контрприклад. Якщо Z3 не встановлено, діє
запасний бекенд — повний перебір значень у скінченному діапазоні, який
може лише *спростувати* формулу (знайти контрприклад) або повідомити, що
контрприкладів у межах діапазону немає (це не доведення).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Optional

from .. import ast as A
from .assertions import (PAnd, PCmp, PFalse, PImp, PNot, POr, PTrue, Pred, eval_pred,
                         pred_vars)

try: 
    import z3 
    HAVE_Z3 = True
except Exception:  
    z3 = None
    HAVE_Z3 = False


@dataclass
class Verdict:
    status: str                      
    method: str                    
    model: Optional[dict] = None   
    detail: str = ""

    @property
    def proved(self) -> bool:
        return self.status == "valid"

    def to_dict(self) -> dict:
        return {"status": self.status, "method": self.method,
                "model": self.model, "detail": self.detail}




def _z3_expr(e: A.Expr, vars_: dict):
    if isinstance(e, A.Num):
        return z3.IntVal(e.value)
    if isinstance(e, A.Var):
        return vars_.setdefault(e.name, z3.Int(e.name))
    a, b = _z3_expr(e.left, vars_), _z3_expr(e.right, vars_)
    if e.op == "+":
        return a + b
    if e.op == "-":
        return a - b
    if e.op == "*":
        return a * b
    return a / b 


def _z3_pred(p: Pred, vars_: dict):
    if isinstance(p, PTrue):
        return z3.BoolVal(True)
    if isinstance(p, PFalse):
        return z3.BoolVal(False)
    if isinstance(p, PCmp):
        a, b = _z3_expr(p.left, vars_), _z3_expr(p.right, vars_)
        return {"=": a == b, "!=": a != b, "<": a < b, "<=": a <= b,
                ">": a > b, ">=": a >= b}[p.op]
    if isinstance(p, PNot):
        return z3.Not(_z3_pred(p.operand, vars_))
    if isinstance(p, PAnd):
        return z3.And(_z3_pred(p.left, vars_), _z3_pred(p.right, vars_))
    if isinstance(p, POr):
        return z3.Or(_z3_pred(p.left, vars_), _z3_pred(p.right, vars_))
    return z3.Implies(_z3_pred(p.left, vars_), _z3_pred(p.right, vars_))


def _check_z3(formula: Pred, timeout_ms: int) -> Verdict:
    vars_: dict = {}
    f = _z3_pred(formula, vars_)
    s = z3.Solver()
    s.set("timeout", timeout_ms)
    s.add(z3.Not(f))
    r = s.check()
    if r == z3.unsat:
        return Verdict("valid", "z3")
    if r == z3.sat:
        m = s.model()
        model = {name: m.eval(v, model_completion=True).as_long() for name, v in vars_.items()}
        return Verdict("invalid", "z3", model)
    return Verdict("unknown", "z3", None, "Z3 не зміг вирішити (таймаут або нелінійна арифметика)")




def _check_bounded(formula: Pred, bound: int, max_cases: int = 400_000) -> Verdict:
    names = pred_vars(formula)
    rng = range(-bound, bound + 1)
    total = len(rng) ** len(names)
    if total > max_cases:
        
        while bound > 1 and (2 * bound + 1) ** len(names) > max_cases:
            bound -= 1
        rng = range(-bound, bound + 1)
    skipped = 0
    for values in itertools.product(rng, repeat=len(names)):
        st = dict(zip(names, values))
        try:
            ok = eval_pred(formula, st)
        except (ZeroDivisionError, KeyError):
            skipped += 1
            continue
        if not ok:
            return Verdict("invalid", "bounded", st)
    return Verdict("bounded-ok", "bounded", None,
                   f"контрприкладів не знайдено для значень змінних від {-bound} до {bound} "
                   "(це не доведення)")


def check_valid(formula: Pred, backend: str = "auto", bound: int = 8,
                timeout_ms: int = 10_000) -> Verdict:
    """Чи є формула тотожно істинною на цілих числах.

    backend: 'auto' (Z3, якщо є), 'z3', 'bounded'.
    """
    if backend not in ("auto", "z3", "bounded"):
        raise ValueError("backend має бути auto, z3 або bounded")
    if backend == "z3" and not HAVE_Z3:
        raise RuntimeError("Z3 не встановлено: pip install z3-solver")
    if backend == "bounded" or (backend == "auto" and not HAVE_Z3):
        return _check_bounded(formula, bound)
    return _check_z3(formula, timeout_ms)
