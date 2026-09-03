"""Apply the current Alembic revision to runtime and test databases."""

from alembic.config import Config

from alembic import command
from app.config import get_settings


def migrate_database(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def main() -> None:
    settings = get_settings()
    urls = list(dict.fromkeys([settings.database_url, settings.test_database_url]))
    for database_url in urls:
        migrate_database(database_url)
    print(f"已迁移数据库数量：{len(urls)}")


if __name__ == "__main__":
    main()
