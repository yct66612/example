import multiprocessing
import os
from queue import Empty

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.enums import TaskStatus
from app.models.task import Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task

pytestmark = pytest.mark.integration


def _seed_tasks(session: Session, count: int) -> list[int]:
    group = TaskGroup(name="claim-group", parameter_overrides={})
    tasks = [
        Task(
            name=f"claim-task-{index}",
            group=group,
            base_parameters={},
            steps=[TaskStep(step_index=0, name="step", parameter_overrides={})],
        )
        for index in range(count)
    ]
    session.add_all(tasks)
    session.commit()
    return [task.id for task in tasks]


def _claim_worker(database_url: str, worker_id: str, result_queue) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            while True:
                task = claim_next_task(session, worker_id)
                if task is None:
                    break
                result_queue.put(task.id)
    finally:
        engine.dispose()


def test_claims_oldest_pending_task_once(db_session: Session) -> None:
    task_ids = _seed_tasks(db_session, 2)

    claimed = claim_next_task(db_session, "worker-a")
    second = claim_next_task(db_session, "worker-a")
    third = claim_next_task(db_session, "worker-a")

    assert claimed is not None
    assert claimed.id == task_ids[0]
    assert second is not None
    assert second.id == task_ids[1]
    assert third is None

    statuses = db_session.scalars(select(Task.status).order_by(Task.id)).all()
    assert statuses == [TaskStatus.CLAIMED, TaskStatus.CLAIMED]


def test_ten_real_processes_claim_each_task_exactly_once(db_session: Session) -> None:
    task_ids = set(_seed_tasks(db_session, 100))
    database_url = os.environ["TEST_DATABASE_URL"]
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(target=_claim_worker, args=(database_url, f"worker-{index}", result_queue))
        for index in range(10)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    claimed_ids: list[int] = []
    while len(claimed_ids) < 100:
        try:
            claimed_ids.append(result_queue.get(timeout=5))
        except Empty:
            break

    assert len(claimed_ids) == 100
    assert len(set(claimed_ids)) == 100
    assert set(claimed_ids) == task_ids
