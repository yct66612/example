from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.models.task import Task


def claim_next_task(session: Session, worker_id: str) -> Task | None:
    with session.begin():
        statement = (
            select(Task)
            .where(Task.status == TaskStatus.PENDING)
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
