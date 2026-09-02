from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.models.task import StepExecutionLog, Task, TaskStep
from app.services.tasks import TaskConflictError, TaskNotFoundError


@dataclass(frozen=True)
class CompletionResult:
    task_id: int
    step_index: int
    success: bool
    advanced: bool
    current_step_index: int
    task_status: TaskStatus


def complete_step(
    session: Session,
    task_id: int,
    step_index: int,
    success: bool,
    worker_id: str | None = None,
) -> CompletionResult:
    with session.begin():
        task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if task is None:
            raise TaskNotFoundError("任务不存在")
        if worker_id is not None and task.worker_id != worker_id:
            raise TaskConflictError("只有认领任务的 worker 可以上报完成")

        step = session.scalar(
            select(TaskStep).where(
                TaskStep.task_id == task_id,
                TaskStep.step_index == step_index,
            )
        )
        if step is None:
            raise TaskNotFoundError("步骤不存在")
        if step_index > task.current_step_index:
            raise TaskConflictError("不能提前上报尚未执行的步骤")
        if task.status in {TaskStatus.PENDING, TaskStatus.CLAIMED}:
            raise TaskConflictError("任务尚未启动，不能上报当前步骤")

        insert_statement = insert(StepExecutionLog).values(
            task_id=task_id,
            step_index=step_index,
            success=success,
        )
        insert_statement = insert_statement.on_duplicate_key_update(
            success=or_(StepExecutionLog.success, insert_statement.inserted.success)
        )
        session.execute(insert_statement)

        advanced = False
        if task.status == TaskStatus.RUNNING and task.current_step_index == step_index:
            advanced = True
            if success:
                task.current_step_index += 1
                step_count = session.scalar(
                    select(func.count()).select_from(TaskStep).where(TaskStep.task_id == task_id)
                )
                if task.current_step_index >= (step_count or 0):
                    task.status = TaskStatus.DONE
            else:
                task.status = TaskStatus.FAILED
        session.flush()
        result = CompletionResult(
            task_id=task.id,
            step_index=step_index,
            success=success,
            advanced=advanced,
            current_step_index=task.current_step_index,
            task_status=task.status,
        )
    return result
