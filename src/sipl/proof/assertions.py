"""Мова тверджень для передумов, післяумов та інваріантів.

Вирази — ті самі, що в SIPL (`+ - * div`, змінні, числа), порівняння
`= != < <= > >=`, зв'язки `∧ ∨ ¬ ⇒` (також `and or not =>`), константи
`true`/`false`. Твердження — це не частина мови SIPL, а метамова для
доведень (за аналогією з логікою Флойда–Гоара).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from .. import ast as A
from ..errors import SiplError


class AssertionSyntaxError(SiplError):
    def __init__(self, message: str, text: str, col: int) -> None:
        super().__init__(f"{message} (позиція {col + 1} у «{text}»)")
        self.text = text
        self.col = col




@dataclass(frozen=True)
class PTrue:
    pass


@dataclass(frozen=True)
class PFalse:
    pass


@dataclass(frozen=True)
class PCmp:
    op: str  
    left: A.Expr
    right: A.Expr


@dataclass(frozen=True)
class PNot:
    operand: "Pred"


@dataclass(frozen=True)
class PAnd:
    left: "Pred"
    right: "Pred"


@dataclass(frozen=True)
class POr:
    left: "Pred"
    right: "Pred"


@dataclass(frozen=True)
class PImp:
    left: "Pred"
    right: "Pred"


Pred = Union[PTrue, PFalse, PCmp, PNot, PAnd, POr, PImp]


def conj(items: list[Pred]) -> Pred:
    out: Pred = PTrue()
    for it in items:
        out = it if isinstance(out, PTrue) else PAnd(out, it)
    return out




def norm_expr(e: A.Expr) -> A.Expr:
    """Прибирає дужки AST (`ParenExpr`)."""
    if isinstance(e, A.ParenExpr):
        return norm_expr(e.inner)
    if isinstance(e, A.BinOp):
        return A.BinOp(e.op, norm_expr(e.left), norm_expr(e.right))
    if isinstance(e, A.Num):
        return A.Num(e.value)
    return A.Var(e.name)


_PREC = {"+": 1, "-": 1, "*": 2, "div": 2}


def expr_str(e: A.Expr) -> str:
    if isinstance(e, A.Num):
        return str(e.value) if e.value >= 0 else f"({e.value})"
    if isinstance(e, A.Var):
        return e.name
    if isinstance(e, A.ParenExpr):
        return expr_str(e.inner)
    p = _PREC[e.op]

    def side(c: A.Expr, right: bool) -> str:
        s = expr_str(c)
        if isinstance(c, A.BinOp):
            cp = _PREC[c.op]
            if cp < p or (right and cp == p):
                return f"({s})"
        return s

    return f"{side(e.left, False)} {e.op} {side(e.right, True)}"


def subst_expr(e: A.Expr, var: str, repl: A.Expr) -> A.Expr:
    if isinstance(e, A.Var):
        return repl if e.name == var else e
    if isinstance(e, A.BinOp):
        return A.BinOp(e.op, subst_expr(e.left, var, repl), subst_expr(e.right, var, repl))
    return e


def expr_vars(e: A.Expr, acc: list[str] | None = None) -> list[str]:
    acc = [] if acc is None else acc
    if isinstance(e, A.Var) and e.name not in acc:
        acc.append(e.name)
    elif isinstance(e, A.BinOp):
        expr_vars(e.left, acc)
        expr_vars(e.right, acc)
    return acc


def eval_expr(e: A.Expr, st: dict) -> int:
    if isinstance(e, A.Num):
        return e.value
    if isinstance(e, A.Var):
        return st[e.name]
    a, b = eval_expr(e.left, st), eval_expr(e.right, st)
    if e.op == "+":
        return a + b
    if e.op == "-":
        return a - b
    if e.op == "*":
        return a * b
    if b == 0:
        raise ZeroDivisionError
    return a // b




_PRED_PREC = {PImp: 0, POr: 1, PAnd: 2, PNot: 3}


def pred_str(p: Pred, parent: int = -1) -> str:
    if isinstance(p, PTrue):
        return "true"
    if isinstance(p, PFalse):
        return "false"
    if isinstance(p, PCmp):
        sym = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥"}[p.op]
        return f"{expr_str(p.left)} {sym} {expr_str(p.right)}"
    prec = _PRED_PREC[type(p)]
    if isinstance(p, PNot):
        s = "¬" + pred_str(p.operand, prec)
    elif isinstance(p, PAnd):
        s = f"{pred_str(p.left, prec)} ∧ {pred_str(p.right, prec + 1)}"
    elif isinstance(p, POr):
        s = f"{pred_str(p.left, prec)} ∨ {pred_str(p.right, prec + 1)}"
    else:
        s = f"{pred_str(p.left, prec + 1)} ⇒ {pred_str(p.right, prec)}"
    return f"({s})" if prec < parent else s


def subst(p: Pred, var: str, repl: A.Expr) -> Pred:
    if isinstance(p, PCmp):
        return PCmp(p.op, subst_expr(p.left, var, repl), subst_expr(p.right, var, repl))
    if isinstance(p, PNot):
        return PNot(subst(p.operand, var, repl))
    if isinstance(p, (PAnd, POr, PImp)):
        return type(p)(subst(p.left, var, repl), subst(p.right, var, repl))
    return p


def pred_vars(p: Pred, acc: list[str] | None = None) -> list[str]:
    acc = [] if acc is None else acc
    if isinstance(p, PCmp):
        expr_vars(p.left, acc)
        expr_vars(p.right, acc)
    elif isinstance(p, PNot):
        pred_vars(p.operand, acc)
    elif isinstance(p, (PAnd, POr, PImp)):
        pred_vars(p.left, acc)
        pred_vars(p.right, acc)
    return acc


def eval_pred(p: Pred, st: dict) -> bool:
    """Значення твердження в стані. Кидає ZeroDivisionError/KeyError при невизначеності."""
    if isinstance(p, PTrue):
        return True
    if isinstance(p, PFalse):
        return False
    if isinstance(p, PCmp):
        a, b = eval_expr(p.left, st), eval_expr(p.right, st)
        return {"=": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[p.op]
    if isinstance(p, PNot):
        return not eval_pred(p.operand, st)
    if isinstance(p, PAnd):
        return eval_pred(p.left, st) and eval_pred(p.right, st)
    if isinstance(p, POr):
        return eval_pred(p.left, st) or eval_pred(p.right, st)
    return (not eval_pred(p.left, st)) or eval_pred(p.right, st)


def simplify(p: Pred) -> Pred:
    """Легке спрощення (константи, тривіальні порівняння) для читабельності."""
    if isinstance(p, PCmp):
        if p.left == p.right:
            return PTrue() if p.op in ("=", "<=", ">=") else PFalse()
        if isinstance(p.left, A.Num) and isinstance(p.right, A.Num):
            return PTrue() if eval_pred(p, {}) else PFalse()
        return p
    if isinstance(p, PNot):
        inner = simplify(p.operand)
        if isinstance(inner, PTrue):
            return PFalse()
        if isinstance(inner, PFalse):
            return PTrue()
        if isinstance(inner, PNot):
            return inner.operand
        return PNot(inner)
    if isinstance(p, PAnd):
        l, r = simplify(p.left), simplify(p.right)
        if isinstance(l, PFalse) or isinstance(r, PFalse):
            return PFalse()
        if isinstance(l, PTrue):
            return r
        if isinstance(r, PTrue) or l == r:
            return l
        return PAnd(l, r)
    if isinstance(p, POr):
        l, r = simplify(p.left), simplify(p.right)
        if isinstance(l, PTrue) or isinstance(r, PTrue):
            return PTrue()
        if isinstance(l, PFalse):
            return r
        if isinstance(r, PFalse) or l == r:
            return l
        return POr(l, r)
    if isinstance(p, PImp):
        l, r = simplify(p.left), simplify(p.right)
        if isinstance(l, PTrue):
            return r
        if isinstance(l, PFalse) or isinstance(r, PTrue) or l == r:
            return PTrue()
        return PImp(l, r)
    return p




_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<id>[A-Za-z_][A-Za-z_0-9]*)|"
    r"(?P<op>=>|->|→|⇒|<=|≤|>=|≥|!=|≠|==|&&|∧|\|\||∨|[=<>!¬+\-*–∗()|&]))")

_KW = {"and": "AND", "or": "OR", "not": "NOT", "true": "TRUE", "false": "FALSE", "div": "DIV"}
_OPS = {
    "=>": "IMP", "->": "IMP", "→": "IMP", "⇒": "IMP",
    "<=": "LE", "≤": "LE", ">=": "GE", "≥": "GE", "!=": "NE", "≠": "NE",
    "==": "EQ", "=": "EQ", "<": "LT", ">": "GT",
    "&&": "AND", "∧": "AND", "&": "AND", "||": "OR", "∨": "OR", "|": "OR",
    "!": "NOT", "¬": "NOT", "+": "PLUS", "-": "MINUS", "–": "MINUS",
    "*": "STAR", "∗": "STAR", "(": "LPAR", ")": "RPAR",
}
_CMP = {"EQ": "=", "NE": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}


class _P:
    def __init__(self, text: str) -> None:
        self.text = text
        self.toks: list[tuple[str, str, int]] = []
        pos = 0
        while pos < len(text):
            if text[pos:].strip() == "":
                break
            m = _TOKEN.match(text, pos)
            if not m:
                bad = pos + (len(text[pos:]) - len(text[pos:].lstrip()))
                raise AssertionSyntaxError(f"невідомий символ {text[bad]!r}", text, bad)
            start = m.start(m.lastgroup)
            if m.lastgroup == "num":
                self.toks.append(("NUM", m.group("num"), start))
            elif m.lastgroup == "id":
                w = m.group("id")
                self.toks.append((_KW.get(w, "ID"), w, start))
            else:
                self.toks.append((_OPS[m.group("op")], m.group("op"), start))
            pos = m.end()
        self.toks.append(("EOF", "", len(text)))
        self.i = 0

    @property
    def kind(self) -> str:
        return self.toks[self.i][0]

    def fail(self, what: str) -> AssertionSyntaxError:
        k, txt, col = self.toks[self.i]
        found = "кінець тексту" if k == "EOF" else f"«{txt}»"
        return AssertionSyntaxError(f"очікувалось {what}, знайдено {found}", self.text, col)

    def take(self) -> tuple[str, str, int]:
        t = self.toks[self.i]
        self.i += 1
        return t

    
    def pred(self) -> Pred:
        left = self.disj()
        if self.kind == "IMP":
            self.take()
            return PImp(left, self.pred())
        return left

    def disj(self) -> Pred:
        left = self.conj_()
        while self.kind == "OR":
            self.take()
            left = POr(left, self.conj_())
        return left

    def conj_(self) -> Pred:
        left = self.neg()
        while self.kind == "AND":
            self.take()
            left = PAnd(left, self.neg())
        return left

    def neg(self) -> Pred:
        if self.kind == "NOT":
            self.take()
            return PNot(self.neg())
        return self.atom()

    def atom(self) -> Pred:
        if self.kind == "TRUE":
            self.take()
            return PTrue()
        if self.kind == "FALSE":
            self.take()
            return PFalse()
        if self.kind == "LPAR":
            save = self.i
            try:
                return self.cmp()
            except AssertionSyntaxError as first:
                self.i = save
                try:
                    self.take()
                    p = self.pred()
                    if self.kind != "RPAR":
                        raise self.fail("')'")
                    self.take()
                    return p
                except AssertionSyntaxError as second:
                    raise second if second.col >= first.col else first
        return self.cmp()

    def cmp(self) -> Pred:
        left = self.expr()
        if self.kind not in _CMP:
            raise self.fail("порівняння (=, ≠, <, ≤, >, ≥)")
        op = _CMP[self.take()[0]]
        return PCmp(op, left, self.expr())

   
    def expr(self) -> A.Expr:
        left = self.term()
        while self.kind in ("PLUS", "MINUS"):
            op = "+" if self.take()[0] == "PLUS" else "-"
            left = A.BinOp(op, left, self.term())
        return left

    def term(self) -> A.Expr:
        left = self.unary()
        while self.kind in ("STAR", "DIV"):
            op = "*" if self.take()[0] == "STAR" else "div"
            left = A.BinOp(op, left, self.unary())
        return left

    def unary(self) -> A.Expr:
        if self.kind == "MINUS":
            self.take()
            inner = self.unary()
            if isinstance(inner, A.Num):
                return A.Num(-inner.value)
            return A.BinOp("-", A.Num(0), inner)
        return self.primary()

    def primary(self) -> A.Expr:
        k = self.kind
        if k == "NUM":
            return A.Num(int(self.take()[1]))
        if k == "ID":
            return A.Var(self.take()[1])
        if k == "LPAR":
            self.take()
            e = self.expr()
            if self.kind != "RPAR":
                raise self.fail("')'")
            self.take()
            return e
        raise self.fail("вираз (число, змінна або '(')")


def parse_pred(text: str) -> Pred:
    p = _P(text)
    out = p.pred()
    if p.kind != "EOF":
        raise p.fail("кінець твердження")
    return out


def parse_assertion_expr(text: str) -> A.Expr:
    p = _P(text)
    out = p.expr()
    if p.kind != "EOF":
        raise p.fail("кінець виразу")
    return out
