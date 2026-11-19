
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional

from .errors import SourceSpan


PROGRAM = "<програма>"
STMT = "<оператор>"
EXPR = "<вираз>"
COND = "<умова>"
VAR = "<змінна>"
NUM = "<число>"


RULES = {
    "NP1": "<програма> ::= begin <оператор> end",
    "NS1": "<оператор> ::= <змінна> := <вираз>",
    "NS2": "<оператор> ::= <оператор> ; <оператор>",
    "NS3": "<оператор> ::= if <умова> then <оператор> else <оператор>",
    "NS4": "<оператор> ::= while <умова> do <оператор>",
    "NS5": "<оператор> ::= begin <оператор> end",
    "NS6": "<оператор> ::= skip",
    "NA1": "<вираз> ::= <число>",
    "NA2": "<вираз> ::= <змінна>",
    "NA3": "<вираз> ::= <вираз> + <вираз>",
    "NA4": "<вираз> ::= <вираз> – <вираз>",
    "NA5": "<вираз> ::= <вираз> * <вираз>",
    "NA6": "<вираз> ::= ( <вираз> )",
    "NA7": "<вираз> ::= <вираз> div <вираз>   (розширення курсу)",
    "NB1": "<умова> ::= <вираз> = <вираз>",
    "NB2": "<умова> ::= <вираз> > <вираз>",
    "NB3": "<умова> ::= <умова> ∨ <умова>",
    "NB4": "<умова> ::= ¬ <умова>",
    "NB5": "<умова> ::= ( <умова> )",
    "NV": "<змінна> ::= ім'я",
    "NN": "<число> ::= цифри",
}


@dataclass
class PNode:
    """Вузол дерева виводу.

    * нетермінал: `symbol` — метазмінна, `rule` — правило БНФ;
    * термінал (листок): `symbol` — текст лексеми, `rule` = None.
    """

    symbol: str
    span: SourceSpan
    rule: Optional[str] = None
    children: list["PNode"] = field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return self.rule is None

    def walk(self) -> Iterator["PNode"]:
        yield self
        for c in self.children:
            yield from c.walk()

    def leaves(self) -> list["PNode"]:
        return [n for n in self.walk() if n.is_terminal]

    def to_dict(self, source: str | None = None) -> dict:
        d: dict = {"symbol": self.symbol, "span": self.span.to_dict()}
        if self.rule:
            d["rule"] = self.rule
        if source is not None:
            d["text"] = self.span.text(source)
        if self.children:
            d["children"] = [c.to_dict(source) for c in self.children]
        return d
