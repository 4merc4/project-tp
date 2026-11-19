from __future__ import annotations

from . import ast as A


def expr(e: A.Expr) -> str:
    if isinstance(e, A.Num):
        return str(e.value)
    if isinstance(e, A.Var):
        return e.name
    if isinstance(e, A.ParenExpr):
        return f"({expr(e.inner)})"
    if isinstance(e, A.BinOp):
        return f"{expr(e.left)} {e.op} {expr(e.right)}"
    raise TypeError(e)


def cond(c: A.Cond) -> str:
    if isinstance(c, A.Compare):
        return f"{expr(c.left)} {c.op} {expr(c.right)}"
    if isinstance(c, A.Or):
        return f"{cond(c.left)} ∨ {cond(c.right)}"
    if isinstance(c, A.Not):
        return f"¬{cond(c.operand)}" if isinstance(c.operand, A.ParenCond) else f"¬ {cond(c.operand)}"
    if isinstance(c, A.ParenCond):
        return f"({cond(c.inner)})"
    raise TypeError(c)


def stmt(s: A.Stmt, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(s, A.Assign):
        return f"{pad}{s.target} := {expr(s.value)}"
    if isinstance(s, A.Skip):
        return f"{pad}skip"
    if isinstance(s, A.Seq):
        return f"{stmt(s.first, indent)};\n{stmt(s.second, indent)}"
    if isinstance(s, A.Block):
        return f"{pad}begin\n{stmt(s.body, indent + 1)}\n{pad}end"
    if isinstance(s, A.While):
        return f"{pad}while {cond(s.cond)} do\n{stmt(s.body, indent + 1)}"
    if isinstance(s, A.If):
        return (f"{pad}if {cond(s.cond)} then\n{stmt(s.then, indent + 1)}\n"
                f"{pad}else\n{stmt(s.orelse, indent + 1)}")
    raise TypeError(s)


def program(p: A.Program) -> str:
    return f"begin\n{stmt(p.body, 1)}\nend"


def short(node: A.Node, limit: int = 60) -> str:
    """Однорядковий запис вузла."""
    if isinstance(node, A.Program):
        text = program(node)
    elif isinstance(node, (A.Assign, A.Seq, A.If, A.While, A.Block, A.Skip)):
        text = stmt(node)
    elif isinstance(node, (A.Compare, A.Or, A.Not, A.ParenCond)):
        text = cond(node)
    else:
        text = expr(node)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
