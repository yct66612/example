from io import StringIO

from alembic.config import Config

from alembic import command


def test_alembic_respects_explicit_database_url() -> None:
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        "mysql+pymysql://app:secret@localhost/task_scheduler_test",
    )
    output = StringIO()
    config.output_buffer = output

    command.upgrade(config, "head", sql=True)

    assert "CREATE TABLE task_groups" in output.getvalue()
