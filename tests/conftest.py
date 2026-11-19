import pathlib

import pytest

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def example():
    def read(name: str) -> str:
        return (EXAMPLES / name).read_text(encoding="utf-8")
    return read
