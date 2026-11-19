"""Командний рядок: sipl check | parse | ast | term | eval | prove."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import __version__, ast as A
from . import check as syntax_check
from . import parse, parse_tree
from .errors import SiplError, SiplSyntaxError
from .proof import AssertionSyntaxError, SpecError, verify
from .proof.solver import HAVE_Z3
from .semantics import (build_term, evaluate, format_state, parse_state, pretty,
                        render_derivation, show)
from .semantics import terms as T
from .visualization import FORMATS

EXIT_OK = 0
EXIT_ERROR = 1        
EXIT_UNDEFINED = 3    
EXIT_UNPROVED = 4    


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        raise SiplError(f"не вдалося прочитати файл {path!r}: {exc.strerror}")


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text if text.endswith("\n") else text + "\n")
    else:
        print(text)


def _syntax_failure(exc: SiplSyntaxError, source: str, name: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "diagnostics": [exc.diagnostic.to_dict()]},
                         ensure_ascii=False, indent=2))
    else:
        print(exc.diagnostic.render(source, name), file=sys.stderr)
    return EXIT_ERROR


def cmd_check(args) -> int:
    src = _read(args.file)
    diags = syntax_check(src)
    if args.json:
        print(json.dumps({"ok": not diags, "diagnostics": [d.to_dict() for d in diags]},
                         ensure_ascii=False, indent=2))
    elif diags:
        for d in diags:
            print(d.render(src, args.file), file=sys.stderr)
    else:
        print(f"{args.file}: синтаксично коректна програма")
    return EXIT_ERROR if diags else EXIT_OK


def cmd_parse(args) -> int:
    src = _read(args.file)
    try:
        tree = parse_tree(src)
    except SiplSyntaxError as exc:
        return _syntax_failure(exc, src, args.file, args.format == "json")
    _emit(FORMATS[args.format](tree, src), args.output)
    return EXIT_OK


def cmd_ast(args) -> int:
    src = _read(args.file)
    try:
        prog = parse(src)
    except SiplSyntaxError as exc:
        return _syntax_failure(exc, src, args.file, True)
    _emit(json.dumps(A.to_dict(prog), ensure_ascii=False, indent=2), args.output)
    return EXIT_OK


def cmd_term(args) -> int:
    src = _read(args.file)
    try:
        prog = parse(src)
    except SiplSyntaxError as exc:
        return _syntax_failure(exc, src, args.file, args.json)
    term, steps = build_term(prog)
    if args.json:
        _emit(json.dumps({"term": show(term, args.style), "tree": T.to_dict(term),
                          "derivation": [s.to_dict() for s in steps]},
                         ensure_ascii=False, indent=2), args.output)
        return EXIT_OK
    text = pretty(term) if args.pretty else show(term, args.style)
    if args.explain:
        text = render_derivation(steps) + "\n\nsem_P(P) = " + text
    _emit(text, args.output)
    return EXIT_OK


def cmd_eval(args) -> int:
    src = _read(args.file)
    try:
        prog = parse(src)
        state = parse_state(args.state or "")
    except SiplSyntaxError as exc:
        return _syntax_failure(exc, src, args.file, args.json)
    except ValueError as exc:
        print(f"помилка у --state: {exc}", file=sys.stderr)
        return EXIT_ERROR
    term, _ = build_term(prog)
    res = evaluate(term, state, limit=args.limit, trace=args.trace or args.json)
    if args.json:
        print(json.dumps({"term": show(term), "input": state, **res.to_dict()},
                         ensure_ascii=False, indent=2))
    else:
        if args.trace:
            print(res.render_trace(verbose=args.verbose))
            print()
        if res.defined:
            print(f"sem_P(P)({format_state(state)}) = {format_state(res.state)}")
        else:
            print(f"sem_P(P)({format_state(state)}) не визначене: {res.reason}")
    return EXIT_OK if res.defined else EXIT_UNDEFINED


def cmd_prove(args) -> int:
    src = _read(args.file)
    spec = {}
    if args.spec:
        try:
            spec = json.loads(_read(args.spec))
        except json.JSONDecodeError as exc:
            print(f"помилка у специфікації {args.spec}: {exc}", file=sys.stderr)
            return EXIT_ERROR
    pre = args.pre if args.pre is not None else spec.get("pre", "true")
    post = args.post if args.post is not None else spec.get("post")
    invs = args.inv if args.inv else spec.get("invariants", [])
    variants = args.variant if args.variant else spec.get("variants", [])
    if post is None:
        print("потрібна післяумова: --post або \"post\" у файлі специфікації", file=sys.stderr)
        return EXIT_ERROR
    try:
        report = verify(src, pre, post, invs, variants, backend=args.backend,
                        bound=args.bound, test=not args.no_test, test_bound=args.test_bound)
    except SiplSyntaxError as exc:
        return _syntax_failure(exc, src, args.file, args.json)
    except (AssertionSyntaxError, SpecError, RuntimeError, ValueError) as exc:
        print(f"помилка специфікації: {exc}", file=sys.stderr)
        return EXIT_ERROR
    _emit(report.to_json() if args.json else report.render(), args.output)
    if report.partial is False or report.total is False:
        return EXIT_ERROR
    wanted_total = bool(variants)
    ok = report.total if wanted_total else report.partial
    return EXIT_OK if ok else EXIT_UNPROVED


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sipl", description="SIPL Language Toolkit: парсер, візуалізація, семантичні терми, "
        "асистент доведення коректності.")
    p.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_file(sp):
        sp.add_argument("file", help="файл .sipl або '-' для stdin")

    sp = sub.add_parser("check", help="синтаксична перевірка")
    add_file(sp)
    sp.add_argument("--json", action="store_true", help="діагностика у JSON")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("parse", help="дерево синтаксичного виводу")
    add_file(sp)
    sp.add_argument("-f", "--format", choices=sorted(FORMATS), default="text")
    sp.add_argument("-o", "--output", help="записати у файл")
    sp.set_defaults(func=cmd_parse)

    sp = sub.add_parser("ast", help="AST у JSON")
    add_file(sp)
    sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_ast)

    sp = sub.add_parser("term", help="семантичний терм програми")
    add_file(sp)
    sp.add_argument("--style", choices=["unicode", "latex"], default="unicode")
    sp.add_argument("--explain", action="store_true", help="показати застосовані правила NS")
    sp.add_argument("--pretty", action="store_true", help="багаторядковий запис")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_term)

    sp = sub.add_parser("eval", help="застосувати семантичний терм до стану")
    add_file(sp)
    sp.add_argument("-s", "--state", default="", help="вхідний стан, напр. 'X=3,Y=7'")
    sp.add_argument("--limit", type=int, default=100_000, help="ліміт ітерацій циклів")
    sp.add_argument("--trace", action="store_true", help="покрокове пояснення (правила AF_*)")
    sp.add_argument("--verbose", action="store_true", help="з деталями на рівні виразів")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("prove", help="асистент доведення коректності циклів")
    add_file(sp)
    sp.add_argument("--pre", help="передумова (за замовчуванням true)")
    sp.add_argument("--post", help="післяумова")
    sp.add_argument("--inv", action="append", help="інваріант циклу (повторюється, в порядку циклів)")
    sp.add_argument("--variant", action="append", help="міра (вираз) для циклу; '-' — пропустити")
    sp.add_argument("--spec", help="JSON зі специфікацією: pre, post, invariants, variants")
    sp.add_argument("--backend", choices=["auto", "z3", "bounded"], default="auto",
                    help=f"розв'язувач (Z3 {'встановлено' if HAVE_Z3 else 'не встановлено'})")
    sp.add_argument("--bound", type=int, default=8, help="діапазон перебору для backend=bounded")
    sp.add_argument("--no-test", action="store_true", help="не запускати програму на малих даних")
    sp.add_argument("--test-bound", type=int, default=5, help="діапазон вхідних даних для запусків")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_prove)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SiplError as exc:
        print(f"помилка: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  
    sys.exit(main())
