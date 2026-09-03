from datetime import UTC, datetime
from time import sleep

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.models.task import Task


def _is_transient_lock_error(error: OperationalError) -> bool:
    original = error.orig
    return getattr(original, "args", [None])[0] in {1205, 1213}


def claim_next_task(
    session: Session,
    worker_id: str,
    max_retries: int = 5,
    name_prefix: str | None = None,
) -> Task | None:
    for attempt in range(max_retries + 1):
        try:
            with session.begin():
                conditions = [Task.status == TaskStatus.PENDING]
                if name_prefix is not None:
                    conditions.append(Task.name.like(f"{name_prefix}%"))
                statement = (
                    select(Task)
                    .where(*conditions)
                    .order_by(Task.created_at, Task.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                task = session.scalar(statement)
                if task is None:
                    return None

                task.status = TaskStatus.CLAIMED
                task.worker_id = worker_id
                task.claimed_at = datetime.now(UTC).replace(tzinfo=None)
                session.flush()

            session.expunge(task)
            return task
        except OperationalError as error:
            session.rollback()
            if not _is_transient_lock_error(error) or attempt == max_retries:
                raise
            sleep(0.01 * (attempt + 1))
    return None
