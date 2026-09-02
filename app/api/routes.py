from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import ParameterResponse, TaskCreate, TaskResponse
from app.db.session import get_session
from app.models.task import Task
from app.services.tasks import (
    TaskConflictError,
    TaskNotFoundError,
    create_task,
    get_task,
    list_tasks,
    task_parameters,
    task_response,
)

router = APIRouter(prefix="/api")


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(
    payload: TaskCreate, session: Session = Depends(get_session)
) -> TaskResponse:
    try:
        return task_response(create_task(session, payload))
    except TaskConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks_endpoint(session: Session = Depends(get_session)) -> list[TaskResponse]:
    return [task_response(task) for task in list_tasks(session)]


@router.get("/tasks/{task_id}/parameters", response_model=ParameterResponse)
def task_parameters_endpoint(
    task_id: int, session: Session = Depends(get_session)
) -> ParameterResponse:
    try:
        task = get_task(session, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ParameterResponse(task_id=task.id, snapshots=task_parameters(task))


@router.post("/tasks/{task_id}/start", response_model=TaskResponse)
def start_task_endpoint(
    task_id: int,
    worker_id: str,
    session: Session = Depends(get_session),
) -> TaskResponse:
    from app.services.tasks import start_task

    try:
        return task_response(start_task(session, task_id, worker_id))
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TaskConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/demo/seed", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def seed_demo_endpoint(session: Session = Depends(get_session)) -> TaskResponse:
    from sqlalchemy import select

    from app.api.schemas import StepCreate

    existing = session.scalar(select(Task).where(Task.name == "看板演示任务"))
    if existing is not None:
        return task_response(get_task(session, existing.id))
    session.rollback()
    payload = TaskCreate(
        group_name="演示客户组",
        group_overrides={"channel": "email", "tone": ""},
        name="看板演示任务",
        base_parameters={"tone": "formal", "retry": 1},
        steps=[
            StepCreate(name="准备消息", overrides={"tone": "friendly"}),
            StepCreate(name="发送消息", overrides={"tone": "", "retry": 3}),
            StepCreate(name="安排跟进", overrides={"channel": "sms"}),
        ],
    )
    return task_response(create_task(session, payload))
