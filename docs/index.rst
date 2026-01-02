Installing Prereq
=================

Prereq has no dependencies. Installing is as simple as:

.. code-block:: bash
   pip install prereq

   # Or

   uv add prereq

Prereq: What & Why?
===================

Prereq is a dependency injection library for Python. It enables the decoupling of resources, and the functions that require resources.
This comes with a `multitude of benefits <https://github.com/cosmicpython/book/blob/master/chapter_13_dependency_injection.asciidoc>`__
, best of all being very clean code!

.. code-block:: python
   :caption: Prereq Example

   import asyncio
   from database import session_maker, Session
   from prereq import provides, Resolver

   @provides
   def create_config() -> Session:
       with session_maker() as session:
           yield session

   resolver = Resolver()
   resolver.add_providers(create_config)

   def get_user(username: str, session: Session):
       return session.get_user(username)

   async def main():
       async with resolver.resolve(get_user) as kwargs:
           user = get_user("my_username", **kwargs)

   if __name__ == "__main__":
       asyncio.run(main())

Why Prereq?
***********

Python has no lack of dependency injection libraries. In fact,
there is a `great list on GitHub <https://github.com/sfermigier/awesome-dependency-injection-in-python>`__
if Prereq isn't what you need. So why create Prereq? In the process of working on another project,
I started looking for a system that best served my needs. I wanted a system that was easy to use, a system that
took advantage of Python typing, a system that provided dependency and didn't call functions, and a system which I
understood.

However, I struggled to find what I was looking for. The two largest projects,
`python-dependency-injector <https://github.com/ets-labs/python-dependency-injector>`__ and
`returns <https://github.com/dry-python/returns>`__ are huge libraries. Not bad libraries, but quickly exceed what I
was looking for. Small projects had other problems, such as `poor async support <https://www.neoteroi.dev/rodi/async/>`__,
`tricky APIs <https://github.com/scrapinghub/andi?tab=readme-ov-file#why-doesnt-andi-handle-creation-of-objects>`__, and
`scope-naive dependencies <https://maldoinc.github.io/wireup/latest/lifetimes_and_scopes/#creating-scopes>`__.

Those libraries are capable, but don't coincide with my needs. Later on I found `ididi <https://github.com/raceychan/ididi>`__,
which is close to what I wanted. But for reasons unknown to me, its implementation is complex, and contains
`undesirable magic <https://github.com/raceychan/ididi/blob/c43e6d8e79d61a8db8cc6e35f64345405216ae51/ididi/graph.py#L358>`__.
Disappointed but not deterred, I created Prereq with the following goals:

#. Offer all the benefits DI can provide.
#. Remain simple in design and scope.
#. First-class Async support.
#. Support multiple levels.
#. Use the best typing available.

You should not use Prereq if:

#. You don't want to use async.
#. You want additional non-DI features.
#. You need to inject positional-only parameters.
