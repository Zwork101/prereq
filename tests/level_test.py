"""Test Synchronous Functions."""

from collections import Counter
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import pytest

from prereq import Resolver, provides


@dataclass
class A:
    value: int

class NamedValue(Protocol):
    value: int
    name: str


@dataclass
class B(NamedValue):
    value: int
    name: str


@dataclass
class C:
    value: int


@dataclass
class D:
    value: int

class EnumLevel(Enum):
    ONE = 1
    TWO = 2
    THREE = 3


@pytest.mark.parametrize(
    "levels",
    [
        [1, 2, 3],
        [EnumLevel.ONE, EnumLevel.TWO, EnumLevel.THREE],
    ],
)
async def test_level(levels: list[int | EnumLevel]) -> None:
    called_counter = Counter[str]()

    @provides(never_cache=True)
    async def create_a() -> A:
        called_counter["A"] += 1
        return A(value=10)

    @provides(level=levels[1])
    def create_b(a: A) -> Generator[B]:
        called_counter["B"] += 1
        yield B(value=10 + a.value, name="B")

    @provides(level=levels[1])
    def create_c(a: A, b: B) -> C:
        called_counter["C"] += 1
        return C(value=10 + a.value + b.value)

    @provides(level=levels[2])
    def create_d(a: A, b: B, c: C) -> D:
        called_counter["D"] += 1
        return D(value=10 + a.value + b.value + c.value)

    def test_func(a: A, b: B, c: C, d: D) -> None: ...  # pyright: ignore[reportUnusedParameter]

    resolver = Resolver()
    resolver.add_providers(
        create_a,
        create_b,
        create_c,
        create_d,
    )

    async with resolver.resolve(test_func) as kwargs:
        assert [*kwargs.keys()] == ["a"]

    async with (
        resolver() as second,
        second.resolve(test_func) as kwargs,
    ):
        assert [*kwargs.keys()] == ["a", "b", "c"]

    async with (
        resolver() as second,
        second() as third,
        third.resolve(test_func) as kwargs,
    ):
        assert [*kwargs.keys()] == ["a", "b", "c", "d"]

    async with resolver.resolve(test_func) as kwargs:
        assert [*kwargs.keys()] == ["a"]
