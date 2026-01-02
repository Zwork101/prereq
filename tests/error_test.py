"""Test exceptions raised by Prereq."""


from enum import Enum
from typing import Literal

import pytest

from prereq import provides


class A: ...


class Level(Enum):
    ONE = "ONE"
    TWO = "TWO"


def test_bad_return() -> None:
    with pytest.raises(TypeError):
        @provides
        def no_return(): ...  # pyright: ignore[reportUnusedFunction]  # noqa: ANN202

    @provides(coverage=[A])  # pyright: ignore[reportCallIssue, reportArgumentType, reportUntypedFunctionDecorator]
    def good_no_return(): ...  # noqa: ANN202  # pyright: ignore[reportUnusedFunction]

def test_literal() -> None:
    with pytest.raises(TypeError):
        @provides
        def literal_return() -> Literal["bad"]: ...  # pyright: ignore[reportUnusedFunction]


def test_bad_level() -> None:
    with pytest.raises(TypeError):
        @provides(level=Level.TWO)
        def weird_level() -> A: ...  # pyright: ignore[reportUnusedFunction]
