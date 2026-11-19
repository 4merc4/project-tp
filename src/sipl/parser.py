
from __future__ import annotations

from .errors import Diagnostic, SiplSyntaxError, SourceSpan
from .lexer import TOKEN_NAMES, Token, tokenize
from .parse_tree import (COND, EXPR, NUM, PROGRAM, STMT, VAR, PNode)


def _cover(nodes: list[PNode]) -> SourceSpan:
    return SourceSpan.cover(nodes[0].span, nodes[-1].span)


class Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens: list[Token] = tokenize(source)
        self.pos = 0
        self._cmp_memo: dict[int, tuple[PNode, int] | SiplSyntaxError] = {}

    
    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def _peek_kind(self, offset: int = 0) -> str:
        i = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[i].kind

    def _fail(self, expected: str) -> SiplSyntaxError:
        found = self.tok
        what = TOKEN_NAMES.get(found.kind, found.text)
        if found.kind in ("IDENT", "NUMBER"):
            what = f"{TOKEN_NAMES[found.kind]} {found.text!r}"
        msg = f"очікувалось {expected}, знайдено {what}"
        return SiplSyntaxError(Diagnostic(msg, found.span))

    def _eat(self, kind: str) -> PNode:
        if self.tok.kind != kind:
            raise self._fail(TOKEN_NAMES[kind])
        t = self.tok
        self.pos += 1
        return PNode(t.text, t.span)

    
    def parse_program(self) -> PNode:
        begin = self._eat("BEGIN")
        body = self.parse_seq()
        if self.tok.kind != "END":
            raise self._fail("';' або 'end'")
        end = self._eat("END")
        if self.tok.kind != "EOF":
            raise SiplSyntaxError(Diagnostic(
                "зайвий текст після завершального 'end'", self.tok.span))
        kids = [begin, body, end]
        return PNode(PROGRAM, _cover(kids), "NP1", kids)

    def parse_seq(self) -> PNode:
        left = self.parse_single()
        while self.tok.kind == "SEMI":
            semi = self._eat("SEMI")
            right = self.parse_single()
            kids = [left, semi, right]
            left = PNode(STMT, _cover(kids), "NS2", kids)
        return left

    def parse_single(self) -> PNode:
        k = self.tok.kind
        if k == "IDENT":
            var = self._var()
            assign = self._eat("ASSIGN")
            value = self.parse_expr()
            kids = [var, assign, value]
            return PNode(STMT, _cover(kids), "NS1", kids)
        if k == "WHILE":
            kw = self._eat("WHILE")
            cond = self.parse_cond()
            do = self._eat("DO")
            body = self.parse_single()
            kids = [kw, cond, do, body]
            return PNode(STMT, _cover(kids), "NS4", kids)
        if k == "IF":
            kw = self._eat("IF")
            cond = self.parse_cond()
            then = self._eat("THEN")
            s1 = self.parse_single()
            els = self._eat("ELSE")
            s2 = self.parse_single()
            kids = [kw, cond, then, s1, els, s2]
            return PNode(STMT, _cover(kids), "NS3", kids)
        if k == "BEGIN":
            b = self._eat("BEGIN")
            inner = self.parse_seq()
            if self.tok.kind != "END":
                raise self._fail("';' або 'end'")
            e = self._eat("END")
            kids = [b, inner, e]
            return PNode(STMT, _cover(kids), "NS5", kids)
        if k == "SKIP":
            s = self._eat("SKIP")
            return PNode(STMT, s.span, "NS6", [s])
        raise self._fail("оператор (присвоювання, if, while, begin або skip)")

    def _var(self) -> PNode:
        leaf = self._eat("IDENT")
        return PNode(VAR, leaf.span, "NV", [leaf])

    
    def parse_expr(self) -> PNode:
        left = self.parse_term()
        while self.tok.kind in ("PLUS", "MINUS"):
            op = self._eat(self.tok.kind)
            right = self.parse_term()
            kids = [left, op, right]
            rule = "NA3" if op.symbol == "+" else "NA4"
            left = PNode(EXPR, _cover(kids), rule, kids)
        return left

    def parse_term(self) -> PNode:
        left = self.parse_primary()
        while self.tok.kind in ("STAR", "DIV"):
            op = self._eat(self.tok.kind)
            right = self.parse_primary()
            kids = [left, op, right]
            rule = "NA5" if op.symbol in ("*", "∗") else "NA7"
            left = PNode(EXPR, _cover(kids), rule, kids)
        return left

    def parse_primary(self) -> PNode:
        k = self.tok.kind
        if k == "NUMBER":
            leaf = self._eat("NUMBER")
            num = PNode(NUM, leaf.span, "NN", [leaf])
            return PNode(EXPR, leaf.span, "NA1", [num])
        if k == "MINUS" and self._peek_kind(1) == "NUMBER":
            minus = self.tok
            digits = self.tokens[self.pos + 1]
            self.pos += 2
            span = SourceSpan.cover(minus.span, digits.span)
            leaf = PNode("-" + digits.text, span)
            num = PNode(NUM, span, "NN", [leaf])
            return PNode(EXPR, span, "NA1", [num])
        if k == "IDENT":
            var = self._var()
            return PNode(EXPR, var.span, "NA2", [var])
        if k == "LPAR":
            lp = self._eat("LPAR")
            inner = self.parse_expr()
            if self.tok.kind != "RPAR":
                raise self._fail("')'")
            rp = self._eat("RPAR")
            kids = [lp, inner, rp]
            return PNode(EXPR, _cover(kids), "NA6", kids)
        raise self._fail("вираз (число, змінна або '(')")

    
    def parse_cond(self) -> PNode:
        left = self.parse_not()
        while self.tok.kind == "OR":
            op = self._eat("OR")
            right = self.parse_not()
            kids = [left, op, right]
            left = PNode(COND, _cover(kids), "NB3", kids)
        return left

    def parse_not(self) -> PNode:
        if self.tok.kind == "NOT":
            op = self._eat("NOT")
            inner = self.parse_not()
            kids = [op, inner]
            return PNode(COND, _cover(kids), "NB4", kids)
        return self.parse_atom_cond()

    def parse_atom_cond(self) -> PNode:
        if self.tok.kind != "LPAR":
            return self._comparison()
        
        start = self.pos
        try:
            return self._comparison()
        except SiplSyntaxError as first:
            self.pos = start
            try:
                lp = self._eat("LPAR")
                inner = self.parse_cond()
                if self.tok.kind != "RPAR":
                    raise self._fail("')'")
                rp = self._eat("RPAR")
                kids = [lp, inner, rp]
                return PNode(COND, _cover(kids), "NB5", kids)
            except SiplSyntaxError as second:
                
                best = second if second.diagnostic.span.start >= first.diagnostic.span.start else first
                raise best

    def _comparison(self) -> PNode:
        start = self.pos
        cached = self._cmp_memo.get(start)
        if isinstance(cached, SiplSyntaxError):
            raise cached
        if cached is not None:
            node, end = cached
            self.pos = end
            return node
        try:
            left = self.parse_expr()
            if self.tok.kind not in ("EQ", "GT"):
                raise self._fail("'=' або '>' (порівняння)")
            op = self._eat(self.tok.kind)
            right = self.parse_expr()
        except SiplSyntaxError as exc:
            self._cmp_memo[start] = exc
            raise
        kids = [left, op, right]
        node = PNode(COND, _cover(kids), "NB1" if op.symbol == "=" else "NB2", kids)
        self._cmp_memo[start] = (node, self.pos)
        return node


def parse_tree(source: str) -> PNode:
    return Parser(source).parse_program()
