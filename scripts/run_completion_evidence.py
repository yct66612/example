"""运行五次重复完成上报证据。"""

import argparse
import concurrent.futures
import os

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models.task import StepExecutionLog, Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task
from app.services.completion import complete_step
from app.services.tasks import start_task


def _require_test_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        raise SystemExit("请先设置 TEST_DATABASE_URL")
    database_name = url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
    if not database_name.endswith("_test"):
        raise SystemExit("为避免误删数据，TEST_DATABASE_URL 的数据库名必须以 _test 结尾")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="输出重复完成上报幂等证据")
    parser.add_argument("--reports", type=int, default=5)
    args = parser.parse_args()
    if args.reports < 2:
        raise SystemExit("reports 必须至少为 2")

    database_url = _require_test_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        group = TaskGroup(name=f"completion-evidence-{os.getpid()}", parameter_overrides={})
        task = Task(
            name=f"completion-evidence-{os.getpid()}",
            group=group,
            base_parameters={},
            steps=[TaskStep(step_index=0, name="step", parameter_overrides={})],
        )
        session.add(task)
        session.commit()
        claimed = claim_next_task(session, "completion-evidence-worker")
        assert claimed is not None
        start_task(session, claimed.id, claimed.worker_id or "")
        task_id = claimed.id

    def report() -> None:
        with factory() as session:
            complete_step(session, task_id, 0, True, "completion-evidence-worker")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.reports) as executor:
        list(executor.map(lambda _: report(), range(args.reports)))

    with factory() as session:
        log_count = session.scalar(
            select(func.count())
            .select_from(StepExecutionLog)
            .where(StepExecutionLog.task_id == task_id, StepExecutionLog.step_index == 0)
        )
        task = session.get(Task, task_id)
        print(f"完成上报次数：{args.reports}")
        print(f"最终日志行数：{log_count}")
        print(f"最终任务状态：{task.status if task else 'missing'}")
        if log_count != 1 or task is None or task.current_step_index != 1:
            raise SystemExit(1)
        session.delete(task)
        session.commit()
    engine.dispose()


if __name__ == "__main__":
    main()
