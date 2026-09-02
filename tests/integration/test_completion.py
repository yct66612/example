import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.enums import TaskStatus
from app.models.task import StepExecutionLog, Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task
from app.services.completion import complete_step
from app.services.tasks import TaskConflictError, TaskNotFoundError, start_task

pytestmark = pytest.mark.integration


def _seed_claimed_task(session: Session, step_count: int = 2) -> tuple[int, str]:
    group = TaskGroup(name="completion-group", parameter_overrides={})
    task = Task(
        name="completion-task",
        group=group,
        base_parameters={},
        steps=[
            TaskStep(step_index=index, name=f"step-{index}", parameter_overrides={})
            for index in range(step_count)
        ],
    )
    session.add(task)
    session.commit()
    claimed = claim_next_task(session, "worker-a")
    assert claimed is not None
    return claimed.id, "worker-a"


def test_only_claiming_worker_can_start_task(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session)

    with pytest.raises(TaskConflictError):
        start_task(db_session, task_id, "worker-b")

    started = start_task(db_session, task_id, worker_id)

    assert started.status == TaskStatus.RUNNING


def test_claimed_task_cannot_report_current_step_before_start(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=1)

    with pytest.raises(TaskConflictError):
        complete_step(db_session, task_id, 0, True, worker_id)

    log_count = db_session.scalar(
        select(func.count())
        .select_from(StepExecutionLog)
        .where(StepExecutionLog.task_id == task_id)
    )
    task = db_session.get(Task, task_id)

    assert log_count == 0
    assert task is not None and task.status == TaskStatus.CLAIMED


def test_completion_rejects_future_or_missing_step(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=2)
    start_task(db_session, task_id, worker_id)

    with pytest.raises(TaskConflictError):
        complete_step(db_session, task_id, 1, True, worker_id)

    with pytest.raises(TaskNotFoundError):
        complete_step(db_session, task_id, 99, True, worker_id)


def test_starting_a_running_task_again_is_rejected(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=1)
    start_task(db_session, task_id, worker_id)

    with pytest.raises(TaskConflictError):
        start_task(db_session, task_id, worker_id)


def test_completion_log_is_idempotent_and_success_is_monotonic(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=1)
    start_task(db_session, task_id, worker_id)

    complete_step(db_session, task_id, 0, True, worker_id)
    complete_step(db_session, task_id, 0, False, worker_id)
    complete_step(db_session, task_id, 0, True, worker_id)

    log_count = db_session.scalar(
        select(func.count())
        .select_from(StepExecutionLog)
        .where(StepExecutionLog.task_id == task_id)
    )
    log = db_session.scalar(
        select(StepExecutionLog).where(
            StepExecutionLog.task_id == task_id,
            StepExecutionLog.step_index == 0,
        )
    )
    task = db_session.get(Task, task_id)

    assert log_count == 1
    assert log is not None and log.success is True
    assert task is not None and task.status == TaskStatus.DONE


def test_failure_then_success_upgrades_only_the_log(db_session: Session) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=1)
    start_task(db_session, task_id, worker_id)

    complete_step(db_session, task_id, 0, False, worker_id)
    complete_step(db_session, task_id, 0, True, worker_id)

    log = db_session.scalar(
        select(StepExecutionLog).where(
            StepExecutionLog.task_id == task_id,
            StepExecutionLog.step_index == 0,
        )
    )
    task = db_session.get(Task, task_id)

    assert log is not None and log.success is True
    assert task is not None and task.status == TaskStatus.FAILED


def test_five_independent_connections_advance_one_step_once(
    db_session: Session, mysql_engine
) -> None:
    task_id, worker_id = _seed_claimed_task(db_session, step_count=2)
    start_task(db_session, task_id, worker_id)
    factory = sessionmaker(bind=mysql_engine, expire_on_commit=False)
    barrier = threading.Barrier(5)
    errors: list[BaseException] = []

    def report() -> None:
        try:
            with factory() as session:
                barrier.wait(timeout=10)
                complete_step(session, task_id, 0, True, worker_id)
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    threads = [threading.Thread(target=report) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors
    with factory() as check_session:
        log_count = check_session.scalar(
            select(func.count())
            .select_from(StepExecutionLog)
            .where(
                StepExecutionLog.task_id == task_id,
                StepExecutionLog.step_index == 0,
            )
        )
        task = check_session.get(Task, task_id)

    assert log_count == 1
    assert task is not None
    assert task.current_step_index == 1
    assert task.status == TaskStatus.RUNNING
