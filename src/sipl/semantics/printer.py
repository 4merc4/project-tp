"""Запис семантичних термів у нотації курсу (Unicode або LaTeX)."""
from __future__ import annotations

from . import terms as T

_SUP = {**{c: s for c, s in zip("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")},
        **{c: s for c, s in zip("abcdefghijklmnoprstuvwxyz",
                                "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")}}

_MACRON = "̄"


def _sup(text: str) -> str | None:
    if all(c in _SUP for c in text):
        return "".join(_SUP[c] for c in text)
    return None


def _as_name(var: str) -> str:
    sup = _sup(var)
    if sup:
        return f"AS{sup}"
    return f"AS^{var}" if len(var) == 1 else f"AS^{{{var}}}"


def _flatten_seq(t: T.Term) -> list[T.Term]:
    """• асоціативне (лема 1.1 посібника), тому ланцюжок друкуємо плоско."""
    if isinstance(t, T.Seq):
        return _flatten_seq(t.first) + _flatten_seq(t.second)
    return [t]


def show(t: T.Term, style: str = "unicode") -> str:
    if style not in ("unicode", "latex"):
        raise ValueError("style має бути 'unicode' або 'latex'")
    return _show(t, style)


def _show(t: T.Term, st: str) -> str:
    latex = st == "latex"
    if isinstance(t, T.Const):
        s = str(t.value)
        return f"\\overline{{{s}}}" if latex else "".join(ch + _MACRON for ch in s)
    if isinstance(t, T.Deref):
        return f"{t.name}\\Rightarrow" if latex else f"{t.name}⇒"
    if isinstance(t, T.Basic):
        return t.name
    if isinstance(t, T.Id):
        return "\\mathrm{id}" if latex else "id"
    if isinstance(t, T.Sup):
        inner = ", ".join([t.func.name] + [_show(a, st) for a in t.args])
        if latex:
            return f"S^{{{t.n}}}({inner})"
        return f"S{_sup(str(t.n))}({inner})"
    if isinstance(t, T.Assign):
        arg = _show(t.func, st)
        if latex:
            return f"AS^{{{t.var}}}({arg})"
        return f"{_as_name(t.var)}({arg})"
    if isinstance(t, T.Seq):
        sep = " \\cdot " if latex else " · "
        return sep.join(_show(p, st) for p in _flatten_seq(t))
    if isinstance(t, T.If):
        return f"IF({_show(t.cond, st)}, {_show(t.then, st)}, {_show(t.orelse, st)})"
    if isinstance(t, T.While):
        return f"WH({_show(t.cond, st)}, {_show(t.body, st)})"
    raise TypeError(t)


def pretty(t: T.Term, width: int = 78) -> str:
    """Багаторядковий запис з відступами (коли рядок задовгий)."""
    flat = show(t)
    if len(flat) <= width:
        return flat
    return _pretty(t, 0, width)


def _pretty(t: T.Term, ind: int, width: int) -> str:
    pad = "  " * ind
    flat = show(t)
    if len(flat) + len(pad) <= width or not T.children(t):
        return pad + flat
    if isinstance(t, T.Seq):
        parts = _flatten_seq(t)
        return (" ·\n").join(_pretty(p, ind, width) for p in parts)
    if isinstance(t, T.While):
        return (f"{pad}WH(\n{_pretty(t.cond, ind + 1, width)},\n"
                f"{_pretty(t.body, ind + 1, width)}\n{pad})")
    if isinstance(t, T.If):
        return (f"{pad}IF(\n{_pretty(t.cond, ind + 1, width)},\n"
                f"{_pretty(t.then, ind + 1, width)},\n{_pretty(t.orelse, ind + 1, width)}\n{pad})")
    if isinstance(t, T.Assign):
        name = _as_name(t.var)
        return f"{pad}{name}(\n{_pretty(t.func, ind + 1, width)}\n{pad})"
    return pad + flat
