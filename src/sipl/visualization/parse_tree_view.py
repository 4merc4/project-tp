"""Експорт дерева синтаксичного виводу: текст, JSON, DOT, SVG, HTML.

Усе генерується з реального дерева (`PNode`), кожен вузол прив'язаний до
фрагмента вихідного коду через `SourceSpan`.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape, quoteattr

from ..parse_tree import RULES, PNode


def _fragment(node: PNode, source: str, limit: int = 40) -> str:
    text = " ".join(node.span.text(source).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"




def to_text(tree: PNode, source: str, show_fragments: bool = True) -> str:
    """Дерево у вигляді відступів: `<оператор> [NS1]  «x := 1»`."""
    lines: list[str] = []

    def label(n: PNode) -> str:
        if n.is_terminal:
            return n.symbol
        s = f"{n.symbol} [{n.rule}]"
        if show_fragments:
            s += f"   «{_fragment(n, source)}»"
        return s

    def rec(n: PNode, prefix: str, last: bool, root: bool) -> None:
        if root:
            lines.append(label(n))
        else:
            lines.append(prefix + ("└── " if last else "├── ") + label(n))
        child_prefix = prefix if root else prefix + ("    " if last else "│   ")
        for i, c in enumerate(n.children):
            rec(c, child_prefix, i == len(n.children) - 1, False)

    rec(tree, "", True, True)
    return "\n".join(lines)




def to_json(tree: PNode, source: str, indent: int = 2) -> str:
    payload = {"grammar": RULES, "source": source, "tree": tree.to_dict(source)}
    return json.dumps(payload, ensure_ascii=False, indent=indent)




def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_dot(tree: PNode, source: str) -> str:
    """Graphviz DOT (нетермінали — еліпси, термінали — прямокутники)."""
    ids: dict[int, str] = {}
    out = ["digraph ParseTree {", '  node [fontname="DejaVu Sans"];', "  ordering=out;"]
    leaves: list[str] = []
    for i, n in enumerate(tree.walk()):
        ids[id(n)] = f"n{i}"
        tip = f"{n.span.line}:{n.span.col}-{n.span.end_line}:{n.span.end_col} «{_fragment(n, source, 60)}»"
        if n.is_terminal:
            out.append(f'  n{i} [shape=box, style=rounded, label="{_dot_escape(n.symbol)}", '
                       f'tooltip="{_dot_escape(tip)}"];')
            leaves.append(f"n{i}")
        else:
            out.append(f'  n{i} [shape=ellipse, label="{_dot_escape(n.symbol)}\\n{n.rule}", '
                       f'tooltip="{_dot_escape(tip)}"];')
    for n in tree.walk():
        for c in n.children:
            out.append(f"  {ids[id(n)]} -> {ids[id(c)]};")
    if leaves:
        out.append("  { rank=same; " + "; ".join(leaves) + "; }")
    out.append("}")
    return "\n".join(out)


FORMATS = {"text": to_text, "json": to_json, "dot": to_dot}
