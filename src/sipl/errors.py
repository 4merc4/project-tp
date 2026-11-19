
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
    

    start: int
    end: int
    line: int
    col: int
    end_line: int
    end_col: int

    def text(self, source: str) -> str:
        return source[self.start:self.end]

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }

    @staticmethod
    def cover(first: "SourceSpan", last: "SourceSpan") -> "SourceSpan":
        
        return SourceSpan(first.start, last.end, first.line, first.col,
                          last.end_line, last.end_col)


class LineIndex:
    

    def __init__(self, source: str) -> None:
        self._starts = [0]
        for i, ch in enumerate(source):
            if ch == "\n":
                self._starts.append(i + 1)

    def locate(self, offset: int) -> tuple[int, int]:
        lo, hi = 0, len(self._starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, offset - self._starts[lo] + 1

    def span(self, start: int, end: int) -> SourceSpan:
        line, col = self.locate(start)
        end_line, end_col = self.locate(end)
        return SourceSpan(start, end, line, col, end_line, end_col)


@dataclass(frozen=True)
class Diagnostic:
    message: str
    span: SourceSpan
    severity: str = "error"

    def to_dict(self) -> dict:
        return {"severity": self.severity, "message": self.message,
                "span": self.span.to_dict()}

    def render(self, source: str, filename: str = "<input>") -> str:
        lines = source.split("\n")
        head = f"{filename}:{self.span.line}:{self.span.col}: {self.severity}: {self.message}"
        if 1 <= self.span.line <= len(lines):
            code = lines[self.span.line - 1]
            width = 1
            if self.span.end_line == self.span.line:
                width = max(1, self.span.end_col - self.span.col)
            pointer = " " * (self.span.col - 1) + "^" * width
            return f"{head}\n    {code}\n    {pointer}"
        return head


class SiplError(Exception):
    """Базова помилка бібліотеки."""


class SiplSyntaxError(SiplError):
    """Синтаксична помилка (лексична або граматична) з позицією."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
