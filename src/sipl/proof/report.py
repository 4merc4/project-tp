"""Верифікація: звіт про доведення, контрприклади, пояснення кроків.

Важливо розрізняти два види «негативного» результату:

* умова верифікації не виконується — контрприклад до *анотації* (інваріант
  хибний або надто слабкий); це ще не помилка програми;
* динамічний запуск програми порушив післяумову або не завершився —
  *справжній* контрприклад до коректності програми.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Union

from .. import ast as A
from .. import parse as parse_source
from ..semantics import evaluate, format_state
from ..semantics.builder import Builder
from .assertions import (Pred, eval_pred, parse_assertion_expr, parse_pred, pred_str,
                         pred_vars)
from .solver import Verdict, check_valid
from .testing import TestOutcome, find_counterexamples
from .vcgen import V0, VC, SpecError, generate


@dataclass
class VCResult:
    vc: VC
    verdict: Verdict
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.vc.kind,
            "title": self.vc.title,
            "formula": pred_str(self.vc.formula),
            "loop": self.vc.loop_index,
            "status": self.verdict.status,
            "method": self.verdict.method,
            "counterexample": self.verdict.model,
            "detail": self.verdict.detail,
            "explanation": self.explanation,
        }


@dataclass
class ProofReport:
    pre: Pred
    post: Pred
    invariants: list[Pred]
    variants: list[Optional[A.Expr]]
    results: list[VCResult]
    tests: Optional[TestOutcome] = None

    def _group(self, kinds: set[str]) -> list[VCResult]:
        return [r for r in self.results if r.vc.kind in kinds]

    @property
    def has_variants(self) -> bool:
        n = len(self.invariants)
        return len(self.variants) >= n and all(v is not None for v in self.variants[:n])

    @property
    def partial(self) -> Optional[bool]:
        """True — доведено; False — спростовано запуском програми; None — не встановлено."""
        if self.tests is not None and self.tests.post_violation is not None:
            return False
        rs = self._group({"init", "preserve", "exit", "defined"})
        return True if all(r.verdict.proved for r in rs) else None

    @property
    def total(self) -> Optional[bool]:
        if self.partial is False:
            return False
        if self.tests is not None and self.tests.no_termination is not None:
            return False
        if not self.partial:
            return None
        if self.invariants and not self.has_variants:
            return None
        rs = self._group({"variant-nonneg", "variant-decrease"})
        return True if all(r.verdict.proved for r in rs) else None

    def to_dict(self) -> dict:
        return {
            "pre": pred_str(self.pre), "post": pred_str(self.post),
            "invariants": [pred_str(i) for i in self.invariants],
            "partial_correctness": self.partial,
            "total_correctness": self.total,
            "conditions": [r.to_dict() for r in self.results],
            "dynamic_check": self.tests.to_dict() if self.tests else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def render(self) -> str:
        sym = {"valid": "✔ доведено", "invalid": "✘ не виконується (контрприклад до анотації)",
               "unknown": "? невідомо", "bounded-ok": "≈ контрприкладів не знайдено (перебір, не доведення)"}
        out = [f"Передумова p:  {pred_str(self.pre)}", f"Післяумова q:  {pred_str(self.post)}"]
        for i, inv in enumerate(self.invariants, 1):
            line = f"Інваріант {i}:   {pred_str(inv)}"
            v = self.variants[i - 1] if i - 1 < len(self.variants) else None
            if v is not None:
                from .assertions import expr_str
                line += f"      міра: {expr_str(v)}"
            out.append(line)
        out.append("")
        for n, r in enumerate(self.results, 1):
            out.append(f"[{n}] {r.vc.title}")
            out.append(f"    {pred_str(r.vc.formula)}")
            out.append(f"    {sym[r.verdict.status]}   (метод: {r.verdict.method})")
            if r.verdict.detail:
                out.append(f"    {r.verdict.detail}")
            for line in r.explanation:
                out.append(f"    {line}")
            out.append("")
        if self.tests is not None:
            t = self.tests
            out.append(f"Динамічна перевірка: програму запущено на {t.cases} вхідних станах "
                       f"(|значення| ≤ {t.bound}), що задовольняють передумову.")
            if t.post_violation:
                c = t.post_violation
                out.append(f"  ✘ ПОРУШЕННЯ ПІСЛЯУМОВИ: {format_state(c.state_in)} → {format_state(c.state_out)}")
            if t.no_termination:
                c = t.no_termination
                out.append(f"  ✘ {c.reason}: вхід {format_state(c.state_in)}")
            if not t.post_violation and not t.no_termination:
                out.append("  усі запуски завершились і задовольнили післяумову")
            out.append("")
        word = {True: "ДОВЕДЕНО", False: "СПРОСТОВАНО (реальним запуском програми)", None: "не доведено"}
        out.append(f"Часткова коректність: {word[self.partial]}")
        if self.invariants and not self.has_variants and self.total is None:
            out.append("Повна коректність:    не доведено (не задано міру для кожного циклу)")
        else:
            out.append(f"Повна коректність:    {word[self.total]}")
        return "\n".join(out)




def _explain(vc: VC, verdict: Verdict, program: A.Program) -> list[str]:
    if verdict.status != "invalid" or verdict.model is None:
        return []
    names = sorted(set(pred_vars(vc.formula)) | set(A.variables(program)))
    st = {n: verdict.model.get(n, 0) for n in names if n != V0}
    head = f"Контрприклад: {format_state(st)}"
    if V0 in verdict.model:
        head += f", v₀ = {verdict.model[V0]}"
    lines = [head]
    full = dict(verdict.model)
    for n in names:
        full.setdefault(n, 0)
    try:
        if vc.antecedent is not None and vc.consequent is not None:
            lines.append(f"  припущення «{pred_str(vc.antecedent)}» істинне: "
                         f"{str(eval_pred(vc.antecedent, full)).lower()}")
            lines.append(f"  висновок «{pred_str(vc.consequent)}» істинний: "
                         f"{str(eval_pred(vc.consequent, full)).lower()}")
    except (ZeroDivisionError, KeyError):
        pass
    
    if vc.kind == "preserve" and vc.loop is not None and vc.invariant is not None:
        res = evaluate(Builder().stmt(vc.loop.body, 0), st, trace=False)
        if res.defined:
            try:
                after = str(eval_pred(vc.invariant, res.state)).lower()
            except (ZeroDivisionError, KeyError):
                after = "невизначено"
            lines.append(f"  одна ітерація тіла: {format_state(st)} → {format_state(res.state)}; "
                         f"інваріант після ітерації: {after}")
    return lines




def _parse_variant(v: Union[str, A.Expr, None]) -> Optional[A.Expr]:
    if v is None:
        return None
    if isinstance(v, str):
        if v.strip() in ("", "-", "none", "None"):
            return None
        return parse_assertion_expr(v)
    return v


def verify(program: Union[str, A.Program], pre: Union[str, Pred], post: Union[str, Pred],
           invariants: list[Union[str, Pred]], variants: Optional[list] = None,
           backend: str = "auto", bound: int = 8, test: bool = True,
           test_bound: int = 5) -> ProofReport:
    """Перевіряє {pre} program {post} з інваріантами (та мірами) циклів.

    Кидає `SpecError`, якщо кількість інваріантів не збігається з кількістю циклів.
    """
    prog = parse_source(program) if isinstance(program, str) else program
    pre_p = parse_pred(pre) if isinstance(pre, str) else pre
    post_p = parse_pred(post) if isinstance(post, str) else post
    inv_p = [parse_pred(i) if isinstance(i, str) else i for i in invariants]
    var_p = [_parse_variant(v) for v in (variants or [])]
    vcs = generate(prog, pre_p, post_p, inv_p, var_p)
    results = []
    for vc in vcs:
        verdict = check_valid(vc.formula, backend=backend, bound=bound)
        results.append(VCResult(vc, verdict, _explain(vc, verdict, prog)))
    tests = find_counterexamples(prog, pre_p, post_p, bound=test_bound) if test else None
    return ProofReport(pre_p, post_p, inv_p, var_p, results, tests)
