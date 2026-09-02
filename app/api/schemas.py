from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import TaskStatus


class StepCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    overrides: dict[str, Any] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=100)
    group_overrides: dict[str, Any] = Field(default_factory=dict)
    name: str = Field(min_length=1, max_length=150)
    base_parameters: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepCreate] = Field(min_length=1)


class TaskStepResponse(BaseModel):
    id: int
    step_index: int
    name: str
    overrides: dict[str, Any]


class TaskResponse(BaseModel):
    id: int
    name: str
    status: TaskStatus
    group_name: str
    current_step_index: int
    worker_id: str | None
    steps: list[TaskStepResponse]
    log_count: int


class TaskListResponse(TaskResponse):
    pass


class ClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)


class ParameterResponse(BaseModel):
    task_id: int
    snapshots: list[dict[str, Any]]


class StepCompleteRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)
    success: bool
