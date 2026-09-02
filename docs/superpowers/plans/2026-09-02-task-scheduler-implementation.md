# Task Scheduler Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI and MySQL task scheduler with sticky parameters, exclusive multi-process claiming, idempotent completion logs, and a minimal polling dashboard.

**Architecture:** FastAPI owns HTTP and static delivery, focused service modules own transaction boundaries, SQLAlchemy 2.x maps MySQL InnoDB tables, and pure domain functions handle parameter resolution. Unit tests isolate deterministic rules; integration tests use independent engines, connections, threads, and processes against a dedicated `_test` database.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, PyMySQL, Pydantic Settings, pytest, pytest-xdist-compatible integration tests, vanilla HTML/CSS/JavaScript.

---

## File Map

- `pyproject.toml`: dependencies, pytest, Ruff, and packaging configuration.
- `.env.example`: non-secret runtime and test database configuration.
- `app/config.py`: validated environment settings.
- `app/db/base.py`: SQLAlchemy declarative base.
- `app/db/session.py`: engine and session factories.
- `app/models/task.py`: group, task, step, and execution-log models.
- `app/domain/enums.py`: task status values.
- `app/domain/parameters.py`: pure sticky parameter resolver.
- `app/services/tasks.py`: task creation, listing, and start transitions.
- `app/services/claiming.py`: exclusive claim transaction.
- `app/services/completion.py`: idempotent completion transaction.
- `app/api/schemas.py`: HTTP request and response models.
- `app/api/routes.py`: API endpoints and error mapping.
- `app/main.py`: application assembly and static routes.
- `app/static/index.html`: operational dashboard markup.
- `app/static/styles.css`: restrained dashboard presentation.
- `app/static/app.js`: polling and demo actions.
- `alembic.ini`, `alembic/env.py`, `alembic/versions/*`: schema migration.
- `tests/unit/*`: pure behavior tests.
- `tests/integration/*`: real MySQL and API tests.
- `scripts/create_databases.sql`: database/user setup example.
- `scripts/run_claim_evidence.py`: repeatable multi-process claim evidence.
- `scripts/run_completion_evidence.py`: repeatable duplicate-report evidence.
- `README.md`: one-page submission guide and architecture summary.
- `COLLAB.md`: ownership and collaboration record.

### Task 1: Project Foundation and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/db/__init__.py`
- Create: `app/db/base.py`
- Create: `app/db/session.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Add project metadata and environment example**

Use Python `>=3.11`, runtime dependencies `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `alembic`, `pymysql`, `pydantic-settings`, and dev dependencies `pytest`, `httpx`, `ruff`. Configure pytest markers `unit` and `integration` and set `testpaths = ["tests"]`. `.env.example` must contain distinct `DATABASE_URL` and `TEST_DATABASE_URL` examples without real credentials.

- [ ] **Step 2: Create Python 3.11 virtual environment and install dependencies**

Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -e ".[dev]"
```

Expected: dependency installation exits with code 0.

- [ ] **Step 3: Write the failing configuration tests**

```python
from app.config import Settings


def test_settings_accept_separate_runtime_and_test_databases() -> None:
    settings = Settings(
        database_url="mysql+pymysql://app:secret@localhost/scheduler",
        test_database_url="mysql+pymysql://app:secret@localhost/scheduler_test",
    )

    assert settings.database_url.endswith("/scheduler")
    assert settings.test_database_url.endswith("/scheduler_test")


def test_test_database_must_end_with_test() -> None:
    try:
        Settings(
            database_url="mysql+pymysql://app:secret@localhost/scheduler",
            test_database_url="mysql+pymysql://app:secret@localhost/scheduler",
        )
    except ValueError as exc:
        assert "_test" in str(exc)
    else:
        raise AssertionError("unsafe test database was accepted")
```

- [ ] **Step 4: Run the tests and verify the missing module failure**

Run: `.\.venv\Scripts\pytest tests/unit/test_config.py -v`

Expected: FAIL because `app.config` does not exist.

- [ ] **Step 5: Implement validated settings and session factories**

`Settings` must use `SettingsConfigDict(env_file=".env", extra="ignore")`, expose both database URLs, and reject a test database whose parsed database name does not end in `_test`. `session.py` must expose `build_engine(url)`, `build_session_factory(engine)`, a lazy application engine, and `get_session()` that always closes the request session.

- [ ] **Step 6: Run focused tests and static checks**

Run:

```powershell
.\.venv\Scripts\pytest tests/unit/test_config.py -v
.\.venv\Scripts\ruff check app tests
```

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml .env.example app tests/unit/test_config.py
git commit -m "工程：建立项目配置与数据库会话基础"
```

