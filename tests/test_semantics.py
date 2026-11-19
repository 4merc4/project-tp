import random

import pytest

import sipl
from sipl import ast as A
from sipl import semantics as S
from sipl.semantics import terms as T

from oracle import run


def term_of(src):
    return S.semantic_term(sipl.parse(src))



def test_golden_term_for_log_program(example):
    t = S.show(term_of(example("log.sipl")))
    assert t == ("AS^K(0̄) · WH(S¹(neg, S²(gr, X⇒, Y⇒)), "
                 "AS^Y(S²(div, Y⇒, X⇒)) · AS^K(S²(add, K⇒, 1̄)))")


def test_golden_term_for_gcd_from_the_book(example):
    t = S.show(term_of(example("gcd.sipl")))
    assert t == ("WH(S¹(neg, S²(eq, M⇒, N⇒)), IF(S²(gr, M⇒, N⇒), "
                 "AS^M(S²(sub, M⇒, N⇒)), AS^N(S²(sub, N⇒, M⇒))))")


@pytest.mark.parametrize("src,expected", [
    ("begin skip end", "id"),
    ("begin x := 1 end", "ASˣ(1̄)"),
    ("begin x := y + 2 end", "ASˣ(S²(add, y⇒, 2̄))"),
    ("begin x := y * 2 - 1 end", "ASˣ(S²(sub, S²(mult, y⇒, 2̄), 1̄))"),
    ("begin x := (y + 1) * 2 end", "ASˣ(S²(mult, S²(add, y⇒, 1̄), 2̄))"),
    ("begin x := 12 end", "ASˣ(1̄2̄)"),
    ("begin x := y div 2 end", "ASˣ(S²(div, y⇒, 2̄))"),
    ("begin x := 1; y := 2; z := 3 end", "ASˣ(1̄) · ASʸ(2̄) · ASᶻ(3̄)"),
    ("begin if x = 1 then skip else x := 2 end", "IF(S²(eq, x⇒, 1̄), id, ASˣ(2̄))"),
    ("begin while a > b ∨ ¬(c = d) do skip end",
     "WH(S²(or, S²(gr, a⇒, b⇒), S¹(neg, S²(eq, c⇒, d⇒))), id)"),
    ("begin begin x := 1 end end", "ASˣ(1̄)"),
])
def test_term_for_each_syntactic_construction(src, expected):
    assert S.show(term_of(src)) == expected


def test_sequence_chain_is_flat_in_the_printout_but_associative():
    left = term_of("begin a := 1; b := 2; c := 3 end")
    assert isinstance(left, T.Seq) and isinstance(left.first, T.Seq)
    assert " · " in S.show(left) and "(" not in S.show(left).replace("(1̄)", "").replace("(2̄)", "").replace("(3̄)", "")


def test_latex_style():
    t = S.show(term_of("begin K := 0 end"), "latex")
    assert t == r"AS^{K}(\overline{0})"


def test_derivation_lists_ns_rules_in_top_down_order(example):
    _, steps = S.build_term(sipl.parse(example("log.sipl")))
    rules = [s.rule for s in steps]
    assert rules[0] == "NS_Prog" and rules[1] == "NS_Stm_Seq"
    assert {"NS_Stm_As", "NS_Stm_Wh", "NS_B_neg", "NS_B_Par", "NS_B_gr", "NS_A_Var",
            "NS_A_Div", "NS_A_Add", "NS_A_Num", "NS_Stm_BE"} <= set(rules)
    text = S.render_derivation(steps)
    assert "sem_S(while b do S) = WH(sem_B(b), sem_S(S))" in text


def test_terms_keep_links_to_source(example):
    src = example("log.sipl")
    term = S.semantic_term(sipl.parse(src))
    assert isinstance(term, T.Seq)
    assert term.first.source.text(src) == "K := 0"
    assert term.second.source.text(src).startswith("while ¬(X > Y) do")


def test_pretty_printer_breaks_long_terms(example):
    t = term_of(example("log.sipl"))
    out = S.pretty(t, width=50)
    assert "\n" in out and out.replace("\n", "").replace(" ", "") == S.show(t).replace(" ", "")




def test_book_example_gcd(example):
    r = S.evaluate(term_of(example("gcd.sipl")), {"M": 8, "N": 16})
    assert r.defined and r.state == {"M": 8, "N": 8}


def test_lab2_test_run(example):
    r = S.evaluate(term_of(example("log.sipl")), {"X": 3, "Y": 7})
    assert r.state == {"X": 3, "Y": 2, "K": 1}
    assert r.iterations == 1
    text = r.render_trace()
    assert "p(st0) = true" in text and "p(st1) = false" in text
    assert "[X ↦ 3, Y ↦ 2, K ↦ 1]" in text


