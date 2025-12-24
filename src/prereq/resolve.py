from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, AsyncContextManager, ContextManager, get_type_hints

from prereq.provide import AsyncProvider, Providers, SyncProvider, SyncProviderGen

try:
    from graphlib2 import TopologicalSorter

    def copy_graph[T](graph: TopologicalSorter[T]) -> TopologicalSorter[T]:  # pyright: ignore[reportRedeclaration]
        return graph.copy()
except ImportError:
    from copy import deepcopy
    from graphlib import TopologicalSorter

    def copy_graph[T](graph: TopologicalSorter[T]) -> TopologicalSorter[T]:
        return deepcopy(graph)


@dataclass(frozen=True, slots=True)
class Scope:

    parent: Scope | None
    level: int
    providers: MappingProxyType[type[Any], Providers]

    cache: dict[type[Any], Any] = field(default_factory=dict, init=False)
    _ctx: list[AsyncContextManager[type[Any]] | ContextManager[type[Any]]] = field(default_factory=list, init=False)

    async def get[T](self, typ: type[T]) -> T:
        if typ in self.cache:
            return self.cache[typ]  # pyright: ignore[reportAny]

        if (provider := self.providers.get(typ)) is None and self.parent:
            return await self.parent.get(typ)

        if provider is None:
            no_provider = f"Unable to locate provider for {typ=} at {self.level=}"
            raise RuntimeError(no_provider)
        
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


    async def collects(self, typs: dict[str, type[Any]]) -> dict[str, Any]:
        return {
            key: await self.get(val)
            for key, val in typs.items()
        }

    async def cleanup(self) -> None:
        for ctx in self._ctx:
            if isinstance(ctx, AsyncContextManager):
                _ = await ctx.__aexit__(None, None, None)
                continue
            _ = ctx.__exit__(None, None, None)
        self._ctx.clear()


@dataclass(slots=True, frozen=True)
class Resolver:

    level: int = 1
    parent: Scope | None = None
    _dep_map: dict[int, dict[type[Any], Providers]] = field(default_factory=lambda: defaultdict(dict))

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[Resolver]:
        
        scope = self._create_scope()

        try:
            yield Resolver(
                self.level + 1,
                scope,
                self._dep_map
            )
        finally:
            await scope.cleanup()

    def add_providers(self, *providers: Providers) -> None:
        for provider in providers:
            self._dep_map[provider.level].update(dict.fromkeys(provider.coverage, provider))

    def inject_const(self, target: type[Any], value: Any, level: int | None = None) -> None:  # pyright: ignore[reportAny]
        self._dep_map[level or self.level][target] = SyncProvider(
            [target],
            {},
            self.level,
            never_cache=False,
            factory=lambda: value  # pyright: ignore[reportAny]
        )

    def _create_scope(self) -> Scope:
        return Scope(
            parent=self.parent,
            level=self.level,
            providers=MappingProxyType(
                self._dep_map[self.level]
            ),
        )

    @asynccontextmanager
    async def resolve(self, func: Callable[..., Any]) -> AsyncGenerator[dict[str, Any]]:
        scope = self._create_scope()

        hints: dict[str, type[Any]] = get_type_hints(func)
        if "return" in hints:
            del hints["return"]

        try:
            yield await scope.collects(hints)
        finally:
            await scope.cleanup()