### Task 2: Database Schema and Migration

**Files:**
- Create: `app/domain/__init__.py`
- Create: `app/domain/enums.py`
- Create: `app/models/__init__.py`
- Create: `app/models/task.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260902_01_create_scheduler_tables.py`
- Create: `scripts/create_databases.sql`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_schema.py`

- [ ] **Step 1: Write schema tests**

The tests must inspect the real MySQL schema and assert:

```python
assert {"task_groups", "tasks", "task_steps", "step_execution_logs"} <= table_names
assert ("task_id", "step_index") in step_unique_constraints
assert ("task_id", "step_index") in log_unique_constraints
assert ("status", "created_at", "id") in task_indexes
```

Also insert a duplicate step and duplicate log and assert MySQL raises `IntegrityError`.

- [ ] **Step 2: Run the schema tests and verify they fail before tables exist**

Run: `.\.venv\Scripts\pytest tests/integration/test_schema.py -v -m integration`

Expected: FAIL because the migration and tables do not exist. If connection fails, configure `.env` first; never substitute the production database URL.

- [ ] **Step 3: Implement enums, models, and migration**

Use typed SQLAlchemy 2.x mappings. JSON columns must be non-null with application-side `dict` defaults. All tables use InnoDB and `utf8mb4`. Foreign keys cascade from task to steps/logs. Store enum values as lowercase strings. Add unique constraints and the polling index with explicit names.

- [ ] **Step 4: Add guarded integration fixtures**

The fixture must parse `TEST_DATABASE_URL`, reject names not ending in `_test`, run Alembic upgrade once per session, and truncate child tables before each test with foreign-key checks temporarily disabled only on the dedicated test database.

- [ ] **Step 5: Apply migration and run schema tests**

Run:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\pytest tests/integration/test_schema.py -v -m integration
```

Expected: migration succeeds and schema tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app alembic.ini alembic scripts tests/integration
git commit -m "数据库：建立任务调度表结构与迁移"
```

### Task 3: Sticky Parameter Resolution

**Files:**
- Create: `app/domain/parameters.py`
- Create: `tests/unit/test_parameters.py`

- [ ] **Step 1: Write exhaustive failing resolver tests**

Use one scenario that proves all layers and snapshots:

```python
def test_resolve_parameters_applies_literal_group_and_sticky_steps() -> None:
    base = {"region": "cn", "tone": "formal", "retry": 1}
    group = {"tone": "", "channel": "email"}
    steps = [
        {"tone": "friendly", "missing": ""},
        {"tone": "", "retry": 3},
        {"tone": "brief", "channel": "sms"},
    ]

    resolved = resolve_step_parameters(base, group, steps)

    assert resolved == [
        {"region": "cn", "tone": "friendly", "retry": 1, "channel": "email"},
        {"region": "cn", "tone": "friendly", "retry": 3, "channel": "email"},
        {"region": "cn", "tone": "brief", "retry": 3, "channel": "sms"},
    ]
    assert base == {"region": "cn", "tone": "formal", "retry": 1}
    assert group == {"tone": "", "channel": "email"}
```

Add separate tests for no steps, a new step key, an absent key with empty override, and independent returned dictionaries.

- [ ] **Step 2: Run and verify the missing function failure**

Run: `.\.venv\Scripts\pytest tests/unit/test_parameters.py -v`

Expected: FAIL because `resolve_step_parameters` does not exist.

- [ ] **Step 3: Implement the minimal pure resolver**

Copy the base dictionary, update it once with group overrides, skip only L3 values equal to `""`, and append `effective.copy()` after each step.

- [ ] **Step 4: Run unit tests and Ruff**

Run:

```powershell
.\.venv\Scripts\pytest tests/unit -v
.\.venv\Scripts\ruff check app tests
```

Expected: all unit tests pass and Ruff is clean.

- [ ] **Step 5: Commit**

```powershell
git add app/domain/parameters.py tests/unit/test_parameters.py
git commit -m "功能：实现三级粘性参数解析"
```

### Task 4: Task Creation, Listing, and Parameter API

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/schemas.py`
- Create: `app/services/__init__.py`
- Create: `app/services/tasks.py`
- Create: `app/api/routes.py`
- Create: `app/main.py`
- Create: `tests/integration/test_tasks_api.py`

