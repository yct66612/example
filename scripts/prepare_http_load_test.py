"""Prepare isolated tasks and JMeter properties for HTTP concurrency tests."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db.session import build_engine
from app.models.task import Task, TaskGroup, TaskStep
from app.services.claiming import claim_next_task
from app.services.tasks import start_task

RESULT_HEADER = "status,task_id,worker_id,instance,request_id\n"


def require_test_database_url(database_url: str) -> str:
    database_name = make_url(database_url).database or ""
    if not database_name.endswith("_test"):
        raise ValueError("load tests require a database name ending with _test")
    return database_url


def prepare_load_test(database_url: str, claim_count: int, output_dir: Path) -> dict:
    require_test_database_url(database_url)
    if claim_count < 1:
        raise ValueError("claim_count must be greater than zero")

    batch_id = uuid4().hex[:10]
    claim_prefix = f"http-claim-{batch_id}-"
    completion_prefix = f"http-completion-{batch_id}-"
    completion_worker_id = f"http-worker-{batch_id}"
    engine = build_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        with factory() as session:
            claim_group = TaskGroup(
                name=f"{claim_prefix}group",
                parameter_overrides={},
            )
            claim_tasks = [
                Task(
                    name=f"{claim_prefix}{index}",
                    group=claim_group,
                    base_parameters={},
                    steps=[TaskStep(step_index=0, name="claim-step", parameter_overrides={})],
                )
                for index in range(claim_count)
            ]
            completion_group = TaskGroup(
                name=f"{completion_prefix}group",
                parameter_overrides={},
            )
            completion_task = Task(
                name=f"{completion_prefix}task",
                group=completion_group,
                base_parameters={},
                steps=[
                    TaskStep(step_index=0, name="completion-step", parameter_overrides={})
                ],
            )
            session.add_all([*claim_tasks, completion_task])
            session.commit()
            claim_task_ids = [task.id for task in claim_tasks]

            claimed = claim_next_task(
                session,
                completion_worker_id,
                name_prefix=completion_prefix,
            )
            if claimed is None:
                raise RuntimeError("failed to claim the completion load-test task")
            start_task(session, claimed.id, completion_worker_id)
            completion_task_id = claimed.id
            claim_group_id = claim_group.id
            completion_group_id = completion_group.id
    finally:
        engine.dispose()

    output_dir.mkdir(parents=True, exist_ok=True)
    claim_results = output_dir / "claim-results.csv"
    completion_results = output_dir / "completion-results.csv"
    claim_results.write_text(RESULT_HEADER, encoding="utf-8")
    completion_results.write_text(RESULT_HEADER, encoding="utf-8")

    context = {
        "batch_id": batch_id,
        "created_at": datetime.now(UTC).isoformat(),
        "claim_prefix": claim_prefix,
        "claim_count": claim_count,
        "claim_task_ids": claim_task_ids,
        "claim_group_id": claim_group_id,
        "completion_prefix": completion_prefix,
        "completion_task_id": completion_task_id,
        "completion_group_id": completion_group_id,
        "completion_worker_id": completion_worker_id,
        "claim_results_file": claim_results.resolve().as_posix(),
        "completion_results_file": completion_results.resolve().as_posix(),
    }
    context_path = output_dir / "context.json"
    context_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    properties = output_dir / "jmeter.properties"
    properties.write_text(
        "\n".join(
            [
                f"claimPrefix={claim_prefix}",
                f"claimCount={claim_count}",
                f"taskId={completion_task_id}",
                f"workerId={completion_worker_id}",
                f"claimResultsFile={context['claim_results_file']}",
                f"completionResultsFile={context['completion_results_file']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="准备隔离的 HTTP 分布式压测数据")
    parser.add_argument("--claim-tasks", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("load-test-results"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        database_url = require_test_database_url(get_settings().test_database_url)
        context = prepare_load_test(database_url, args.claim_tasks, args.output_dir)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"压测批次：{context['batch_id']}")
    print(f"认领任务数：{context['claim_count']}")
    print(f"认领任务前缀：{context['claim_prefix']}")
    print(f"幂等任务 ID：{context['completion_task_id']}")
    print(f"幂等 Worker：{context['completion_worker_id']}")
    print(f"JMeter 属性：{args.output_dir / 'jmeter.properties'}")


if __name__ == "__main__":
    main()
