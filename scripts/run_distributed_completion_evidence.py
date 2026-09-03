"""使用多个真实进程和独立 MySQL 连接验证完成上报幂等性。"""

import argparse
import multiprocessing
import os
import uuid
from queue import Empty

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.session import build_engine
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


def _worker(database_url: str, task_id: int, worker_id: str, barrier, result_queue) -> None:
    engine = build_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            barrier.wait(timeout=30)
            result = complete_step(session, task_id, 0, True, worker_id)
            result_queue.put(
                {
                    "advanced": result.advanced,
                    "status": str(result.task_status),
                }
            )
    except BaseException as exc:
        result_queue.put({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        engine.dispose()


def _create_running_task(
    session: Session, run_number: int, worker_id: str
) -> tuple[int, str]:
    prefix = f"distributed-evidence-{os.getpid()}-{run_number}-{uuid.uuid4().hex[:8]}-"
    group = TaskGroup(name=f"{prefix}group", parameter_overrides={})
    task = Task(
        name=f"{prefix}task",
        group=group,
        base_parameters={},
        steps=[TaskStep(step_index=0, name="step", parameter_overrides={})],
    )
    session.add(task)
    session.commit()
    claimed = claim_next_task(session, worker_id, name_prefix=prefix)
    if claimed is None:
        raise RuntimeError("演示任务认领失败")
    start_task(session, claimed.id, worker_id)
    return claimed.id, prefix


def run_once(
    database_url: str, process_count: int, run_number: int, keep_data: bool
) -> tuple[int, int, str, int]:
    parent_engine = create_engine(database_url, pool_pre_ping=True)
    parent_factory = sessionmaker(bind=parent_engine, expire_on_commit=False)
    task_id = None
    try:
        worker_id = f"distributed-worker-{os.getpid()}-{run_number}"
        with parent_factory() as session:
            task_id, _ = _create_running_task(session, run_number, worker_id)

        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(process_count)
        result_queue = context.Queue()
        worker_id = f"distributed-worker-{os.getpid()}-{run_number}"
        processes = [
            context.Process(
                target=_worker,
                args=(database_url, task_id, worker_id, barrier, result_queue),
            )
            for _ in range(process_count)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=60)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                raise RuntimeError("分布式 worker 超时")
        if any(process.exitcode != 0 for process in processes):
            raise RuntimeError(f"分布式 worker 异常退出：{[p.exitcode for p in processes]}")

        results: list[dict] = []
        for _ in processes:
            try:
                results.append(result_queue.get(timeout=10))
            except Empty:
                break
        errors = [result["error"] for result in results if "error" in result]
        if errors:
            raise RuntimeError(f"分布式上报异常：{errors}")
        if len(results) != process_count:
            raise RuntimeError(f"收到 {len(results)} 条结果，预期 {process_count} 条")

        with parent_factory() as session:
            log_count = session.scalar(
                select(func.count())
                .select_from(StepExecutionLog)
                .where(
                    StepExecutionLog.task_id == task_id,
                    StepExecutionLog.step_index == 0,
                )
            )
            task = session.get(Task, task_id)
            if log_count != 1 or task is None:
                raise RuntimeError("日志数量或任务不存在校验失败")
            if task.current_step_index != 1 or task.status != TaskStatus.DONE:
                raise RuntimeError(
                    f"最终状态异常：status={task.status}, step={task.current_step_index}"
                )
            advanced_count = sum(bool(result["advanced"]) for result in results)
            return log_count, advanced_count, str(task.status), task_id
    finally:
        if task_id is not None and not keep_data:
            with parent_factory() as session:
                task = session.get(Task, task_id)
                if task is not None:
                    group = session.get(TaskGroup, task.group_id)
                    session.delete(task)
                    session.flush()
                    if group is not None:
                        session.delete(group)
                    session.commit()
        parent_engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="输出多进程分布式幂等证据")
    parser.add_argument("--processes", type=int, default=5)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--keep-data", action="store_true", help="保留证据任务和完成日志")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.processes < 2 or args.runs < 1:
        raise SystemExit("processes 必须至少为 2，runs 必须大于 0")

    database_url = _require_test_url()
    total_logs = total_advanced = 0
    final_status = "unknown"
    preserved_task_ids: list[int] = []
    for run_number in range(args.runs):
        log_count, advanced_count, final_status, task_id = run_once(
            database_url, args.processes, run_number, args.keep_data
        )
        total_logs += log_count
        total_advanced += advanced_count
        if args.keep_data:
            preserved_task_ids.append(task_id)

    print(f"真实进程数：{args.processes}，运行轮数：{args.runs}")
    print(f"重复上报总数：{args.processes * args.runs}")
    print(f"最终日志总数：{total_logs}")
    print(f"实际推进总数：{total_advanced}")
    print(f"最终任务状态：{final_status}")
    if args.keep_data:
        print(f"保留任务 ID：{', '.join(str(task_id) for task_id in preserved_task_ids)}")
        print("证据数据：已保留在 task_scheduler_test.tasks 和 step_execution_logs")
    if total_logs != args.runs or total_advanced != args.runs or final_status != "done":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
