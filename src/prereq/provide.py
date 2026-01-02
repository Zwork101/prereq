"""
The provider decorated, and providers.

To add a factory function or generator to a Resolver, it must
become a provider. This is accmplished by decorating the factories
with the provider decorator.
"""
from abc import ABC
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Iterator,
)
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
    contextmanager,
)
from enum import Enum
from inspect import (
    isasyncgenfunction,
    iscoroutinefunction,
    isgeneratorfunction,
)
from typing import (
    Any,
    Literal,
    NamedTuple,
    Protocol,
    get_origin,
    get_type_hints,
    overload,
)


class _ProviderSpec[T, F: Callable[..., Any]](NamedTuple):
    coverage: Iterable[type[T] | type[Any]]
    args: dict[str, type[Any]]
    level: int
    never_cache: bool
    factory: F


class SyncProvider[**P, T](_ProviderSpec[T, Callable[P, T]]):
    """
    Wrap a synchronous provider function.

    Attributes:
        coverage (Iterable[type[T | Any]]): The types this provider handles.
        args (dict[str, type[Any]]): The provider's arguement types.
        level (int): The level this provider operates on.
        never_cache (bool): If the provider should be cached after being called.
        factory (F): The function wrapped by this provider.

    """

    def __call__(self, *args: P.args, **kwds: P.kwargs) -> T:  # noqa: D102
        return self.factory(*args, **kwds)


class SyncProviderGen[**P, T](_ProviderSpec[T, Callable[P, Iterator[T]]]):
    """
    Wrap a synchronous context provider function.

    Attributes:
        coverage (Iterable[type[T | Any]]): The types this provider handles.
        args (dict[str, type[Any]]): The provider's arguement types.
        level (int): The level this provider operates on.
        never_cache (bool): If the provider should be cached after being called.
        factory (F): The generator which will become a context manager.

    """

    def __call__(self, *args: P.args, **kwds: P.kwargs) -> AbstractContextManager[T]:  # noqa: D102
        return contextmanager(self.factory)(*args, **kwds)


class AsyncProvider[**P, T](_ProviderSpec[T, Callable[P, Awaitable[T]]]):
    """
    Wrap an asynchronous provider function.

    Attributes:
        coverage (Iterable[type[T | Any]]): The types this provider handles.
        args (dict[str, type[Any]]): The provider's arguement types.
        level (int): The level this provider operates on.
        never_cache (bool): If the provider should be cached after being called.
        factory (F): The function wrapped by this provider.

    """

    async def __call__(self, *args: P.args, **kwds: P.kwargs) -> T:  # noqa: D102
        return await self.factory(*args, **kwds)


class AsyncProviderGen[**P, T](_ProviderSpec[T, Callable[P, AsyncIterator[T]]]):
    """
    Wrap an asynchronous context provider function.

    Attributes:
        coverage (Iterable[type[T | Any]]): The types this provider handles.
        args (dict[str, type[Any]]): The provider's arguement types.
        level (int): The level this provider operates on.
        never_cache (bool): If the provider should be cached after being called.
        factory (F): The async generator which will become a context manager.

    """

    def __call__(  # noqa: D102
        self,
        *args: P.args,
        **kwds: P.kwargs,
    ) -> AbstractAsyncContextManager[T]:
        return asynccontextmanager(self.factory)(*args, **kwds)


def _get_parents(typ: type[Any]) -> list[Any]:
    stop_types = (object, type, Protocol, ABC)
    total: list[type[Any]] = []

    for base in typ.__bases__:
        if base not in stop_types and hasattr(base, "__bases__"):
            total.append(base)
            total += _get_parents(base)

    return total

Providers = SyncProvider[Any, Any] |\
                       SyncProviderGen[Any, Any] |\
                       AsyncProvider[Any, Any] |\
                       AsyncProviderGen[Any, Any]

