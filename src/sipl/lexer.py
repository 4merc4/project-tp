
from __future__ import annotations

from dataclasses import dataclass

from .errors import Diagnostic, LineIndex, SiplSyntaxError, SourceSpan

KEYWORDS = {
    "begin": "BEGIN",
    "end": "END",
    "while": "WHILE",
    "do": "DO",
    "if": "IF",
    "then": "THEN",
    "else": "ELSE",
    "skip": "SKIP",
    
    "not": "NOT",
    "or": "OR",
   
    "div": "DIV",
}

SINGLE = {
    ";": "SEMI",
    "+": "PLUS",
    "-": "MINUS",
    "–": "MINUS",   
    "−": "MINUS",
    "*": "STAR",
    "∗": "STAR",
    "(": "LPAR",
    ")": "RPAR",
    "=": "EQ",
    ">": "GT",
    "¬": "NOT",
    "!": "NOT",
    "∨": "OR",
    "|": "OR",
}

TOKEN_NAMES = {
    "BEGIN": "'begin'", "END": "'end'", "WHILE": "'while'", "DO": "'do'",
    "IF": "'if'", "THEN": "'then'", "ELSE": "'else'", "SKIP": "'skip'",
    "NOT": "'¬'", "OR": "'∨'", "DIV": "'div'", "SEMI": "';'",
    "PLUS": "'+'", "MINUS": "'-'", "STAR": "'*'", "LPAR": "'('",
    "RPAR": "')'", "EQ": "'='", "GT": "'>'", "ASSIGN": "':='",
    "IDENT": "ім'я змінної", "NUMBER": "число", "EOF": "кінець програми",
}


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    span: SourceSpan


def tokenize(source: str) -> list[Token]:
    """Розбиває текст на лексеми. Коментарі `// ...` до кінця рядка ігноруються."""
    idx = LineIndex(source)
    tokens: list[Token] = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith(":=", i):
            tokens.append(Token("ASSIGN", ":=", idx.span(i, i + 2)))
            i += 2
            continue
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            tokens.append(Token("NUMBER", source[i:j], idx.span(i, j)))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            tokens.append(Token(KEYWORDS.get(word, "IDENT"), word, idx.span(i, j)))
            i = j
            continue
        if ch in SINGLE:
            tokens.append(Token(SINGLE[ch], ch, idx.span(i, i + 1)))
            i += 1
            continue
        raise SiplSyntaxError(Diagnostic(f"невідомий символ {ch!r}", idx.span(i, i + 1)))
    tokens.append(Token("EOF", "", idx.span(n, n)))
    return tokens
