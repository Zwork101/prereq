Tutorial
========

To begin dependency injection, you'll need to configure your dependency providers. Providers are functions that return,
or yield only once, an instance of the type they're providing. Say we have the following type:

.. code-block:: python
    :caption: Example Type

    from dataclass import dataclass
    from typing import Protocol, final

    class Database(Protocol):
        uri: str

        def get_items(self) -> list[str]: ...

        def write_item(self, item: str) -> None: ...

    @dataclass(slots=True)
    class JSONDatabase(Database):
        uri: str

        def close(self) -> None:
            (implementation)

        def get_items(self) -> list[str]:
            (implementation)

        def write_item(self, item: str) -> None:
            (implementation)

`JSONDatabase` implements the `Database` protocol, and offers an additional `read_book` method. Creating parent Protocols
or abstract classes for your dependencies is preferred to maximize the benefits of dependency injection. However this
is not always feasible, especially for third-party tools. Then create a provider in one of two ways. You can create a
separate function:

.. code-block:: python
    :caption: Function Provider

    from collections.abc import Generator
    import os

    from prereq import provides

    @provides(level=2)
    def create_database() -> Generator[JSONDatabase]:
        db = JSONDatabase(os.environ["DB_URI"])
        try:
            yield db
        finally:
            db.close()

Or, create a class method on JSONDatabase and make that a provider.

.. code-block:: python
    :caption: Class Method Provider

    from collections.abc import Generator
    import os

    from prereq import provides

    @dataclass(slots=True)
    class JSONDatabase(Database):
        uri: str

        @provides(level=2)
        @classmethod
        def create_database(cls) -> Generator[JSONDatabase]:
            db = cls(os.environ["DB_URI"])
            try:
                yield db
            finally: # Try-finally isn't necessary for prereq, but a good practice all the same.
                db.close()

The function can also be async, and can return the value instead of yielding. In both of these examples, the a provider
is created **in the function namespace**. Meaning, in both examples, the create_database variable is not a function.
It is a special provider instance that contains relevant information about the provider to the resolver.

In these snippets, the provider will observe the return type notation. It takes the `JSONDatabase` return type,
and binds the resolver that type, and that type's parents. So create_database will provide for the `JSONDatabase`
type, and the `Database` type. To only provide to the `JSONDatabase` type, add the `cover_parents=False` kwargs.
Alternatively, you can directly set what types are provided using the `coverage` kwarg.

Setting `level=2` tells the resolvers to let the level 2 resolver handle this provider. What this means depends
entirely on how Prereq is being used. For example, a web server might have all app lifetime providers at level 1,
and request lifetime providers at level 2. Providers can have dependencies that are on the same level, a
lower level, but not a higher level. The default level is 1.

.. code-block:: python
    :caption: Good Example

    from enum import Enum

    # Instead of using magic numbers, Prereq can also read integer values from Enums
    class Level(Enum):
        PROCESS = 1
        EVENT = 2
        ACTION = 3

    @provides
    def config() -> Config: ...

    @provides(level=Level.EVENT)
    async def emailer(config: Config) -> Emailer: ...

.. code-block:: python
    :caption: Bad Example

    # This code is bad! It is strange, and won't work.

    @provides
    def config(emailer: Emailer) -> Config: ...

    @provides(level=Level.EVENT)
    async def emailer() -> Emailer: ...

When you've created your providers, you'll need to add them to a resolver.

.. code-block:: python
    :caption: Setting up a Resolver

    from prereq import Resolver

    resolver = Resolver()
    resolver.add_providers(
        create_database,
        config,
        emailer
    )
    # Or if a classmethod was used:
    # resolver.add_providers(JSONDatabase.create_database)

By default, this creates a level 1 Provider. It can resolve level 1 types, or create a child resolver. The child resolver is always
1 plus the previous resolver level.

.. code-block:: python
    :caption: Injecting dependencies

    def setup_logging(config: Config):
        ...

    async def send_emails(db: Database, emailer: Emailer):
        ...

    async def main():

        async with resolver.resolve(setup_logging) as kwargs:
            setup_logging(**kwargs)

        async with resolver() as level_two:
            async with level_two.resolve(send_emails) as kwargs:
                await send_emails(**kwargs)

            # Resolving level 1 from level 2 works fine!
            async with level_two.resolve(setup_logging) as kwargs:
                setup_logging(**kwargs)

And just like that, dependency injection is setup. Prereq does not call functions the dependencies are for, it 
will only provide the dependencies.

Potential Pitfalls
==================

Prereq isn't providing all the arguments in the function signature?
--------------------------------------------------------------------

This is likely the result of the following issues:

#. No provider exists for the type not being injected. It may not have been added to the Resolver, or added to an unrelated Resolver.
#. The provider operates at a higher level than the Resolver, and as such the Resolver could not find the provider.
#. The dependency is not typed, and therefore ignored by the Resolver.

How do I add a dependency for a primitive type? Or two different dependencies of the same type?
-----------------------------------------------------------------------------------------------

Both of these scenarios are unlikely, especially wanting to inject a primitive type. But, it can still be done in a few ways. The simplest is
to use :py:class:`typing.NewType` and create a subclass of the primitive or duplicate type.

.. code-block:: python
    :caption: NewType Example

    from typing import NewType

    from prereq import provides
    from sqlalchemy.orm import Session

    MemoryUsage = NewType("MemoryUsage", float)

    MariaSession = NewType("MariaSession", Session)
    PostgresSession = NewType("PostgresSession", Session)

    @provides
    def get_memory() -> MemoryUsage: ...

    @provides(cover_parents=False)
    def maria_connection() -> MariaSession: ...

    @provides(cover_parents=False)
    def postgres_connection() -> PostgresSession: ...
