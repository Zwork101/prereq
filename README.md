# Prereq

Prereq is a dependency injection library for Python that is uncomplicated, and async-first.

### [Full Documentation Here](https://prereq.readthedocs.io/en/latest/)

## Installation

Use your favorite package manager to install prereq.

```bash
pip install prereq
# Or
uv add prereq
```

## Usage

To get started with Prereq, you just need to create a Provider, and a Resolver. Behavior is inferred based on typing. 

```python
import asyncio
from prereq import provides, Resolver

class User: ...

@provides
def user_factory() -> User:
    return User()

def update_user(user: User) -> None:
    print(f"Updated {user}")

resolver = Resolver()
resolver.add_providers(user_factory)

async def main() -> None:
    async with resolver.resolve(update_user) as kwargs:
        update_user(**kwargs)

asyncio.run(main())

```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Pull requests must pass ruff, and avoid ignoring pyright errors (but it may be needed, I understand.). You may need to add tests to maintain Prereq's 100% coverage.

## License

Prepreq is free and open source using the [MIT](LICENSE.md) license.