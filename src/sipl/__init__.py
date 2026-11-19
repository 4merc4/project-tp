"""SIPL Language Toolkit: інструменти для навчальної мови SIPL."""
from __future__ import annotations

from . import ast
from .ast_builder import build_ast
from .errors import Diagnostic, SiplError, SiplSyntaxError, SourceSpan
from .parse_tree import PNode
from .parser import parse_tree

__version__ = "0.1.0"


def parse(source: str) -> ast.Program:
    """Розбирає текст програми й повертає AST (або кидає `SiplSyntaxError`)."""
    return build_ast(parse_tree(source))


def check(source: str) -> list[Diagnostic]:
    """Синтаксична перевірка: порожній список, якщо програма коректна."""
    try:
        parse_tree(source)
    except SiplSyntaxError as exc:
        return [exc.diagnostic]
    return []


__all__ = [
    "ast", "parse", "parse_tree", "build_ast", "check", "Diagnostic",
    "SiplError", "SiplSyntaxError", "SourceSpan", "PNode", "__version__",
]
