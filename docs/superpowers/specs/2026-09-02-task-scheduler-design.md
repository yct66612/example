# Task Scheduler Dashboard Design

## Goal

Build a small FastAPI and MySQL task scheduler that demonstrates sticky parameter resolution, exclusive multi-worker task claiming, idempotent step completion logs, and a minimal live status dashboard.

## Scope

The delivery includes task groups, tasks, ordered steps, sticky parameter resolution, exclusive claims, state transitions, idempotent step completion, a polling dashboard, a five-request completion demo, and repeatable unit/integration evidence. It excludes authentication, external queues, distributed locks, worker leases, abandoned-claim recovery, deployment infrastructure, and production observability; these limitations will be documented.

## Technology and Boundaries

- Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, PyMySQL, pytest.
- MySQL 8 with InnoDB.
- Vanilla HTML/CSS/JavaScript served by FastAPI.
- Routine persistence uses SQLAlchemy ORM.
- Locking reads use SQLAlchemy `with_for_update(skip_locked=True)`.
- MySQL upserts use the SQLAlchemy MySQL dialect, not hand-built SQL strings.
- The API owns request-scoped sessions; service functions own explicit transaction blocks.

## Data Model

`task_groups` stores a unique name and JSON group overrides. `tasks` stores a group reference, name, status (`pending`, `claimed`, `running`, `done`, `failed`), base JSON parameters, current step index, worker identity, and claim timestamps. `task_steps` stores ordered steps and JSON overrides with unique `(task_id, step_index)`. `step_execution_logs` stores completion time and success with unique `(task_id, step_index)`.

The claim query is supported by index `(status, created_at, id)`.

## Parameter Resolution

Start with a copy of task base parameters, apply group overrides literally, then process steps in order. A non-empty step override replaces or introduces a value and remains sticky for later steps. A step override value of `""` does nothing and preserves the currently effective value; if no value exists yet, the key stays absent. The resolver returns independent snapshots and never mutates stored JSON.

Tests cover base values, group replacement, literal group empty strings, sticky step overrides, later replacement, empty-string fallback, new keys, and input immutability.

## Claiming and State

Claiming is one transaction on one connection:

1. Select the oldest pending task with `FOR UPDATE SKIP LOCKED`.
2. Update it to `claimed`, recording worker ID and time.
3. Commit before returning.

Allowed transitions are `pending -> claimed -> running -> done|failed`. Successful completion advances the current step and marks the final step done. A conditional update matching expected status and current step prevents duplicate reports from advancing twice.

## Idempotent Completion

Completion uses the log unique constraint and a MySQL atomic upsert. Success is monotonic: a later failure cannot downgrade an existing success, while a later success may upgrade an earlier failure. Five concurrent success reports therefore leave one log row and one state transition.

## API and Dashboard

- `POST /api/tasks`: create a group, task, and ordered steps.
- `GET /api/tasks`: list task states and log summaries.
- `POST /api/tasks/claim`: claim the next task for a worker ID.
- `POST /api/tasks/{task_id}/start`: start a claimed task.
- `POST /api/tasks/{task_id}/steps/{step_index}/complete`: report completion.
- `GET /api/tasks/{task_id}/parameters`: show resolved snapshots.
- `POST /api/demo/seed`: create deterministic sample data.

The root page is the operational dashboard. It polls task state once per second and provides seed, claim, start, parameter, and `Complete x5` controls.

## Testing and Evidence

Unit tests run without MySQL. Integration tests use a dedicated database whose name ends in `_test`; they cover schema constraints, transitions, real multi-process claims, concurrent duplicate completion, monotonic success, rollback, and API responses. Each worker process creates its own engine and MySQL connection. The parent verifies every task was claimed exactly once and prints duplicate/missing counts.

## Configuration and Git

Database credentials come from `.env`; only `.env.example` is tracked. The supplied API-key file is ignored because this full-stack solution does not need it. Milestone commits will cover repository safety, schema, parameter resolution, claiming, idempotent logging, API/dashboard, and evidence documentation. `COLLAB.md` records substantive ownership and collaboration decisions for both teammates.

## Acceptance Criteria

- A clean checkout starts from the README.
- Unit and MySQL integration tests pass.
- Parameter edge cases are demonstrated.
- Multi-process evidence reports zero duplicate claims.
- Five completion reports leave exactly one log row.
- A successful log cannot be overwritten by a later failure.
- The dashboard exposes all required task states and the five-report demo.
- No secret file is tracked by Git.
