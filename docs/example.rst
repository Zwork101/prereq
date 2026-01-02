Example
=======

.. code-block:: python
    :caption: Prereq Example

    from __future__ import annotations

    import asyncio
    import json
    import random
    from dataclasses import dataclass
    from enum import Enum
    from pathlib import Path
    from typing import TYPE_CHECKING, Any, NewType, Protocol, TextIO, TypedDict, override

    from prereq import Resolver, provides

    if TYPE_CHECKING:
        from collections.abc import Generator


    class Level(Enum):
        SESSION = 1
        REQUEST = 2


    UserID = NewType("UserID", str)

    class Config(TypedDict):
        db_path: str
        point_delta: int

    @provides
    async def create_config() -> Config:
        return {
            "db_path": "db.json",
            "point_delta": 10,
        }


    class Database(Protocol):

        def get(self, user_id: UserID, key: str) -> Any: ...

        def set(self, user_id: UserID, key: str, value: Any) -> None: ...  # pyright: ignore[reportAny]


    @dataclass
    class JSONDatabase(Database):
        file: TextIO

        @classmethod
        def create(cls, config: Config) -> Generator[JSONDatabase]:
            db_file = Path(config["db_path"])
            if not db_file.exists():
                _ = db_file.write_text(json.dumps({
                    "BOB": {
                        "name": "Bobby Tables",
                        "points": 900,
                    },
                    "ALICE": {
                        "name": "Alice Keys",
                        "points": 500,
                    },
                }))

            with open(db_file, "r+") as file:
                yield cls(file)


        @override
        def get(self, user_id: UserID, key: str) -> Any:
            _ = self.file.seek(0)
            return json.load(self.file)[user_id][key]  # pyright: ignore[reportAny]

        @override
        def set(self, user_id: UserID, key: str, value: Any) -> None:  # pyright: ignore[reportAny]
            _ = self.file.seek(0)
            data: dict[UserID, dict[str, Any]] = json.loads(  # pyright: ignore[reportAny]
                self.file.read(),
            )
            if user_id not in data:
                data[user_id] = {}
            data[user_id][key] = value
            _ = self.file.seek(0)
            _ = json.dump(data, self.file)

    db_create = provides(JSONDatabase.create, level=Level.REQUEST)


    @dataclass
    class User:
        user_id: UserID
        name: str
        points: int


    @provides(level=Level.REQUEST)
    def create_user(user_id: UserID, db: Database) -> User:
        return User(
            user_id=user_id,
            name=db.get(user_id, "name"),
            points=db.get(user_id, "points"),
        )

    session = Resolver()
    session.add_providers(
        create_config,
        db_create,
        create_user,
    )

    def add_points(user: User, db: Database, config: Config) -> None:
        db.set(user.user_id, "points", user.points + config["point_delta"])

    def remove_points(user: User, db: Database, config: Config) -> None:
        db.set(user.user_id, "points", user.points - config["point_delta"])

    USER_IDS: list[str] = ["BOB", "ALICE"]

    async def main() -> None:
        selected_user = random.choice(USER_IDS)
        print(f"Changing points for {selected_user}")
        change = random.choice((add_points, remove_points))
        print(f"Performing {change.__name__} operation.")

        async with (
            session({UserID: selected_user}) as request,
            request.resolve(change) as kwargs,
        ):
            change(**kwargs)

        print("Updated random user!")

    if __name__ == "__main__":
        asyncio.run(main())

