import pytest

import sipl
from sipl import proof
from sipl.proof import assertions as AS
from sipl.proof.assertions import (PAnd, PCmp, PFalse, PImp, PNot, POr, PTrue, eval_pred,
                                   parse_pred, pred_str, simplify)

needs_z3 = pytest.mark.skipif(not proof.HAVE_Z3, reason="потрібен z3-solver")

MUL = "begin p := 0; k := y; while k > 0 do begin p := p + x; k := k - 1 end end"
SUM = "begin s := 0; i := 0; while n > i do begin i := i + 1; s := s + i end end"
HALF = "begin c := 0; while n > 0 do begin n := n div 2; c := c + 1 end end"




@pytest.mark.parametrize("text", [
    "x = 1", "x != y", "x <= y + 1", "x >= 0 and y >= 0", "not x = 1", "x = 1 or y = 2 and z = 3",
    "x > 0 => y > 0", "(x + 1) * 2 > y", "(x > 1) or (y > 1)", "true", "false", "2 * s = n * (n + 1)",
    "x ≤ y ∧ y ≥ 0", "¬(x = y)", "x - -1 > 0",
])
def test_assertions_parse_and_roundtrip(text):
    p = parse_pred(text)
    assert parse_pred(pred_str(p)) == p


def test_assertion_precedence():
    p = parse_pred("a = 1 or b = 2 and c = 3")
    assert isinstance(p, POr) and isinstance(p.right, PAnd)
    q = parse_pred("a = 1 => b = 2 => c = 3")
    assert isinstance(q, PImp) and isinstance(q.right, PImp)   
    r = parse_pred("not a = 1 and b = 2")
    assert isinstance(r, PAnd) and isinstance(r.left, PNot)


@pytest.mark.parametrize("text", ["", "x", "x = ", "x = 1 and", "(x = 1", "x = 1 )", "x @ 1", "= 1"])
def test_assertion_errors(text):
    with pytest.raises(proof.AssertionSyntaxError):
        parse_pred(text)


def test_simplify():
    assert simplify(parse_pred("x = x")) == PTrue()
    assert simplify(parse_pred("1 > 2")) == PFalse()
    assert simplify(parse_pred("x > 0 and 1 = 1")) == parse_pred("x > 0")
    assert simplify(PImp(PTrue(), parse_pred("x > 0"))) == parse_pred("x > 0")
    assert simplify(PImp(parse_pred("x > 0"), PTrue())) == PTrue()


def test_substitution_is_capture_free_and_printed_with_parentheses():
    p = AS.subst(parse_pred("x * 2 = y"), "x", AS.parse_assertion_expr("a + 1"))
    assert pred_str(p) == "(a + 1) * 2 = y"


def test_eval_pred():
    assert eval_pred(parse_pred("x > 0 and y = 2"), {"x": 1, "y": 2})
    assert not eval_pred(parse_pred("x > 0 => y = 3"), {"x": 1, "y": 2})
    with pytest.raises(ZeroDivisionError):
        eval_pred(parse_pred("x div y = 1"), {"x": 1, "y": 0})




def test_vc_kinds_for_loop_with_variant():
    prog = sipl.parse(MUL)
    vcs = proof.generate(prog, parse_pred("y >= 0"), parse_pred("p = x * y"),
                         [parse_pred("p + x * k = x * y and k >= 0")], [AS.parse_assertion_expr("k")])
    assert [v.kind for v in vcs] == ["init", "preserve", "exit", "variant-nonneg", "variant-decrease"]
    init = vcs[0]
    assert pred_str(init.formula) == "y ≥ 0 ⇒ 0 + x * y = x * y ∧ y ≥ 0"


def test_assignment_substitution_in_preserve_vc():
    prog = sipl.parse(MUL)
    vcs = proof.generate(prog, PTrue(), PTrue(), [parse_pred("p + x * k = x * y")])
    pres = [v for v in vcs if v.kind == "preserve"][0]
    assert pred_str(pres.formula) == "p + x * k = x * y ∧ k > 0 ⇒ p + x + x * (k - 1) = x * y"


def test_wrong_number_of_invariants_is_a_spec_error():
    with pytest.raises(proof.SpecError):
        proof.verify(MUL, "true", "true", [])
    with pytest.raises(proof.SpecError):
        proof.verify("begin skip end", "true", "true", ["true"])


def test_program_without_loops_needs_no_invariant():
    r = proof.verify("begin x := x + 1 end", "x >= 0", "x >= 1", [])
    assert r.partial is True and r.total is True
    r = proof.verify("begin x := x + 1 end", "x >= 0", "x >= 2", [])
    assert r.partial is False 


def test_if_statement_wp():
    prog = "begin if x > y then m := x else m := y end"
    r = proof.verify(prog, "true", "m >= x and m >= y", [])
    assert r.partial is True


def test_nested_loops_get_invariants_in_textual_order():
    src = ("begin i := 0; s := 0; while n > i do begin j := 0; while i > j do begin s := s + 1; j := j + 1 end; "
           "i := i + 1 end end")
    r = proof.verify(src, "n >= 0", "s >= 0",
                     ["i >= 0 and s >= 0", "j >= 0 and s >= 0 and i >= 0"], ["n - i", "i - j"], test=False)
    assert [x.vc.loop_index for x in r.results].count(1) >= 4
    assert r.partial is True and r.total is True


@needs_z3
def test_division_requires_positive_divisor():
    bad = proof.verify("begin q := a div b end", "true", "true", [])
    d = bad.results[0]
    assert d.verdict.status == "invalid" and d.verdict.model["b"] <= 0
    ok = proof.verify("begin q := a div b end", "b > 0", "q * b <= a", [], test=False)
    assert ok.results[0].verdict.status == "valid" and ok.total is True