@pytest.mark.parametrize("x,y,k", [(2, 1, 0), (2, 8, 3), (3, 26, 2), (3, 27, 3), (10, 999, 2), (2, 1024, 10)])
def test_log_program_computes_floor_log(example, x, y, k):
    r = S.evaluate(term_of(example("log.sipl")), {"X": x, "Y": y})
    assert r.state["K"] == k


@pytest.mark.parametrize("src,state,reason", [
    ("begin x := y end", {"x": 1}, "змінна y"),
    ("begin x := 1 div 0 end", {}, "ділення на нуль"),
    ("begin while x > 0 do skip end", {"x": 1}, "ліміт"),
])
def test_undefined_results(src, state, reason):
    r = S.evaluate(term_of(src), state, limit=100)
    assert not r.defined and r.state is None and reason in r.reason
    assert r.reason_kind == ("limit" if "ліміт" in reason else "partial")


def test_undefined_condition_makes_while_undefined():
    r = S.evaluate(term_of("begin while y > 0 do skip end"), {})
    assert not r.defined


def test_if_branches_and_skip():
    t = term_of("begin if x > 0 then y := 1 else skip end")
    assert S.evaluate(t, {"x": 1}).state == {"x": 1, "y": 1}
    assert S.evaluate(t, {"x": 0}).state == {"x": 0}


def test_assignment_overrides_without_touching_other_variables():
    r = S.evaluate(term_of("begin x := x + 1 end"), {"x": 1, "y": 9})
    assert r.state == {"x": 2, "y": 9}


def test_runaway_number_growth_is_cut_off():
    r = S.evaluate(term_of("begin while 1 = 1 do x := x * x end"), {"x": 3}, limit=10_000)
    assert not r.defined and r.reason_kind == "limit" and "біт" in r.reason


def test_input_state_is_not_mutated():
    st = {"x": 3}
    S.evaluate(term_of("begin x := x + 1 end"), st)
    assert st == {"x": 3}


def test_trace_verbose_has_expression_level_details():
    r = S.evaluate(term_of("begin x := y + 1 end"), {"y": 1})
    assert "AF_DNM" not in r.render_trace()
    assert "AF_DNM" in r.render_trace(verbose=True)


def test_parse_state_formats_and_errors():
    assert S.parse_state("X=3, Y=7") == {"X": 3, "Y": 7}
    assert S.parse_state("[X ↦ 3, Y ↦ -7]") == {"X": 3, "Y": -7}
    assert S.parse_state("") == {}
    with pytest.raises(ValueError):
        S.parse_state("X=abc")
    with pytest.raises(ValueError):
        S.parse_state("X")
    assert S.format_state({"X": 3}) == "[X ↦ 3]"




VARS = ["x", "y", "z"]


def rnd_expr(r, depth):
    if depth == 0 or r.random() < 0.3:
        return r.choice([str(r.randint(0, 4)), r.choice(VARS)])
    op = r.choice(["+", "-", "*", "div"])
    if op == "*":  
        return f"({rnd_expr(r, depth - 1)} * {r.randint(0, 3)})"
    return f"({rnd_expr(r, depth - 1)} {op} {rnd_expr(r, depth - 1)})"


def rnd_cond(r, depth):
    if depth == 0 or r.random() < 0.5:
        return f"{rnd_expr(r, 2)} {r.choice(['=', '>'])} {rnd_expr(r, 2)}"
    k = r.choice(["or", "not"])
    if k == "or":
        return f"({rnd_cond(r, depth - 1)}) ∨ ({rnd_cond(r, depth - 1)})"
    return f"¬({rnd_cond(r, depth - 1)})"


def rnd_stmt(r, depth):
    k = r.random()
    if depth == 0 or k < 0.35:
        return f"{r.choice(VARS)} := {rnd_expr(r, 2)}"
    if k < 0.5:
        return "skip"
    if k < 0.7:
        return f"if {rnd_cond(r, 1)} then {rnd_stmt(r, depth - 1)} else {rnd_stmt(r, depth - 1)}"
    if k < 0.85:
        return f"while {rnd_cond(r, 1)} do {rnd_stmt(r, depth - 1)}"
    return f"begin {rnd_stmt(r, depth - 1)}; {rnd_stmt(r, depth - 1)} end"


def test_term_evaluation_agrees_with_direct_execution():
    r = random.Random(20260519)
    checked_defined = checked_undefined = 0
    for _ in range(400):
        body = "; ".join(rnd_stmt(r, 3) for _ in range(r.randint(1, 3)))
        src = f"begin {body} end"
        prog = sipl.parse(src)
        term = S.semantic_term(prog)
        for _ in range(3):
            st = {v: r.randint(-3, 6) for v in VARS if r.random() < 0.9}
            expected = run(prog, st, limit=60)
            got = S.evaluate(term, st, limit=60, trace=False)
            if expected is None:
                assert not got.defined, (src, st)
                checked_undefined += 1
            else:
                assert got.defined and got.state == expected, (src, st)
                checked_defined += 1
    assert checked_defined > 200 and checked_undefined > 20

