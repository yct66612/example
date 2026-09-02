from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import TaskCreate, TaskResponse, TaskStepResponse
from app.domain.enums import TaskStatus
from app.domain.parameters import resolve_step_parameters
from app.models.task import Task, TaskGroup, TaskStep

DEMO_GROUP_NAME = "演示客户组"
DEMO_TASK_NAME = "看板演示任务"


class TaskConflictError(Exception):
    """Raised when a task operation conflicts with persisted state."""


class TaskNotFoundError(Exception):
    """Raised when a requested task does not exist."""


def create_task(session: Session, payload: TaskCreate) -> Task:
    group = TaskGroup(name=payload.group_name, parameter_overrides=payload.group_overrides)
    task = _build_task(payload, group)

    try:
        with session.begin():
            session.add(task)
            session.flush()
    except IntegrityError as exc:
        raise TaskConflictError("任务组名称已经存在") from exc

    return task


def _build_task(payload: TaskCreate, group: TaskGroup) -> Task:
    task = Task(
        name=payload.name,
        group=group,
        base_parameters=payload.base_parameters,
    )
    task.steps = [
        TaskStep(
            step_index=index,
            name=step.name,
            parameter_overrides=step.overrides,
        )
        for index, step in enumerate(payload.steps)
    ]
    return task


def reset_demo_task(session: Session) -> Task:
    from app.api.schemas import StepCreate

    payload = TaskCreate(
        group_name=DEMO_GROUP_NAME,
        group_overrides={"channel": "email", "tone": ""},
        name=DEMO_TASK_NAME,
        base_parameters={"tone": "formal", "retry": 1},
        steps=[
            StepCreate(name="准备消息", overrides={"tone": "friendly"}),
            StepCreate(name="发送消息", overrides={"tone": "", "retry": 3}),
            StepCreate(name="安排跟进", overrides={"channel": "sms"}),
        ],
    )

    with session.begin():
        old_tasks = session.scalars(
            select(Task)
            .join(TaskGroup, Task.group_id == TaskGroup.id)
            .where(
                Task.name == DEMO_TASK_NAME,
                TaskGroup.name == DEMO_GROUP_NAME,
            )
            .with_for_update()
        ).all()
        for old_task in old_tasks:
            session.delete(old_task)
        session.flush()

        group = session.scalar(
            select(TaskGroup).where(TaskGroup.name == DEMO_GROUP_NAME).with_for_update()
        )
        if group is None:
            group = TaskGroup(
                name=payload.group_name,
                parameter_overrides=payload.group_overrides,
            )
            session.add(group)
            session.flush()
        else:
            group.parameter_overrides = payload.group_overrides

        task = _build_task(payload, group)
        session.add(task)
        session.flush()
    return task


def list_tasks(session: Session) -> Sequence[Task]:
    statement = (
        select(Task)
        .options(
            selectinload(Task.group),
            selectinload(Task.steps),
            selectinload(Task.execution_logs),
        )
        .order_by(Task.created_at, Task.id)
    )
    return session.scalars(statement).all()


def get_task(session: Session, task_id: int) -> Task:
    statement = (
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.group),
            selectinload(Task.steps),
            selectinload(Task.execution_logs),
        )
    )
    task = session.scalar(statement)
    if task is None:
        raise TaskNotFoundError("任务不存在")
    return task


def task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        group_name=task.group.name,
        current_step_index=task.current_step_index,
        worker_id=task.worker_id,
        steps=[
            TaskStepResponse(
                id=step.id,
                step_index=step.step_index,
                name=step.name,
                overrides=step.parameter_overrides,
            )
            for step in task.steps
        ],
        log_count=len(task.execution_logs),
    )


def task_parameters(task: Task) -> list[dict]:
    return resolve_step_parameters(
        task.base_parameters,
        task.group.parameter_overrides,
        [step.parameter_overrides for step in task.steps],
    )


def start_task(session: Session, task_id: int, worker_id: str) -> Task:
    with session.begin():
        task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if task is None:
            raise TaskNotFoundError("任务不存在")
        if task.status != TaskStatus.CLAIMED or task.worker_id != worker_id:
            raise TaskConflictError("只有认领任务的 worker 可以启动任务")
        task.status = TaskStatus.RUNNING
        session.flush()
    started_task = get_task(session, task_id)
    session.rollback()
    return started_task
