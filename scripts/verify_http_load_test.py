"""Verify JMeter HTTP concurrency results against MySQL state."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db.session import build_engine
from app.domain.enums import TaskStatus
from app.models.task import StepExecutionLog, Task, TaskGroup


def require_test_database_url(database_url: str) -> str:
    database_name = make_url(database_url).database or ""
    if not database_name.endswith("_test"):
        raise ValueError("load tests require a database name ending with _test")
    return database_url


def configured_load_test_database_url(env_file: Path | None = None) -> str:
    settings = Settings(_env_file=env_file) if env_file is not None else get_settings()
    return require_test_database_url(
        settings.load_test_database_url or settings.test_database_url
    )


def read_result_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_claim_results(expected_ids: set[int], rows: list[dict[str, str]]) -> dict:
    successful_rows = [row for row in rows if row.get("status") == "200"]
    returned_ids = [int(row["task_id"]) for row in successful_rows if row.get("task_id")]
    returned_set = set(returned_ids)
    instances = Counter(row.get("instance") or "unknown" for row in successful_rows)
    return {
        "total_responses": len(rows),
        "successful_responses": len(successful_rows),
        "error_responses": len(rows) - len(successful_rows),
        "duplicate_count": len(returned_ids) - len(returned_set),
        "missing_ids": sorted(expected_ids - returned_set),
        "unexpected_ids": sorted(returned_set - expected_ids),
        "instances": dict(sorted(instances.items())),
    }


def has_expected_instances(instances: dict[str, int], expected_instances: int) -> bool:
    observed = [
        name for name, count in instances.items() if name != "unknown" and count > 0
    ]
    return len(observed) >= expected_instances


def verify_load_test(
    database_url: str,
    context: dict,
    claim_rows: list[dict[str, str]],
    completion_rows: list[dict[str, str]],
    expected_instances: int = 3,
) -> dict:
    require_test_database_url(database_url)
    expected_ids = set(context["claim_task_ids"])
    claim_summary = summarize_claim_results(expected_ids, claim_rows)
    completion_successes = [row for row in completion_rows if row.get("status") == "200"]
    completion_instances = Counter(
        row.get("instance") or "unknown" for row in completion_successes
    )

    engine = build_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            claimed_count = session.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.id.in_(expected_ids), Task.status == TaskStatus.CLAIMED)
            )
            completion_task = session.get(Task, context["completion_task_id"])
            completion_log_count = session.scalar(
                select(func.count())
                .select_from(StepExecutionLog)
                .where(
                    StepExecutionLog.task_id == context["completion_task_id"],
                    StepExecutionLog.step_index == 0,
                )
            )
    finally:
        engine.dispose()

    summary = {
        "claim": claim_summary,
        "database_claimed_count": claimed_count or 0,
        "completion": {
            "total_responses": len(completion_rows),
            "successful_responses": len(completion_successes),
            "error_responses": len(completion_rows) - len(completion_successes),
            "instances": dict(sorted(completion_instances.items())),
            "log_count": completion_log_count or 0,
            "current_step_index": (
                completion_task.current_step_index if completion_task is not None else None
            ),
            "status": str(completion_task.status) if completion_task is not None else "missing",
        },
        "expected_instances": expected_instances,
    }
    valid = (
        claim_summary["successful_responses"] == context["claim_count"]
        and claim_summary["error_responses"] == 0
        and claim_summary["duplicate_count"] == 0
        and not claim_summary["missing_ids"]
        and not claim_summary["unexpected_ids"]
        and has_expected_instances(claim_summary["instances"], expected_instances)
        and (claimed_count or 0) == context["claim_count"]
        and len(completion_rows) >= 2
        and len(completion_successes) == len(completion_rows)
        and has_expected_instances(dict(completion_instances), expected_instances)
        and (completion_log_count or 0) == 1
        and completion_task is not None
        and completion_task.current_step_index == 1
        and completion_task.status == TaskStatus.DONE
    )
    summary["valid"] = valid
    return summary


def cleanup_load_test(database_url: str, context: dict) -> None:
    engine = build_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session, session.begin():
            session.execute(delete(Task).where(Task.id.in_(context["claim_task_ids"])))
            completion_task = session.get(Task, context["completion_task_id"])
            if completion_task is not None:
                session.delete(completion_task)
            session.flush()
            for group_id in (context["claim_group_id"], context["completion_group_id"]):
                group = session.get(TaskGroup, group_id)
                if group is not None:
                    session.delete(group)
    finally:
        engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 HTTP 分布式压测结果")
    parser.add_argument("--context", type=Path, default=Path("load-test-results/context.json"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--expected-instances", type=int, default=3)
    parser.add_argument("--cleanup", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    context = json.loads(args.context.read_text(encoding="utf-8"))
    claim_rows = read_result_rows(Path(context["claim_results_file"]))
    completion_rows = read_result_rows(Path(context["completion_results_file"]))
    database_url = configured_load_test_database_url(args.env_file)
    if args.expected_instances < 1:
        raise SystemExit("expected-instances 必须大于 0")
    summary = verify_load_test(
        database_url,
        context,
        claim_rows,
        completion_rows,
        expected_instances=args.expected_instances,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["valid"]:
        raise SystemExit(1)
    if args.cleanup:
        cleanup_load_test(database_url, context)
        print("本批压测数据已清理")


if __name__ == "__main__":
    main()
