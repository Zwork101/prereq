import asyncio
from collections.abc import AsyncGenerator, Generator
from enum import Enum
from prereq import provides, Resolver


class Level(Enum):
    APP = 1
    REQUEST = 2
    FUNC = 3


class A:
    pass


class B:
    pass


class C:
    pass


@provides
def create_a() -> Generator[A]:
    print("Starting A")
    yield A()
    print("Ending A")


@provides(level=Level.APP, never_cache=True)
async def create_b(a: A) -> B:
    print("Getting B")
    return B()

@provides(level=Level.REQUEST)
async def create_c(a: A, b: B) -> AsyncGenerator[C]:
    print("Starting C")
    yield C()
    print("Ending C")

def gimme(a: A, b: B, c: C) -> str:
    return "done"

resolver = Resolver()
resolver.add_providers(
    create_a,
    create_b,
    create_c
)

async def main() -> None:
    async with resolver() as subresolver:
        async with subresolver.resolve(gimme) as kwargs:
            print(kwargs)
            print(gimme(**kwargs))


if __name__ == "__main__":
    asyncio.run(main())
