import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("未配置 TEST_DATABASE_URL，跳过 MySQL 集成测试")
    database_name = url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
    if not database_name.endswith("_test"):
        pytest.fail("集成测试数据库名称必须以 _test 结尾")
    return url


@pytest.fixture(scope="session")
def mysql_engine() -> Generator[Engine, None, None]:
    url = _test_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(mysql_engine: Engine) -> Generator[None, None, None]:
    with mysql_engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in ("step_execution_logs", "task_steps", "tasks", "task_groups"):
            connection.execute(text(f"TRUNCATE TABLE {table}"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    yield


@pytest.fixture
def db_session(mysql_engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=mysql_engine, expire_on_commit=False)
    with factory() as session:
        yield session
