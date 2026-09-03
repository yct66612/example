"""运行五次重复完成上报证据。"""

import argparse
import concurrent.futures
import os
import uuid

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.domain.enums import TaskStatus
from app.models.task import StepExecutionLog, Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task
from app.services.completion import complete_step
from app.services.tasks import start_task


def _require_test_url() -> str:
    try:
        url = get_settings().test_database_url
    except Exception as exc:
        raise SystemExit(f"请先配置 TEST_DATABASE_URL：{exc}") from exc
    database_name = url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
    if not database_name.endswith("_test"):
        raise SystemExit("为避免误删数据，TEST_DATABASE_URL 的数据库名必须以 _test 结尾")
    return url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="输出重复完成上报幂等证据")
    parser.add_argument("--reports", type=int, default=5)
    parser.add_argument("--keep-data", action="store_true", help="保留证据任务和完成日志")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.reports < 2:
        raise SystemExit("reports 必须至少为 2")

    database_url = _require_test_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    prefix = f"completion-evidence-{os.getpid()}-{uuid.uuid4().hex[:8]}-"
    with factory() as session:
        group = TaskGroup(name=f"{prefix}group", parameter_overrides={})
        task = Task(
            name=f"{prefix}task",
            group=group,
            base_parameters={},
            steps=[TaskStep(step_index=0, name="step", parameter_overrides={})],
        )
        session.add(task)
        session.commit()
        claimed = claim_next_task(
            session, "completion-evidence-worker", name_prefix=prefix
        )
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
        print(f"证据任务 ID：{task_id}")
        if (
            log_count != 1
            or task is None
            or task.current_step_index != 1
            or task.status != TaskStatus.DONE
        ):
            raise SystemExit(1)
        if not args.keep_data:
            group = session.get(TaskGroup, task.group_id)
            session.delete(task)
            session.flush()
            if group is not None:
                session.delete(group)
            session.commit()
        else:
            print("证据数据：已保留在 task_scheduler_test.tasks 和 step_execution_logs")
    engine.dispose()


if __name__ == "__main__":
    main()
