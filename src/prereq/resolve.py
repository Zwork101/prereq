"""
Resolver and Scope API.

Resolvers are "layers" which can create sublayers,
and manage their scope. Scopes use providers to
inject dependencies, and cache results. For most cases,
interacting with scopes is not nessesary, and only
resolvers should be used.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
)
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    get_type_hints,
)

from prereq.errors import ProviderNotFoundError
from prereq.provide import AsyncProvider, Providers, SyncProvider, SyncProviderGen

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping

@dataclass(frozen=True, slots=True)
class Scope:
    """
    Temporary cache and context manager.

    Scopes are created by Resolvers to manage a specific
    level's cache, and close context managers. A rounter
    creates a scope when initiating a sub router, as well
    as when it's resolving a function's params. Scopes do not
    themselves ensure that :py:meth:`prereq.resolve.Scope.cleanup`
    gets called. That should bew handled by the process using
    the scope.

    Attributes:
        parent (:py:class:`.Scope` | None): The previous level's scope, if applicable.
        level (int): The level this scope services.
        providers (MappingProxyType[type[Any], Providers]): Providers on
            this scope's level.
        cache (dict[type[Any], Any]): Instances of types which have already been
            gathered for this scope.

    """

    parent: Scope | None
    level: int
    providers: MappingProxyType[type[Any], Providers]

    cache: dict[type[Any], Any] = field(default_factory=dict, init=False)
    _ctx: list[
        AbstractAsyncContextManager[type[Any]] |\
        AbstractContextManager[type[Any]]
    ] = field(default_factory=list, init=False)

    async def get[T](self, typ: type[T]) -> T:
        """
        Create an instance of a type using a provider.

        This method will check this scope's providers to see if any
        support this type. If none do, it will pass the request off
        to the parent scope. The level associated with that type will
        then cache the result, if the provide has caching enabled.

        Args:
            typ (type[T]): The type that needs to be instantiated by a provider.

        Returns:
            T: Returns an instance of the requested type.

        Raises:
            ProviderNotFoundError: If no provider is found, and this scope has no
                parent, this error will be raised.

        """
        if typ in self.cache:
            return self.cache[typ]  # pyright: ignore[reportAny]

        if (provider := self.providers.get(typ)) is None and self.parent:
            return await self.parent.get(typ)

        if provider is None:
            no_provider = f"Unable to locate provider for {typ=} at {self.level=}"
            raise ProviderNotFoundError(no_provider)

        keywords = {
            key: await self.get(val)
            for key, val in provider.args.items()
        }

        if isinstance(provider, SyncProvider):
            value = provider(**keywords)  # pyright: ignore[reportAny]
        elif isinstance(provider, AsyncProvider):
            value = await provider(**keywords)  # pyright: ignore[reportAny]
        elif isinstance(provider, SyncProviderGen):
            ctx = provider(**keywords)
            self._ctx.append(ctx)
            value = ctx.__enter__()  # pyright: ignore[reportAny]
        else:
            ctx = provider(**keywords)
            self._ctx.append(ctx)
            value = await ctx.__aenter__()  # pyright: ignore[reportAny]

        if not provider.never_cache and provider.level == self.level:
            self.cache[typ] = value
        return value  # pyright: ignore[reportAny]

    async def cleanup(self) -> None:
        """
        Resolve pending context managers.

        Some providers are context managers that need to be exited when
        the scope is left. This method exits all pending context managers
        created by the scope.
        """
        for ctx in self._ctx:
            if isinstance(ctx, AbstractAsyncContextManager):
                _ = await ctx.__aexit__(None, None, None)
                continue
            _ = ctx.__exit__(None, None, None)
        self._ctx.clear()


@dataclass(slots=True, frozen=True)
class Resolver:
    """
    The dependency injector.

    Resolvers hold on to providers, and create / manage scopes.
    Resolvers also allow for easy creation of subresolvers. Because scopes
    are ephemeral and internal, resolvers do not provide any method to
    access their temporary scopes.

    Attributes:
        level (int): The level this resolver operates on. Defaults to level 1.

    """

    level: int = 1
    _parent: Scope | None = None
    _dep_map: dict[
        int,
        dict[type[Any], Providers],
    ] = field(default_factory=lambda: defaultdict(dict))

    @asynccontextmanager
    async def __call__(
        self,
        cache: Mapping[Any, Any] | None = None,
    ) -> AsyncGenerator[Resolver]:
        """
        Create a sub-resolver, and handle subresolver cleanup.

        Subresolvers share providers with their parent, but will only access providers
        at their level. Adding a provider to a subresolver adds it to all related
        resolvers.

        .. code-block:: python
            :caption: Creating a sub-resolver.

            primary = Resolver()
            async with primary() as secondary:
                print(primary.level)   # prints "1"
                print(secondary.level) # prints "2"

        Args:
            cache (dict[type[Any], Any], optional): Optional premade cache to set
                constant values. Defaults to None.

        Yields:
            :py:class:`.Resolver`: Subresolver, level incremented by 1.

        """
        scope = self._create_scope()
        if cache:
            scope.cache.update(cache)

        try:
            yield Resolver(
                self.level + 1,
                scope,
                self._dep_map,
            )
        finally:
            await scope.cleanup()

    def add_providers(self, *providers: Providers) -> None:
        """
        Add providers to the resolver.

        Providers are functions decorated with
        :py:func:`prereq.provides`. Providers will be made accessible to
        resolvers related to this resolver at the same level as the provider.

        Args:
            *providers (:ref:`Providers`): Functions decorated with
                :py:func:`prereq.provides`.

        """
        for provider in providers:
            self._dep_map[provider.level].update(
                dict.fromkeys(provider.coverage, provider),
            )

    def _create_scope(self) -> Scope:
        return Scope(
            parent=self._parent,
            level=self.level,
            providers=MappingProxyType(
                self._dep_map[self.level],
            ),
        )

    @asynccontextmanager
    async def resolve(
        self,
        func: Callable[..., Any],
        cache: dict[type[Any], Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """
        Create keyword arguements for a function using providers.

        This function is an context manager, and should be used as following:

        .. code-block:: python
            :caption: Resolve example.

            async with resolver.resolve(func) as kwargs:
                func(**kwargs)

        Any untyped arguements, or missing dependencies, will be ignored.

        Args:
            func (Callable[..., Any]): The function to get dependencies for.
            cache (dict[type[Any], Any], optional): An optional premade cache to set
                constant values. Defaults to None.

        Yields:
            (dict[str, Any]): The dependencies for the function's parameters, except for
            non-typed parameters.

        """
        scope = self._create_scope()
        if cache:
            scope.cache.update(cache)

        hints: dict[str, type[Any]] = get_type_hints(func)
        _ = hints.pop("return", None)
        resolved: dict[str, Any] = {}

        try:
            for key, val in hints.items():
                try:
                    value = await scope.get(val)  # pyright: ignore[reportAny]
                except ProviderNotFoundError:
                    continue
                resolved[key] = value

            yield resolved
        finally:
            await scope.cleanup()
