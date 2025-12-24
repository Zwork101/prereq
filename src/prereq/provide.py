
from abc import ABC
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Generator, Iterator
from contextlib import asynccontextmanager, contextmanager
from enum import Enum
from inspect import isasyncgenfunction, isclass, iscoroutinefunction, isgeneratorfunction, signature
from typing import Any, AsyncContextManager, ContextManager, Literal, NamedTuple, Protocol, get_origin, get_type_hints, overload

class ProviderSpec[T, F: Callable[..., Any]](NamedTuple):
    coverage: list[type[T] | type[Any]]
    args: dict[str, type[Any]]
    level: int
    never_cache: bool
    factory: F


class SyncProvider[**P, T](ProviderSpec[T, Callable[P, T]]):
    def __call__(self, *args: P.args, **kwds: P.kwargs) -> T:
        return self.factory(*args, **kwds)


class SyncProviderGen[**P, T](ProviderSpec[T, Callable[P, Iterator[T]]]):

    def __call__(self, *args: P.args, **kwds: P.kwargs) -> ContextManager[T]:
        return contextmanager(self.factory)(*args, **kwds)


class AsyncProvider[**P, T](ProviderSpec[T, Callable[P, Awaitable[T]]]):

    async def __call__(self, *args: P.args, **kwds: P.kwargs) -> T:
        return await self.factory(*args, **kwds)


class AsyncProviderGen[**P, T](ProviderSpec[T, Callable[P, AsyncIterator[T]]]):

    def __call__(self, *args: P.args, **kwds: P.kwargs) -> AsyncContextManager[T]:
        return asynccontextmanager(self.factory)(*args, **kwds)


def _get_parents(typ: type[Any]) -> list[Any]:
    stop_types = (object, type, Protocol, ABC)
    total: list[type[Any]] = []
    for base in typ.__bases__:
        if base not in stop_types:
            total.append(base)
            total += _get_parents(base)

    return total

Providers = SyncProvider[Any, Any] | SyncProviderGen[Any, Any] | AsyncProvider[Any, Any] | AsyncProviderGen[Any, Any]

class ProviderWrapper[**P, T](Protocol):

    @overload
    @staticmethod
    def __call__(factory: Callable[P, Awaitable[T]]) -> AsyncProvider[..., Any]: ...

    @overload
    @staticmethod
    def __call__(factory: Callable[P, AsyncGenerator[T]]) -> AsyncProviderGen[..., Any]: ...

    @overload
    @staticmethod
    def __call__(factory: Callable[P, Generator[T]]) -> SyncProviderGen[..., Any]: ...

    @overload
    @staticmethod
    def __call__(factory: Callable[P, T]) -> SyncProvider[..., Any]: ...


@overload
def provides[**P, T](  # pyright: ignore[reportOverlappingOverload]
    factory: Callable[P, Awaitable[T]],
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> AsyncProvider[P, T]: ...

@overload
def provides[**P, T](
    factory: Callable[P, AsyncIterator[T]],
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> AsyncProviderGen[P, T]: ...

@overload
def provides[**P, T](
    factory: Callable[P, Iterator[T]],
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> SyncProviderGen[P, T]: ...

@overload
def provides[**P, T](
    factory: Callable[P, T],
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> SyncProvider[P, T]: ...

@overload
def provides[**P, T](
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> ProviderWrapper[P, T]: ...

def provides[**P, T](
    factory: None | \
             Callable[P, Awaitable[T]] | \
             Callable[P, AsyncIterator[T]] | \
             Callable[P, Iterator[T]] | \
             Callable[P, T] = None,
    *,
    level: int | Enum = 1,
    coverage: list[type[T] | type[Any]] | None = None,
    cover_parents: bool = True,
    never_cache: bool = False,
) -> AsyncProvider[P, T] | \
     AsyncProviderGen[P, T] | \
     SyncProviderGen[P, T] | \
     SyncProvider[P, T] | \
     ProviderWrapper[P, T]:
     
    def create_provider(
        factory: Callable[P, Awaitable[T]] | \
                 Callable[P, AsyncIterator[T]] | \
                 Callable[P, Iterator[T]] | \
                 Callable[P, T]
    ) -> AsyncProvider[P, T] | \
         AsyncProviderGen[P, T] | \
         SyncProviderGen[P, T] | \
         SyncProvider[P, T]:
        nonlocal coverage, level, cover_parents, never_cache
        sign = signature(factory)
        hints = get_type_hints(factory)
        
        for param in sign.parameters:
            if param not in hints:
                include = f"{factory} must include type signature for {param}"
                raise TypeError(include)

        if coverage is None:
            missing_return = f"{factory} is missing a return type annotation."
            returns: type[Any] | None = sign.return_annotation  # pyright: ignore[reportAny]
            if hasattr(returns, "__args__"):
                returns = returns.__args__[0]  # pyright: ignore[reportOptionalMemberAccess, reportAny]

            if returns is None:
                raise TypeError(missing_return)

            no_literal = f"{factory} cannot provide a Literal value."
            if get_origin(returns) is Literal:
                raise TypeError(no_literal)

            coverage = [returns]

            if cover_parents:
                coverage += _get_parents(returns)

        if "return" in hints:
            del hints["return"]

        if isinstance(level, Enum):
            if not isinstance(level.value, int):  # pyright: ignore[reportAny]
                bad_enum = f"Enum levels must be integers, not {level.value}"  # pyright: ignore[reportAny]
                raise TypeError(bad_enum)
            level = level.value

        if any(not isclass(val) for val in hints.values()):  # pyright: ignore[reportAny]
            bad_args = f"{factory} has non-class arguements."
            raise TypeError(bad_args)

        if isasyncgenfunction(factory):
            return AsyncProviderGen[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory
            )
        if iscoroutinefunction(factory):
            return AsyncProvider[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory
            )
        if isgeneratorfunction(factory):
            return SyncProviderGen[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory
            )
        return SyncProvider[P, T](
            coverage=coverage,
            args=hints,
            level=level,
            never_cache=never_cache,
            factory=factory  # pyright: ignore[reportArgumentType]
        )

    if factory is not None:
        return create_provider(factory)
    return create_provider  # pyright: ignore[reportReturnType]
