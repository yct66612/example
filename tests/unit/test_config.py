import pytest

from app.config import Settings


def test_settings_accept_separate_runtime_and_test_databases() -> None:
    settings = Settings(
        database_url="mysql+pymysql://app:secret@localhost/scheduler",
        test_database_url="mysql+pymysql://app:secret@localhost/scheduler_test",
    )

    assert settings.database_url.endswith("/scheduler")
    assert settings.test_database_url.endswith("/scheduler_test")


def test_test_database_must_end_with_test() -> None:
    with pytest.raises(ValueError, match="_test"):
        Settings(
            database_url="mysql+pymysql://app:secret@localhost/scheduler",
            test_database_url="mysql+pymysql://app:secret@localhost/scheduler",
        )
