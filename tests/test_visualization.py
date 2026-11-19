import json
import xml.etree.ElementTree as ET

import pytest

import sipl
from sipl import visualization as V

SRC = "begin\n  while ¬(M = N) do\n    if M > N then M := M - N else N := N - M\nend"


@pytest.fixture
def tree():
    return sipl.parse_tree(SRC)


def test_text_shows_rules_and_fragments(tree):
    out = V.to_text(tree, SRC)
    assert out.splitlines()[0].startswith("<програма> [NP1]")
    assert "<оператор> [NS4]" in out and "<оператор> [NS3]" in out
    assert "└──" in out and "├──" in out


def test_json_is_valid_and_spans_match_source(tree):
    data = json.loads(V.to_json(tree, SRC))
    assert data["tree"]["rule"] == "NP1"
    assert data["grammar"]["NS4"].startswith("<оператор> ::= while")

    def check(node):
        s = node["span"]
        assert SRC[s["start"]:s["end"]] == node["text"]
        for c in node.get("children", []):
            check(c)

    check(data["tree"])


def test_dot_has_node_and_edge_per_tree_node(tree):
    dot = V.to_dot(tree, SRC)
    n_nodes = sum(1 for _ in tree.walk())
    assert dot.startswith("digraph ParseTree {") and dot.rstrip().endswith("}")
    assert dot.count("->") == n_nodes - 1
    assert dot.count("[shape=") == n_nodes
    assert dot.count("{") == dot.count("}")


def test_dot_escapes_quotes():
    src = "begin x := 1 end"
    dot = V.to_dot(sipl.parse_tree(src), src)
    assert '"' in dot and '\\"' not in dot



def test_all_formats_registered():
    assert set(V.FORMATS) == {"text", "json", "dot"}