- [ ] **Step 1: Write failing API tests**

Create a task with three steps through `POST /api/tasks`, assert `201`, then list it and request resolved parameters. Assert steps are ordered by `step_index`, the response includes `pending`, and resolved values match Task 3 behavior. Add validation tests for an empty step list and duplicate group name handling.

- [ ] **Step 2: Run and verify 404/import failures**

Run: `.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v -m integration`

Expected: FAIL because routes and application do not exist.

- [ ] **Step 3: Implement schemas and task service**

Use request schemas with bounded names, dictionary parameters, and a non-empty step list. The creation service creates the group, task, and enumerated steps in one transaction. Listing eagerly loads ordered steps and logs to avoid request-time N+1 queries. Response models expose current step name and log count.

- [ ] **Step 4: Implement API assembly and error mapping**

Create the FastAPI app, include `/api` routes, and map duplicate group names to `409`. Use dependency injection for the session so tests can override it.

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v -m integration
.\.venv\Scripts\pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app tests/integration/test_tasks_api.py
git commit -m "功能：提供任务创建查询与参数接口"
```

### Task 5: Exclusive Multi-Process Claiming

**Files:**
- Create: `app/services/claiming.py`
- Modify: `app/api/schemas.py`
- Modify: `app/api/routes.py`
- Create: `tests/integration/test_claiming.py`
- Create: `scripts/run_claim_evidence.py`

- [ ] **Step 1: Write the single-transaction claim test**

Seed two tasks, call `claim_next_task(session, "worker-a")`, and assert the oldest task is committed as `claimed` with worker ID and timestamp. A third call after both are claimed returns `None`.

- [ ] **Step 2: Write the real multi-process attack test**

Seed 100 tasks. Start ten processes with `multiprocessing.get_context("spawn")`; each process creates its own engine and repeatedly claims until empty, returning IDs through a process-safe queue. Assert:

```python
assert len(claimed_ids) == 100
assert len(set(claimed_ids)) == 100
assert set(claimed_ids) == set(seed_ids)
```

- [ ] **Step 3: Run and verify the tests fail without claiming**

Run: `.\.venv\Scripts\pytest tests/integration/test_claiming.py -v -m integration`

Expected: FAIL because the claim service does not exist.

- [ ] **Step 4: Implement explicit locking claim transaction**

Build a select ordered by `created_at, id`, limited to one row, with `.with_for_update(skip_locked=True)`. Execute selection and status mutation inside one `session.begin()` block. Return a detached immutable result after commit. Never perform the select and update in separate sessions.

- [ ] **Step 5: Add claim endpoint and evidence script**

`POST /api/tasks/claim` accepts `worker_id`; return `204` if no pending task remains. The evidence script accepts task/worker/repetition counts, recreates only its tagged sample records, prints counts, and exits nonzero on duplicates or omissions.

- [ ] **Step 6: Run the attack repeatedly**

Run:

```powershell
.\.venv\Scripts\pytest tests/integration/test_claiming.py -v -m integration
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
```

Expected: all tests pass; evidence reports 1,000 total claims across ten runs, zero duplicates, and zero missing tasks.

- [ ] **Step 7: Commit**

```powershell
git add app scripts/run_claim_evidence.py tests/integration/test_claiming.py
git commit -m "并发：实现多进程安全任务认领"
```

### Task 6: Start Transition and Idempotent Completion

**Files:**
- Modify: `app/services/tasks.py`
- Create: `app/services/completion.py`
- Modify: `app/api/schemas.py`
- Modify: `app/api/routes.py`
- Create: `tests/integration/test_completion.py`
- Create: `scripts/run_completion_evidence.py`

- [ ] **Step 1: Write failing transition tests**

Assert only the owning worker can change `claimed` to `running`. Wrong worker, pending task, and terminal task attempts must raise a domain conflict and leave the row unchanged.

- [ ] **Step 2: Write failing idempotency tests**

Cover repeated failure, repeated success, failure followed by success, and success followed by failure. In every case assert one log row; in the last case assert success remains true. Verify an already processed step does not advance `current_step_index` again.

- [ ] **Step 3: Write the five-way concurrent report test**

Start five threads, each with a separate engine connection and session, synchronize them with a barrier, and report the same running step. Assert one log row, one advancement, and the expected task status. Use a second scenario for the final step becoming `done`.

- [ ] **Step 4: Run and verify missing service failures**

Run: `.\.venv\Scripts\pytest tests/integration/test_completion.py -v -m integration`

Expected: FAIL because completion and transition behavior is missing.

- [ ] **Step 5: Implement guarded start and completion transactions**

Start uses a conditional update matching task ID, `claimed`, and worker ID. Completion validates the step exists, locks the task row, uses MySQL `insert(...).on_duplicate_key_update(success = existing_success OR inserted_success)`, then advances only when status is `running` and `current_step_index` equals the reported step. Return the persisted log and final task state after commit.

- [ ] **Step 6: Add endpoints and evidence runner**

Expose start and completion endpoints with `404` and `409` mapping. The evidence runner sends five simultaneous completion requests for a seeded running task and prints request count, log count, advancement count, and final state.

- [ ] **Step 7: Run focused tests and evidence**

Run:

```powershell
.\.venv\Scripts\pytest tests/integration/test_completion.py -v -m integration
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

