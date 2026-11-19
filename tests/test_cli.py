import json

import pytest

from sipl.cli import EXIT_ERROR, EXIT_OK, EXIT_UNDEFINED, EXIT_UNPROVED, main
from sipl.proof import HAVE_Z3

import pathlib

EX = str(pathlib.Path(__file__).resolve().parent.parent / "examples") + "/"


def run(capsys, *argv):
    code = main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_check_ok_and_error(capsys):
    code, out, _ = run(capsys, "check", EX + "log.sipl")
    assert code == EXIT_OK and "коректна" in out
    code, _, err = run(capsys, "check", EX + "invalid/if_without_else.sipl")
    assert code == EXIT_ERROR and "3:1" in err and "'else'" in err


def test_check_json(capsys):
    code, out, _ = run(capsys, "check", EX + "invalid/extra_end.sipl", "--json")
    data = json.loads(out)
    assert code == EXIT_ERROR and data["ok"] is False
    assert data["diagnostics"][0]["span"]["line"] == 4


def test_parse_formats(capsys, tmp_path):
    for fmt, marker in [("text", "<програма> [NP1]"), ("json", '"rule": "NP1"'),
                        ("dot", "digraph ParseTree")]:
        code, out, _ = run(capsys, "parse", EX + "gcd.sipl", "-f", fmt)
        assert code == EXIT_OK and marker in out, fmt
    target = tmp_path / "t.dot"
    code, out, _ = run(capsys, "parse", EX + "gcd.sipl", "-f", "dot", "-o", str(target))
    assert code == EXIT_OK and out == "" and target.read_text(encoding="utf-8").startswith("digraph")


def test_parse_error_reports_and_fails(capsys):
    code, out, err = run(capsys, "parse", EX + "invalid/extra_end.sipl")
    assert code == EXIT_ERROR and out == "" and "extra_end.sipl:4:5" in err


def test_ast_json(capsys):
    code, out, _ = run(capsys, "ast", EX + "mult.sipl")
    data = json.loads(out)
    assert data["type"] == "Program" and data["children"][0]["type"] == "Seq"


def test_term_variants(capsys):
    code, out, _ = run(capsys, "term", EX + "log.sipl")
    assert out.startswith("AS^K(0̄) · WH(")
    code, out, _ = run(capsys, "term", EX + "log.sipl", "--explain")
    assert "NS_Stm_Wh" in out and "sem_P(P) = " in out
    code, out, _ = run(capsys, "term", EX + "log.sipl", "--style", "latex")
    assert "\\overline{0}" in out
    code, out, _ = run(capsys, "term", EX + "log.sipl", "--json")
    data = json.loads(out)
    assert data["term"].startswith("AS^K") and data["derivation"][0]["rule"] == "NS_Prog"


def test_eval_defined_trace_and_json(capsys):
    code, out, _ = run(capsys, "eval", EX + "log.sipl", "-s", "X=3,Y=7", "--trace")
    assert code == EXIT_OK and "AF_WH: p(st1) = false" in out
    assert out.strip().endswith("= [X ↦ 3, Y ↦ 2, K ↦ 1]")
    code, out, _ = run(capsys, "eval", EX + "gcd.sipl", "-s", "M=8,N=16", "--json")
    assert json.loads(out)["state"] == {"M": 8, "N": 8}


def test_eval_undefined_has_dedicated_exit_code(capsys, tmp_path):
    f = tmp_path / "loop.sipl"
    f.write_text("begin while 1 = 1 do skip end", encoding="utf-8")
    code, out, _ = run(capsys, "eval", str(f), "--limit", "50")
    assert code == EXIT_UNDEFINED and "не визначене" in out


def test_eval_bad_state(capsys):
    code, _, err = run(capsys, "eval", EX + "log.sipl", "-s", "X=abc")
    assert code == EXIT_ERROR and "--state" in err


@pytest.mark.skipif(not HAVE_Z3, reason="потрібен z3-solver")
def test_prove_with_spec_file(capsys):
    code, out, _ = run(capsys, "prove", EX + "mult.sipl", "--spec", EX + "spec_mult.json")
    assert code == EXIT_OK and "Повна коректність:    ДОВЕДЕНО" in out


@pytest.mark.skipif(not HAVE_Z3, reason="потрібен z3-solver")
def test_prove_with_flags_and_json(capsys):
    code, out, _ = run(capsys, "prove", EX + "sum.sipl", "--pre", "n >= 0",
                       "--post", "2 * s = n * (n + 1)",
                       "--inv", "2 * s = i * (i + 1) and i <= n", "--variant", "n - i", "--json")
    data = json.loads(out)
    assert code == EXIT_OK and data["total_correctness"] is True


def test_prove_refuted_and_unproved_exit_codes(capsys):
    code, out, _ = run(capsys, "prove", EX + "mult.sipl", "--post", "p = x * y",
                       "--inv", "p + x * k = x * y and k >= 0")      
    assert code == EXIT_ERROR and "ПОРУШЕННЯ ПІСЛЯУМОВИ" in out
    code, out, _ = run(capsys, "prove", EX + "mult.sipl", "--pre", "y >= 0", "--post", "p = x * y",
                       "--inv", "p = x * y", "--variant", "k")      
    assert code == EXIT_UNPROVED


def test_prove_spec_errors(capsys):
    code, _, err = run(capsys, "prove", EX + "mult.sipl", "--post", "p = x * y")
    assert code == EXIT_ERROR and "інваріант" in err
    code, _, err = run(capsys, "prove", EX + "mult.sipl", "--post", "p = ", "--inv", "true")
    assert code == EXIT_ERROR and "очікувалось" in err
    code, _, err = run(capsys, "prove", EX + "mult.sipl")
    assert code == EXIT_ERROR and "післяумова" in err


def test_missing_file(capsys):
    code, _, err = run(capsys, "check", "no_such_file.sipl")
    assert code == EXIT_ERROR and "не вдалося прочитати" in err


def test_stdin(capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("begin x := 1 end"))
    code, out, _ = run(capsys, "term", "-")
    assert code == EXIT_OK and out.strip() == "ASˣ(1̄)"


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "sipl 0.1.0" in capsys.readouterr().out