@needs_z3
@pytest.mark.parametrize("src,pre,post,inv,var", [
    (MUL, "y >= 0", "p = x * y", "p + x * k = x * y and k >= 0", "k"),
    (SUM, "n >= 0", "2 * s = n * (n + 1)", "2 * s = i * (i + 1) and i <= n", "n - i"),
    (HALF, "n >= 0", "c >= 0", "c >= 0 and n >= 0", "n"),
])
def test_correct_programs_are_proved(src, pre, post, inv, var):
    r = proof.verify(src, pre, post, [inv], [var])
    assert r.partial is True and r.total is True
    assert all(x.verdict.status == "valid" for x in r.results)
    assert r.tests.post_violation is None and r.tests.no_termination is None


@needs_z3
def test_wrong_invariant_gives_genuine_counterexample_to_the_condition():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p = x * y"], ["k"])
    bad = [x for x in r.results if x.verdict.status == "invalid"]
    assert {x.vc.kind for x in bad} == {"init", "preserve"}
    for x in bad:  
        m = {**{v: 0 for v in AS.pred_vars(x.vc.formula)}, **x.verdict.model}
        assert eval_pred(x.vc.antecedent, m) and not eval_pred(x.vc.consequent, m)
    
    assert r.partial is None and r.total is None
    assert "інваріант після ітерації: false" in r.render()


@needs_z3
def test_weak_invariant_fails_exit_condition():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["k >= 0"], ["k"])
    kinds = {x.vc.kind: x.verdict.status for x in r.results}
    assert kinds["exit"] == "invalid" and kinds["variant-decrease"] == "valid"


@needs_z3
def test_missing_variant_proves_only_partial_correctness():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p + x * k = x * y and k >= 0"])
    assert r.partial is True and r.total is None
    assert "не задано міру" in r.render()


@needs_z3
def test_bad_variant_is_rejected():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p + x * k = x * y and k >= 0"], ["y"])
    dec = [x for x in r.results if x.vc.kind == "variant-decrease"][0]
    assert dec.verdict.status == "invalid"
    assert r.partial is True and r.total is None


@needs_z3
def test_variant_must_be_nonnegative():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p + x * k = x * y and k >= 0"], ["0 - k"])
    nonneg = [x for x in r.results if x.vc.kind == "variant-nonneg"][0]
    assert nonneg.verdict.status == "invalid"




def test_dynamic_check_refutes_when_precondition_is_dropped():
    r = proof.verify(MUL, "true", "p = x * y", ["p + x * k = x * y and k >= 0"], ["k"])
    c = r.tests.post_violation
    assert c is not None and c.state_in["y"] < 0
    assert r.partial is False and r.total is False
    assert "ПОРУШЕННЯ ПІСЛЯУМОВИ" in r.render()


def test_dynamic_check_finds_minimal_counterexample():
    r = proof.verify(MUL, "true", "p = x * y", ["true"], ["k"])
    c = r.tests.post_violation
    assert sum(abs(v) for v in c.state_in.values()) == 2  


def test_nonterminating_loop_partially_but_not_totally_correct():
    src = "begin while 1 = 1 do skip end"
    r = proof.verify(src, "true", "false", ["true"], ["0"], backend="auto")
    assert r.partial is True           
    assert r.total is False             
    assert r.tests.no_termination.kind == "nonterminating"


def test_undefined_input_is_reported_as_termination_failure():
    r = proof.verify("begin x := 10 div y end", "true", "true", [])
    assert r.tests.no_termination is not None and "ділення" in r.tests.no_termination.reason




def test_bounded_backend_finds_counterexamples_and_never_claims_proof():
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p = x * y"], ["k"], backend="bounded", bound=4)
    st = {x.vc.kind: x.verdict.status for x in r.results}
    assert st["init"] == "invalid" and st["preserve"] == "invalid"
    good = proof.verify(MUL, "y >= 0", "p = x * y", ["p + x * k = x * y and k >= 0"], ["k"],
                        backend="bounded", bound=4)
    assert all(x.verdict.status == "bounded-ok" for x in good.results)
    assert good.partial is None and good.total is None 


def test_check_valid_basic():
    f = parse_pred("x > 0 and y > 0 => x + y > 0")
    assert proof.check_valid(f, backend="bounded", bound=5).status == "bounded-ok"
    g = parse_pred("x > 0 => x > 1")
    v = proof.check_valid(g, backend="bounded", bound=5)
    assert v.status == "invalid" and v.model == {"x": 1}


@needs_z3
def test_z3_proves_and_refutes():
    assert proof.check_valid(parse_pred("x > 0 and y > 0 => x + y > 0")).proved
    v = proof.check_valid(parse_pred("x > 0 => x > 1"))
    assert v.status == "invalid" and v.model["x"] == 1


def test_report_serialises_to_json():
    import json
    r = proof.verify(MUL, "y >= 0", "p = x * y", ["p + x * k = x * y and k >= 0"], ["k"])
    data = json.loads(r.to_json())
    assert data["partial_correctness"] in (True, None) and len(data["conditions"]) == 5


def test_without_z3_auto_backend_falls_back_to_bounded(monkeypatch):
    from sipl.proof import solver
    monkeypatch.setattr(solver, "HAVE_Z3", False)
    v = solver.check_valid(parse_pred("x > 0 => x > 1"))
    assert v.method == "bounded" and v.status == "invalid"
    with pytest.raises(RuntimeError):
        solver.check_valid(parse_pred("x = x"), backend="z3")
