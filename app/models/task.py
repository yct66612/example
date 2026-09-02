from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import TaskStatus


class TaskGroup(Base):
    __tablename__ = "task_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    parameter_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="group")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_claim", "status", "created_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("task_groups.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        String(16),
        default=TaskStatus.PENDING,
        server_default=TaskStatus.PENDING.value,
        nullable=False,
    )
    base_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    current_step_index: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    group: Mapped[TaskGroup] = relationship(back_populates="tasks")
    steps: Mapped[list["TaskStep"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskStep.step_index"
    )
    execution_logs: Mapped[list["StepExecutionLog"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="StepExecutionLog.step_index"
    )


class TaskStep(Base):
    __tablename__ = "task_steps"
    __table_args__ = (UniqueConstraint("task_id", "step_index", name="uq_task_steps_task_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    parameter_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    task: Mapped[Task] = relationship(back_populates="steps")


class StepExecutionLog(Base):
    __tablename__ = "step_execution_logs"
    __table_args__ = (UniqueConstraint("task_id", "step_index", name="uq_step_logs_task_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    success: Mapped[bool] = mapped_column(nullable=False)

    task: Mapped[Task] = relationship(back_populates="execution_logs")
