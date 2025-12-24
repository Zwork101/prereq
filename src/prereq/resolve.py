from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncGenerator, Callable, Collection, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from types import MappingProxyType
from typing import Any, AsyncContextManager, ContextManager, get_type_hints

from prereq.provide import AsyncProvider, Providers, SyncProvider, SyncProviderGen

@dataclass
class Scope:

    parent: Scope | None
    level: int
    cache: dict[type[Any], Any] = field(default_factory=dict)
    providers: dict[type[Any], Providers] = field(default_factory=dict)
    graph: dict[type[Any], tuple[type[Any], ...]] = field(default_factory=dict)
    _ctx: list[AsyncContextManager[type[Any]] | ContextManager[type[Any]]] = field(default_factory=list)

    def prepare(self, reqs: Iterable[tuple[type[Any], Providers]]) -> None:
        for req in reqs:
            if req[0] in self.graph:
                continue
            
            self.graph[req[0]] = tuple(req[1].args.values())
            self.providers[req[0]] = req[1]

    @classmethod
    def min_graph[K](cls, graph: Mapping[K, Iterable[K]], targets: Collection[K]) -> Mapping[K, Iterable[K]]:
        # This function is likely awful efficiency-wise
        new_targets: set[K] = set(targets)
        for target in targets:
            new_targets.update(graph[target])

        print(new_targets)

        if len(new_targets) == len(targets):
            return {k: v for k, v in graph.items() if k in new_targets}
        return cls.min_graph(graph, new_targets)


    async def get[T](self, typ: type[T]) -> T:
        if typ in self.cache:
            return self.cache[typ]  # pyright: ignore[reportAny]

        provider = self.providers[typ]

        if provider.level > self.level:
            too_low = f"{typ} is a level {provider.level} type, which is higher than this scope {self.level=}"
            raise ValueError(too_low)
        if provider.level < self.level:
            if self.parent is None:
                no_parent = f"Resolver at {self.level=} has no parent, and can't resolve lower type {typ}"
                raise ValueError(no_parent)

            return await self.parent.get(typ)

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
        
        if not provider.never_cache:
            self.cache[typ] = value
        return value  # pyright: ignore[reportAny]


    async def collects(self, typs: dict[str, type[Any]]) -> dict[str, Any]:
        print(self.graph, typs)
        print("graph", self.min_graph(self.graph, typs.values()))
        graph = TopologicalSorter(
            self.min_graph(self.graph, typs.values())
        )
        graph.prepare()

        result: dict[str, Any] = {}
        type_name = {val: key for key, val in typs.items()}

        while graph.is_active():
            nodes = graph.get_ready()

            for node in nodes:
                val = await self.get(node)  # pyright: ignore[reportAny]
                if name := type_name.get(node):
                    result[name] = val
                graph.done(node)

        return result

    async def cleanup(self) -> None:
        for ctx in self._ctx:
            if isinstance(ctx, AsyncContextManager):
                _ = await ctx.__aexit__(None, None, None)
                continue
            _ = ctx.__exit__(None, None, None)
        self._ctx.clear()


@dataclass
class Resolver:

    level: int = 1
    parent: Resolver | None = None
    _dep_map: dict[int, dict[type[Any], Providers]] = field(default_factory=lambda: defaultdict(dict))
    _scope: Scope | None = None

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[Resolver]:
        
        self._scope = self._create_scope()

        yield Resolver(
            self.level + 1,
            self,
            self._dep_map
        )

        await self._scope.cleanup()
        self._scope = None

    @property
    def deps(self) -> MappingProxyType[type[Any], Providers]:
        return MappingProxyType(self._dep_map[self.level])

    @property
    def scope(self) -> Scope:
        if self._scope is None:
            scope_error = f"Scope for resolver {self.level=} has not been created yet."
            raise ValueError(scope_error)
        return self._scope

    def add_provider(self, provider: Providers) -> None:
        self._dep_map[provider.level].update(dict.fromkeys(provider.coverage, provider))

    def _create_scope(self) -> Scope:
        if self.parent:
            scope = Scope(
                self.parent.scope,
                self.level,
                providers=self.parent.scope.providers,
                graph=self.parent.scope.graph
            )
        else:
            scope = Scope(
                None,
                self.level
            )
        scope.prepare(self.deps.items())
        return scope


    @asynccontextmanager
    async def resolve(self, func: Callable[..., Any]) -> AsyncGenerator[dict[str, Any]]:
        if self._scope is not None:
            in_use = f"{self} is currently being used by a subrouter, cannot currently resolve."
            raise RuntimeError(in_use)

        scope = self._create_scope()

        hints: dict[str, type[Any]] = get_type_hints(func)
        if "return" in hints:
            del hints["return"]

        
        yield await scope.collects(hints)

        await scope.cleanup()
