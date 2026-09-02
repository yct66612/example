"""运行真实多进程任务认领证据。"""

import argparse
import multiprocessing
import os
from queue import Empty

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.enums import TaskStatus
from app.models.task import Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task


def _require_test_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        raise SystemExit("请先设置 TEST_DATABASE_URL")
    database_name = url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
    if not database_name.endswith("_test"):
        raise SystemExit("为避免误删数据，TEST_DATABASE_URL 的数据库名必须以 _test 结尾")
    return url


def _worker(database_url: str, worker_id: str, result_queue) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            while True:
                task = claim_next_task(session, worker_id)
                if task is None:
                    return
                result_queue.put(task.id)
    finally:
        engine.dispose()


def _prepare_tasks(session: Session, count: int, prefix: str) -> set[int]:
    old_tasks = session.scalars(select(Task).where(Task.name.like(f"{prefix}%"))).all()
    for old_task in old_tasks:
        session.delete(old_task)
    session.flush()
    old_group = session.scalar(select(TaskGroup).where(TaskGroup.name == f"{prefix}group"))
    if old_group is not None:
        session.delete(old_group)
        session.flush()

    group = TaskGroup(name=f"{prefix}group", parameter_overrides={})
    tasks = [
        Task(
            name=f"{prefix}{index}",
            group=group,
            base_parameters={},
            steps=[TaskStep(step_index=0, name="step", parameter_overrides={})],
        )
        for index in range(count)
    ]
    session.add_all(tasks)
    session.commit()
    return {task.id for task in tasks}


def run_once(database_url: str, count: int, workers: int, run_number: int) -> tuple[int, int, int]:
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    prefix = f"evidence-{os.getpid()}-{run_number}-"
    with factory() as session:
        expected_ids = _prepare_tasks(session, count, prefix)

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    processes = [
        context.Process(target=_worker, args=(database_url, f"evidence-worker-{i}", result_queue))
        for i in range(workers)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=60)
    exit_codes = [process.exitcode for process in processes]
    if any(code != 0 for code in exit_codes):
        raise RuntimeError(f"worker 进程异常退出：{exit_codes}")

    claimed_ids: list[int] = []
    while len(claimed_ids) < count:
        try:
            claimed_ids.append(result_queue.get(timeout=5))
        except Empty:
            break
    duplicate_count = len(claimed_ids) - len(set(claimed_ids))
    missing_count = len(expected_ids - set(claimed_ids))
    with factory() as session:
        claimed_count = session.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.name.like(f"{prefix}%"), Task.status == TaskStatus.CLAIMED)
        )
        session.execute(delete(Task).where(Task.name.like(f"{prefix}%")))
        session.commit()
    engine.dispose()
    if claimed_count != count:
        missing_count += count - (claimed_count or 0)
    return len(claimed_ids), duplicate_count, missing_count


def main() -> None:
    parser = argparse.ArgumentParser(description="输出多进程唯一认领证据")
    parser.add_argument("--tasks", type=int, default=100)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    if min(args.tasks, args.workers, args.runs) < 1:
        raise SystemExit("tasks、workers、runs 都必须大于 0")

    database_url = _require_test_url()
    total_claims = total_duplicates = total_missing = 0
    for run_number in range(args.runs):
        claimed, duplicates, missing = run_once(
            database_url, args.tasks, args.workers, run_number
        )
        total_claims += claimed
        total_duplicates += duplicates
        total_missing += missing
    print(f"任务数：{args.tasks}，Worker 数：{args.workers}，运行轮数：{args.runs}")
    print(f"总认领数：{total_claims}")
    print(f"重复认领数：{total_duplicates}")
    print(f"遗漏任务数：{total_missing}")
    if total_duplicates or total_missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
