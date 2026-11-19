import pytest

import sipl
from sipl import ast as A
from sipl import unparse
from sipl.errors import SiplSyntaxError

VALID = [
    "begin skip end",
    "begin x := 1 end",
    "begin x := -5 end",
    "begin x := y + 1 * 2 end",
    "begin x := (y + 1) * 2 end",
    "begin x := y div 2 end",
    "begin x := 1; y := 2; z := 3 end",
    "begin if x > 1 then x := 1 else y := 2 end",
    "begin while x > 0 do x := x - 1 end",
    "begin while ¬(x = y) do x := x + 1 end",
    "begin while not x = y or x > 3 do skip end",
    "begin while (x + 1) > 2 do skip end",
    "begin while ((x > 1)) do skip end",
    "begin begin skip end end",
    "begin x := 1 // коментар\n; y := 2 end",
    "begin while x > 1 ∨ y = 2 do x := x – 1 end",
    "begin if (x > 1) ∨ (y > 1) then skip else skip end",
]

INVALID = [
    ("", "begin"),
    ("begin end", "оператор"),
    ("begin x := end", "вираз"),
    ("begin x := 1; end", "оператор"),
    ("begin x = 1 end", "':='"),
    ("begin x := (1 end", "')'"),
    ("begin while x do skip end", "порівняння"),
    ("begin while x > 1 skip end", "'do'"),
    ("begin if x > 1 then skip end", "'else'"),
    ("begin x := 1 end end", "зайвий"),
    ("begin x := 1", "'end'"),
    ("begin x := @ end", "невідомий символ"),
    ("x := 1", "'begin'"),
    ("begin while (x > 1 do skip end", "')'"),
    ("begin x := 1 + end", "вираз"),
    ("begin 1 := x end", "оператор"),
]


@pytest.mark.parametrize("src", VALID)
def test_valid_programs_parse(src):
    assert sipl.check(src) == []
    prog = sipl.parse(src)
    assert isinstance(prog, A.Program)


@pytest.mark.parametrize("src,fragment", INVALID)
def test_invalid_programs_report_position(src, fragment):
    diags = sipl.check(src)
    assert len(diags) == 1
    d = diags[0]
    assert fragment in d.message
    assert d.span.line >= 1 and d.span.col >= 1
    with pytest.raises(SiplSyntaxError):
        sipl.parse(src)


def test_error_position_is_precise():
    src = "begin\n  x := 1;\n  y := ;\nend"
    d = sipl.check(src)[0]
    assert (d.span.line, d.span.col) == (3, 8)
    assert "^" in d.render(src, "t.sipl")


def test_arithmetic_precedence_and_associativity():
    e = sipl.parse("begin x := 1 + 2 * 3 - 4 end").body.value
   
    assert isinstance(e, A.BinOp) and e.op == "-"
    assert e.left == A.BinOp("+", A.Num(1), A.BinOp("*", A.Num(2), A.Num(3)))
    assert e.right == A.Num(4)


def test_subtraction_is_left_associative():
    e = sipl.parse("begin x := 10 - 3 - 2 end").body.value
    assert e == A.BinOp("-", A.BinOp("-", A.Num(10), A.Num(3)), A.Num(2))


def test_negation_binds_weaker_than_comparison_and_stronger_than_or():
    c = sipl.parse("begin while ¬ x > 1 ∨ y = 2 do skip end").body.cond
    assert isinstance(c, A.Or)
    assert c.left == A.Not(A.Compare(">", A.Var("x"), A.Num(1)))
    assert c.right == A.Compare("=", A.Var("y"), A.Num(2))


def test_sequence_binds_weakest():
    s = sipl.parse("begin while x > 0 do x := x - 1; y := 1 end").body
    assert isinstance(s, A.Seq)
    assert isinstance(s.first, A.While) and isinstance(s.second, A.Assign)


def test_if_branches_are_single_statements():
    s = sipl.parse("begin if x > 0 then x := 1 else x := 2; y := 3 end").body
    assert isinstance(s, A.Seq) and isinstance(s.first, A.If)


def test_parenthesised_comparison_vs_expression():
    a = sipl.parse("begin while (x + 1) > 2 do skip end").body.cond
    assert isinstance(a, A.Compare) and isinstance(a.left, A.ParenExpr)
    b = sipl.parse("begin while (x > 1) ∨ (y > 1) do skip end").body.cond
    assert isinstance(b, A.Or) and isinstance(b.left, A.ParenCond)


def test_ast_equality_ignores_spans():
    a = sipl.parse("begin x := 1 end")
    b = sipl.parse("begin\n   x   :=   1\nend")
    assert a == b and a.span != b.span


def test_spans_cover_the_right_source_fragment():
    src = "begin\n  x := y + 1;\n  skip\nend"
    prog = sipl.parse(src)
    seq = prog.body
    assert seq.first.span.text(src) == "x := y + 1"
    assert seq.first.value.span.text(src) == "y + 1"
    assert seq.second.span.text(src) == "skip"
    assert prog.span.text(src) == src


def test_parse_tree_uses_book_rule_names():
    tree = sipl.parse_tree("begin x := 1 + 2; skip end")
    rules = {n.rule for n in tree.walk() if n.rule}
    assert {"NP1", "NS2", "NS1", "NA3", "NA1", "NS6", "NV", "NN"} <= rules
    assert tree.rule == "NP1" and tree.children[0].symbol == "begin"


def test_parse_tree_leaves_reproduce_source_tokens():
    src = "begin while ¬(x = y) do x := x + 1 end"
    leaves = [n.symbol for n in sipl.parse_tree(src).leaves()]
    assert leaves == ["begin", "while", "¬", "(", "x", "=", "y", ")", "do", "x", ":=", "x", "+", "1", "end"]


def test_deeply_nested_parentheses_are_fast():
    src = "begin while " + "(" * 40 + "x > 1" + ")" * 40 + " do skip end"
    assert sipl.check(src) == []


@pytest.mark.parametrize("src", VALID)
def test_unparse_roundtrip(src):
    prog = sipl.parse(src)
    again = sipl.parse(unparse.program(prog))
    assert again == prog


def test_variables_in_order_of_appearance():
    prog = sipl.parse("begin z := x + y; x := z end")
    assert A.variables(prog) == ["z", "x", "y"]