Expected: all tests pass; evidence reports five reports, one log row, and one state transition.

- [ ] **Step 8: Commit**

```powershell
git add app scripts/run_completion_evidence.py tests/integration/test_completion.py
git commit -m "幂等：保证步骤完成日志单行且成功单调"
```

### Task 7: Operational Dashboard

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/app.js`
- Modify: `app/main.py`
- Modify: `app/api/routes.py`
- Create: `tests/integration/test_dashboard.py`

- [ ] **Step 1: Write failing dashboard delivery tests**

Assert `/` returns HTML containing the task table and controls, static CSS/JS return `200`, and `/api/demo/seed` creates deterministic sample data only when no demo task exists.

- [ ] **Step 2: Run and verify 404 failures**

Run: `.\.venv\Scripts\pytest tests/integration/test_dashboard.py -v -m integration`

Expected: FAIL because static files and seed endpoint do not exist.

- [ ] **Step 3: Implement the dashboard**

Build one dense operational screen with status counters, worker ID input, task table, refresh/seed/claim controls, contextual start and complete actions, and a parameter detail panel. Poll every second. `Complete x5` uses `Promise.allSettled` with five simultaneous fetch requests, then refreshes and displays the aggregate outcome.

- [ ] **Step 4: Implement static serving and deterministic seed**

Mount `/static`, return `index.html` at `/`, and create one three-step demonstration task using base, group, sticky, empty-string, and new-key overrides.

- [ ] **Step 5: Run tests and browser smoke check**

Run:

```powershell
.\.venv\Scripts\pytest tests/integration/test_dashboard.py -v -m integration
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: tests pass; dashboard loads without console errors at `http://127.0.0.1:8000` and the complete action leaves one log.

- [ ] **Step 6: Commit**

```powershell
git add app/static app/main.py app/api/routes.py tests/integration/test_dashboard.py
git commit -m "界面：完成任务状态看板与五次并发演示"
```

### Task 8: Documentation, Collaboration, and Final Verification

**Files:**
- Create: `README.md`
- Create: `COLLAB.md`
- Create: `docs/test-evidence.md`
- Modify: `.gitignore`

- [ ] **Step 1: Write the one-page README**

Document prerequisites, MySQL setup, `.env`, migration, startup, tests, architecture, Python/MySQL rationale, why processes are real concurrency, parameter edge cases, InnoDB locking behavior, explicit omissions, and actual time spent. Keep the main README concise and move raw evidence to `docs/test-evidence.md`.

- [ ] **Step 2: Write collaboration guidance**

Record two candidate names, substantive ownership, disagreements, resolution, and validation performed by each person. State that the second teammate must make real commits before delivery.

- [ ] **Step 3: Capture fresh evidence**

Run:

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

Expected: Ruff clean, all tests pass, zero duplicate/missing claims, and one completion log.

- [ ] **Step 4: Audit Git safety and diff**

Run:

```powershell
git diff --check
git status --short --ignored
git check-ignore -v 实习笔试apikey.txt .env
git grep -n -I -E "api[_-]?key|password|secret" -- . ':!*.example' ':!kGroup实习生笔试题-候选人版-2026-08-10.md'
```

Expected: no whitespace errors, API key and `.env` are ignored, and no real credentials appear in tracked files.

- [ ] **Step 5: Commit final documentation**

```powershell
git add README.md COLLAB.md docs/test-evidence.md .gitignore
git commit -m "文档：补充运行说明协作记录与测试证据"
```

- [ ] **Step 6: Review commit history**

Run: `git log --oneline --decorate --reverse`

Expected: small Chinese-language milestone commits with no secret files and no empty collaboration commits.
