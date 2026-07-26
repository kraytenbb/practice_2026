from sqlalchemy import inspect
from sqlalchemy import text
from database import engine
from models import User


def table_exists(table_name: str) -> bool:
    inspector = inspect(engine)

    return inspector.has_table(table_name)


def get_column_names(table_name: str) -> set[str]:
    inspector = inspect(engine)

    if not inspector.has_table(table_name):
        return set()

    return {
        column["name"]
        for column in inspector.get_columns(table_name)
    }


def drop_old_users_table() -> None:
    with engine.begin() as connection:
        if table_exists("users"):
            connection.execute(
                text(
                    """
                    DROP TABLE users CASCADE
                    """
                )
            )

            print(
                "Старая таблица users удалена."
            )
        else:
            print(
                "Старая таблица users не найдена."
            )


def create_users_table() -> None:
    User.__table__.create(
        bind=engine,
        checkfirst=True
    )

    print(
        "Новая таблица users создана."
    )


def add_user_id_to_library() -> None:
    columns = get_column_names("library")

    if "user_id" in columns:
        print(
            "Столбец library.user_id уже существует."
        )

        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE library
                ADD COLUMN user_id INTEGER
                """
            )
        )

    print(
        "Добавлен столбец library.user_id."
    )


def add_user_id_to_history() -> None:
    columns = get_column_names(
        "reading_history"
    )

    if "user_id" in columns:
        print(
            "Столбец reading_history.user_id "
            "уже существует."
        )

        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE reading_history
                ADD COLUMN user_id INTEGER
                """
            )
        )

    print(
        "Добавлен столбец "
        "reading_history.user_id."
    )


def constraint_exists(
    constraint_name: str
) -> bool:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = :constraint_name
                )
                """
            ),
            {
                "constraint_name": constraint_name
            }
        )

        return bool(
            result.scalar()
        )


def add_library_foreign_key() -> None:
    constraint_name = (
        "fk_library_user_id"
    )

    if constraint_exists(
        constraint_name
    ):
        print(
            "Внешний ключ library.user_id "
            "уже существует."
        )

        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE library
                ADD CONSTRAINT fk_library_user_id
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
                """
            )
        )

    print(
        "Добавлен внешний ключ "
        "library.user_id → users.id."
    )


def add_history_foreign_key() -> None:
    constraint_name = (
        "fk_reading_history_user_id"
    )

    if constraint_exists(
        constraint_name
    ):
        print(
            "Внешний ключ "
            "reading_history.user_id "
            "уже существует."
        )

        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE reading_history
                ADD CONSTRAINT fk_reading_history_user_id
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
                """
            )
        )

    print(
        "Добавлен внешний ключ "
        "reading_history.user_id → users.id."
    )


def verify_users_table() -> None:
    if not table_exists("users"):
        raise RuntimeError(
            "Таблица users не была создана."
        )

    columns = get_column_names("users")

    required_columns = {
        "id",
        "username",
        "email",
        "password_hash",
        "created_at",
    }

    missing_columns = (
        required_columns - columns
    )

    if missing_columns:
        raise RuntimeError(
            "В таблице users отсутствуют поля: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    print(
        "Проверка таблицы users успешна."
    )

    print(
        "Столбцы users:",
        ", ".join(
            sorted(columns)
        )
    )


def migrate() -> None:
    print(
        "Начинаем исправление базы данных..."
    )

    drop_old_users_table()

    create_users_table()

    add_user_id_to_library()

    add_user_id_to_history()

    add_library_foreign_key()

    add_history_foreign_key()

    verify_users_table()

    print()
    print(
        "Миграция авторизации завершена успешно."
    )


if __name__ == "__main__":
    migrate()