class _ProviderWrapper[**P, T](Protocol):

    @overload
    @staticmethod
    def __call__(factory: Callable[P, Awaitable[T]]) -> AsyncProvider[..., Any]: ...

    @overload
    @staticmethod
    def __call__(factory: Callable[P, AsyncGenerator[T]]) -> \
        AsyncProviderGen[..., Any]: ...

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
) -> _ProviderWrapper[P, T]: ...

def provides[**P, T](  # noqa: C901
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
     _ProviderWrapper[P, T]:
    """
    Create a provider from factory function or generator.

    This is a decorator that also supports being called. For example, you can do:

    .. code-block:: python
            :caption: With defaults.

            @provides
            def factory(a: A) -> Obj:
                return Obj()

    Or you can change the default arguments by calling the decorator.

    .. code-block:: python
            :caption: Changed defaults.

            @provides(level=2, never_cache=True)
            def factory(a: A) -> Obj:
                return Obj()

    This decorator consumes the function. This means that in the previous examples,
    `factory` is no longer a function, it would be a :py:class:`.SyncProvider`. If
    you're applying multiple decorators, this one should be the outer-most decorator
    from the function.

    Args:
        factory (Async/Sync function or context-manager compatible generator): The
            factory being decorated. If no factory is provided, a decorator is returned.
        level (int): The level this provider operates on. For example, a web server may
            have app level providers (1) and request level providers (2). Default is 1.
        coverage (list[type[T] | type[Any]] | None): The types this provider provides.
            If none are specified, it will be inferred from the factory return notation.
        cover_parents (bool): If coverage is inferred, this enables adding coverage for
            non-abstract inherited types of the return type. Default is True.
        never_cache (bool): Disables cacheing the provider in the given resolver scope.
            Default is False.

    Returns:
        (:py:class:`.AsyncProvider`): If the factory is an asynchronous function.

        (:py:class:`.AsyncProviderGen`): If the factory is an asynchronous generator.

        (:py:class:`.SyncProvider`): If the factory is a synchronous function.

        (:py:class:`.SyncProviderGen`): If the factory is a synchronous generator.

    """

    def create_provider(  # noqa: C901
        factory: Callable[P, Awaitable[T]] | \
                 Callable[P, AsyncIterator[T]] | \
                 Callable[P, Iterator[T]] | \
                 Callable[P, T],
    ) -> AsyncProvider[P, T] | \
         AsyncProviderGen[P, T] | \
         SyncProviderGen[P, T] | \
         SyncProvider[P, T]:
        nonlocal coverage, level, cover_parents, never_cache

        hints = get_type_hints(factory)

        if coverage is None:
            returns: type[Any] | None = hints.pop("return", None)  # pyright: ignore[reportAny]
            if hasattr(returns, "__args__"):
                returns = returns.__args__[0]  # pyright: ignore[reportOptionalMemberAccess, reportAny]

            if returns is None:
                missing_return = f"{factory} is missing a return type annotation."
                raise TypeError(missing_return)

            no_literal = f"{factory} cannot provide a Literal value."
            if get_origin(returns) is Literal:
                raise TypeError(no_literal)

            coverage = [returns]

            if cover_parents:
                coverage += _get_parents(returns)

        _ = hints.pop("return", None)  # pyright: ignore[reportAny]

        if isinstance(level, Enum):
            if not isinstance(level.value, int):  # pyright: ignore[reportAny]
                bad_enum = f"Enum levels must be integers, not {level.value}"  # pyright: ignore[reportAny]
                raise TypeError(bad_enum)
            level = level.value

        if isasyncgenfunction(factory):
            return AsyncProviderGen[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory,
            )
        if iscoroutinefunction(factory):
            return AsyncProvider[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory,
            )
        if isgeneratorfunction(factory):
            return SyncProviderGen[P, T](
                coverage=coverage,
                args=hints,
                level=level,
                never_cache=never_cache,
                factory=factory,
            )
        return SyncProvider[P, T](
            coverage=coverage,
            args=hints,
            level=level,
            never_cache=never_cache,
            factory=factory,  # pyright: ignore[reportArgumentType]
        )

    if factory is not None:
        return create_provider(factory)
    return create_provider  # pyright: ignore[reportReturnType]
