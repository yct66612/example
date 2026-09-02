import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.task import StepExecutionLog, Task, TaskGroup, TaskStep

pytestmark = pytest.mark.integration


def test_scheduler_tables_have_required_constraints_and_indexes(mysql_engine) -> None:
    inspector = inspect(mysql_engine)
    table_names = set(inspector.get_table_names())

    assert {"task_groups", "tasks", "task_steps", "step_execution_logs"} <= table_names

    step_constraints = inspector.get_unique_constraints("task_steps")
    log_constraints = inspector.get_unique_constraints("step_execution_logs")
    task_indexes = inspector.get_indexes("tasks")

    assert any(c["column_names"] == ["task_id", "step_index"] for c in step_constraints)
    assert any(c["column_names"] == ["task_id", "step_index"] for c in log_constraints)
    assert any(i["column_names"] == ["status", "created_at", "id"] for i in task_indexes)


def test_duplicate_step_and_log_are_rejected(db_session) -> None:
    group = TaskGroup(name="schema-group", parameter_overrides={})
    task = Task(
        name="schema-task",
        group=group,
        base_parameters={},
    )
    task.steps.append(TaskStep(step_index=0, name="first", parameter_overrides={}))
    db_session.add(task)
    db_session.commit()

    db_session.add(
        TaskStep(task_id=task.id, step_index=0, name="duplicate", parameter_overrides={})
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        StepExecutionLog(task_id=task.id, step_index=0, success=True),
    )
    db_session.flush()
    db_session.add(
        StepExecutionLog(task_id=task.id, step_index=0, success=False),
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_models_are_registered_on_metadata() -> None:
    assert {"task_groups", "tasks", "task_steps", "step_execution_logs"} <= set(
        Base.metadata.tables
    )
