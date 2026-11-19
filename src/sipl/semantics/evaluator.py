"""Обчислення семантичного терму на стані (SEM-02) за таблицею 1.5 посібника.

Функції часткові: якщо значення складової не визначене, то й результат
не визначений (зауваження 1.6). Тому невизначеність — повноправний
результат: змінної немає в стані, ділення на нуль, цикл не завершується
(на практиці — перевищено ліміт ітерацій).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from . import terms as T
from .printer import show

State = dict  
Value = Union[int, bool, dict]


class Undefined(Exception):
    """Значення функції на цьому стані не визначене."""

    def __init__(self, reason: str, kind: str = "partial") -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind  


def format_state(st: State) -> str:
    if not st:
        return "[]"
    return "[" + ", ".join(f"{k} ↦ {v}" for k, v in st.items()) + "]"


def parse_state(text: str) -> State:
    """`X=3,Y=7` або `[X ↦ 3, Y ↦ 7]` -> {'X': 3, 'Y': 7}."""
    text = text.strip().strip("[]")
    st: State = {}
    if not text.strip():
        return st
    for part in text.split(","):
        part = part.strip()
        for sep in ("↦", "=", ":"):
            if sep in part:
                name, val = part.split(sep, 1)
                break
        else:
            raise ValueError(f"не вдалося розібрати {part!r}: очікується ім'я=число")
        name = name.strip()
        if not name or not (name[0].isalpha() or name[0] == "_"):
            raise ValueError(f"некоректне ім'я змінної {name!r}")
        try:
            st[name] = int(val.strip())
        except ValueError:
            raise ValueError(f"значення змінної {name} має бути цілим числом, а не {val.strip()!r}")
    return st


def override(st: State, name: str, value: int) -> State:
    """st ∇ [name ↦ value]."""
    new = dict(st)
    new[name] = value
    return new


MAX_BITS = 4096  


def _check_size(v: int) -> int:
    if v.bit_length() > MAX_BITS:
        raise Undefined(f"число перевищило {MAX_BITS} біт: обчислення зупинено", "limit")
    return v


def _apply_basic(name: str, args: list) -> Value:
    if name == "add":
        return _check_size(args[0] + args[1])
    if name == "sub":
        return _check_size(args[0] - args[1])
    if name == "mult":
        return _check_size(args[0] * args[1])
    if name == "div":
        if args[1] == 0:
            raise Undefined("ділення на нуль")
        return args[0] // args[1]
    if name == "or":
        return args[0] or args[1]
    if name == "neg":
        return not args[0]
    if name == "eq":
        return args[0] == args[1]
    if name == "gr":
        return args[0] > args[1]
    raise ValueError(f"невідома базова функція {name}")


@dataclass
class TraceEvent:
    rule: str       
    depth: int
    text: str
    kind: str = "step"   

    def to_dict(self) -> dict:
        return {"rule": self.rule, "depth": self.depth, "text": self.text, "kind": self.kind}


@dataclass
class EvalResult:
    status: str                      
    state: Optional[State]
    reason: Optional[str] = None
    reason_kind: Optional[str] = None 
    iterations: int = 0
    events: list[TraceEvent] = field(default_factory=list)

    @property
    def defined(self) -> bool:
        return self.status == "defined"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "state": self.state,
            "reason": self.reason,
            "reason_kind": self.reason_kind,
            "iterations": self.iterations,
            "trace": [e.to_dict() for e in self.events],
        }

    def render_trace(self, verbose: bool = False) -> str:
        lines = []
        for e in self.events:
            if e.kind == "expr" and not verbose:
                continue
            lines.append(f"{'  ' * e.depth}{e.rule}: {e.text}")
        return "\n".join(lines)


def _short(text: str, limit: int = 96) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _Eval:
    def __init__(self, limit: int, trace: bool) -> None:
        self.limit = limit
        self.trace = trace
        self.iterations = 0
        self.events: list[TraceEvent] = []

    def log(self, rule: str, depth: int, text: str, kind: str = "step") -> None:
        if self.trace:
            self.events.append(TraceEvent(rule, depth, text, kind))

    def ev(self, t: T.Term, st: State, d: int) -> Value:
        if isinstance(t, T.Const):
            self.trace and self.log("AF_S", d, f"{show(t)}(st) = {t.value}", "expr")
            return t.value
        if isinstance(t, T.Deref):
            if t.name not in st:
                raise Undefined(f"змінна {t.name} не має значення в стані {format_state(st)}")
            v = st[t.name]
            self.trace and self.log("AF_DNM", d, f"{t.name}⇒(st) = st({t.name}) = {v}", "expr")
            return v
        if isinstance(t, T.Id):
            self.trace and self.log("AF_ID", d, f"id(st) = {format_state(st)}")
            return dict(st)
        if isinstance(t, T.Sup):
            vals = [self.ev(a, st, d + 1) for a in t.args]
            r = _apply_basic(t.func.name, vals)
            shown = ", ".join(str(v).lower() if isinstance(v, bool) else str(v) for v in vals)
            res = str(r).lower() if isinstance(r, bool) else str(r)
            self.trace and self.log("AF_S", d, f"{_short(show(t))}(st) = {t.func.name}({shown}) = {res}", "expr")
            return r
        if isinstance(t, T.Assign):
            v = self.ev(t.func, st, d + 1)
            new = override(st, t.var, v)
            self.trace and self.log("AF_AS", d, f"{_short(show(t))}(st) = st∇[{t.var} ↦ {v}] = {format_state(new)}")
            return new
        if isinstance(t, T.Seq):
            mid = self.ev(t.first, st, d + 1)
            out = self.ev(t.second, mid, d + 1)
            self.trace and self.log("AF_SEQ", d, f"(f • g)(st) = g(f(st)) = {format_state(out)}")
            return out
        if isinstance(t, T.If):
            p = self.ev(t.cond, st, d + 1)
            branch = t.then if p else t.orelse
            out = self.ev(branch, st, d + 1)
            self.trace and self.log("AF_IF", d, f"умова {str(p).lower()}, виконано гілку {'then' if p else 'else'}: "
                                 f"{format_state(out)}")
            return out
        if isinstance(t, T.While):
            cur = st
            n = 0
            while True:
                p = self.ev(t.cond, cur, d + 1)
                self.trace and self.log("AF_WH", d, f"p(st{n}) = {str(p).lower()}, st{n} = {format_state(cur)}")
                if not p:
                    break
                self.iterations += 1
                if self.iterations > self.limit:
                    raise Undefined(
                        f"перевищено ліміт {self.limit} ітерацій циклів: цикл, ймовірно, "
                        "не завершується, тому значення вважаємо невизначеним", "limit")
                cur = self.ev(t.body, cur, d + 1)
                n += 1
            self.trace and self.log("AF_WH", d, f"WH(p, f)(st0) = st{n} = {format_state(cur)}  ({n} ітер.)")
            return cur
        raise TypeError(t)


def evaluate(term: T.Term, state: State, limit: int = 100_000, trace: bool = True) -> EvalResult:
    """Застосовує терм до стану. Ніколи не кидає `Undefined`: повертає результат."""
    ev = _Eval(limit, trace)
    try:
        out = ev.ev(term, dict(state), 0)
    except Undefined as exc:
        ev.log("↑", 0, f"значення не визначене: {exc.reason}")
        return EvalResult("undefined", None, exc.reason, exc.kind, ev.iterations, ev.events)
    if not isinstance(out, dict):
        raise TypeError("очікувався терм типу State → State (програма або оператор)")
    return EvalResult("defined", out, None, None, ev.iterations, ev.events)
