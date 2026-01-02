"""Test Asynchronous Functions."""

from collections import Counter
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Protocol

from prereq import (
    AsyncProvider,
    AsyncProviderGen,
    Resolver,
    provides,
)


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


async def test_async() -> None:
    called_counter = Counter[str]()

    @provides(never_cache=True)
    async def create_a() -> A:
        called_counter["A"] += 1
        return A(value=10)

    assert isinstance(create_a, AsyncProvider)

    @provides
    async def create_b(a: A) -> AsyncGenerator[B]:
        called_counter["B"] += 1
        yield B(value=10 + a.value, name="B")

    assert isinstance(create_b, AsyncProviderGen)

    @provides
    async def create_c(a: A, b: B) -> C:
        called_counter["C"] += 1
        return C(value=10 + a.value + b.value)

    assert isinstance(create_c, AsyncProvider)

    @provides
    async def create_d(a: A, b: B, c: C) -> D:
        called_counter["D"] += 1
        return D(value=10 + a.value + b.value + c.value)

    assert isinstance(create_d, AsyncProvider)

    def test_func(d: D) -> None:
        assert d.value == (10 + 10 + 20 + 40)

    resolver = Resolver()
    resolver.add_providers(
        create_a,
        create_b,
        create_c,
        create_d,
    )

    async with resolver.resolve(test_func) as kwargs:
        test_func(**kwargs)  # pyright: ignore[reportAny]

    assert called_counter == {
        "A": 3,
        "B": 1,
        "C": 1,
        "D": 1,
    }
