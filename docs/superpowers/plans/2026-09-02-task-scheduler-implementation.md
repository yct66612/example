# 任务调度看板实施计划

> **执行要求：** 实施时按任务顺序逐项完成，每个功能遵循“先写失败测试、确认失败原因、最小实现、确认通过、中文提交”的流程。每个步骤使用复选框跟踪。

**目标：** 构建一个基于 FastAPI 和 MySQL 的任务调度系统，支持粘性参数解析、多进程唯一认领、幂等完成日志和极简轮询看板。

**架构：** FastAPI 负责 HTTP 接口和静态资源；独立 Service 模块负责事务边界；SQLAlchemy 2.x 映射 MySQL InnoDB 表；纯领域函数负责参数解析。单元测试验证确定性规则，集成测试使用独立 Engine、连接、线程和进程攻击专用 `_test` 数据库。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2.x、Alembic、PyMySQL、Pydantic Settings、pytest、原生 HTML/CSS/JavaScript。

---

## 文件规划

- `pyproject.toml`：依赖、pytest、Ruff 和打包配置。
- `.env.example`：不含真实凭证的运行与测试数据库配置示例。
- `app/config.py`：经过校验的环境配置。
- `app/db/base.py`：SQLAlchemy 声明式基类。
- `app/db/session.py`：Engine 和 Session 工厂。
- `app/models/task.py`：任务组、任务、步骤和执行日志模型。
- `app/domain/enums.py`：任务状态枚举。
- `app/domain/parameters.py`：纯粘性参数解析器。
- `app/services/tasks.py`：任务创建、查询和启动流转。
- `app/services/claiming.py`：唯一认领事务。
- `app/services/completion.py`：幂等完成事务。
- `app/api/schemas.py`：HTTP 请求与响应模型。
- `app/api/routes.py`：API 路由和错误映射。
- `app/main.py`：FastAPI 应用组装与静态资源路由。
- `app/static/*`：操作看板。
- `alembic.ini`、`alembic/env.py`、`alembic/versions/*`：数据库迁移。
- `tests/unit/*`：不依赖数据库的行为测试。
- `tests/integration/*`：真实 MySQL 与 API 集成测试。
- `scripts/create_databases.sql`：数据库和用户初始化示例。
- `scripts/run_claim_evidence.py`：多进程认领证据脚本。
- `scripts/run_completion_evidence.py`：重复完成上报证据脚本。
- `README.md`：一页以内的提交说明。

## 任务一：项目基础与配置

**文件：**
- 新建：`pyproject.toml`
- 新建：`.env.example`
- 新建：`app/__init__.py`
- 新建：`app/config.py`
- 新建：`app/db/__init__.py`
- 新建：`app/db/base.py`
- 新建：`app/db/session.py`
- 新建：`tests/unit/test_config.py`

- [ ] **步骤 1：建立项目元数据和环境变量示例**

Python 版本要求为 `>=3.11`。运行依赖包含 `fastapi`、`uvicorn[standard]`、`sqlalchemy`、`alembic`、`pymysql`、`pydantic-settings`；开发依赖包含 `pytest`、`httpx`、`ruff`。pytest 配置 `unit` 和 `integration` 标记，测试目录设置为 `tests`。`.env.example` 提供不同的 `DATABASE_URL` 和 `TEST_DATABASE_URL`，不得包含真实密码。

- [ ] **步骤 2：创建 Python 3.11 虚拟环境并安装依赖**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -e ".[dev]"
```

预期：依赖安装成功，退出码为 0。

- [ ] **步骤 3：先写配置失败测试**

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

- [ ] **步骤 4：运行测试并确认因缺少模块而失败**

运行：`.\.venv\Scripts\pytest tests/unit/test_config.py -v`

预期：因 `app.config` 不存在而失败，而不是测试语法错误。

- [ ] **步骤 5：实现配置校验与 Session 工厂**

`Settings` 使用 `SettingsConfigDict(env_file=".env", extra="ignore")`，暴露运行和测试数据库 URL，并解析数据库名，拒绝名称不以 `_test` 结尾的测试数据库。`session.py` 提供 `build_engine(url)`、`build_session_factory(engine)`、延迟创建的应用 Engine，以及始终关闭请求 Session 的 `get_session()`。

- [ ] **步骤 6：运行配置测试和静态检查**

```powershell
.\.venv\Scripts\pytest tests/unit/test_config.py -v
.\.venv\Scripts\ruff check app tests
```

预期：测试全部通过，Ruff 无错误。

- [ ] **步骤 7：中文提交**

```powershell
git add pyproject.toml .env.example app tests/unit/test_config.py
git commit -m "工程：建立项目配置与数据库会话基础"
```

## 任务二：数据库表结构与迁移

**文件：**
- 新建：`app/domain/__init__.py`
- 新建：`app/domain/enums.py`
- 新建：`app/models/__init__.py`
- 新建：`app/models/task.py`
- 新建：`alembic.ini`
- 新建：`alembic/env.py`
- 新建：`alembic/script.py.mako`
- 新建：`alembic/versions/20260902_01_create_scheduler_tables.py`
- 新建：`scripts/create_databases.sql`
- 新建：`tests/integration/conftest.py`
- 新建：`tests/integration/test_schema.py`

- [ ] **步骤 1：先写真实 MySQL 表结构测试**

测试通过 SQLAlchemy Inspector 验证四张表、步骤和日志唯一约束、任务认领索引：

```python
assert {"task_groups", "tasks", "task_steps", "step_execution_logs"} <= table_names
assert ("task_id", "step_index") in step_unique_constraints
assert ("task_id", "step_index") in log_unique_constraints
assert ("status", "created_at", "id") in task_indexes
```

另外插入重复步骤和重复日志，确认 MySQL 抛出 `IntegrityError`。

- [ ] **步骤 2：迁移前运行测试并确认失败**

运行：`.\.venv\Scripts\pytest tests/integration/test_schema.py -v -m integration`

预期：因为迁移和表尚不存在而失败。如果数据库连接失败，先配置 `.env`，绝不能临时把测试 URL 指向业务数据库。

- [ ] **步骤 3：实现枚举、模型和迁移**

使用 SQLAlchemy 2.x 类型化映射。JSON 字段非空并使用应用侧 `dict` 默认值。所有表指定 InnoDB 和 `utf8mb4`。任务删除时级联删除步骤和日志。枚举以小写字符串保存。唯一约束和索引均使用明确名称。

- [ ] **步骤 4：建立有安全保护的集成测试夹具**

夹具解析 `TEST_DATABASE_URL`，数据库名不是 `_test` 时立即拒绝。测试会话开始时执行 Alembic 升级；每个测试前按外键依赖顺序清空表，仅允许在专用测试库中临时关闭外键检查。

- [ ] **步骤 5：执行迁移并运行表结构测试**

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\pytest tests/integration/test_schema.py -v -m integration
```

预期：迁移成功，表结构和约束测试全部通过。

- [ ] **步骤 6：中文提交**

```powershell
git add app alembic.ini alembic scripts tests/integration
git commit -m "数据库：建立任务调度表结构与迁移"
```

## 任务三：三级粘性参数解析

**文件：**
- 新建：`app/domain/parameters.py`
- 新建：`tests/unit/test_parameters.py`

- [ ] **步骤 1：先写完整的失败测试**

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

再分别测试没有步骤、步骤新增 key、不存在 key 的空字符串覆盖，以及返回快照互不共享对象。

- [ ] **步骤 2：运行测试并确认缺少函数导致失败**

运行：`.\.venv\Scripts\pytest tests/unit/test_parameters.py -v`

预期：因 `resolve_step_parameters` 不存在而失败。

- [ ] **步骤 3：实现最小纯函数**

复制基础参数，统一应用一次组级覆盖，只跳过 L3 中等于 `""` 的值，每处理完一个步骤追加 `effective.copy()`。

- [ ] **步骤 4：运行全部单元测试和 Ruff**

```powershell
.\.venv\Scripts\pytest tests/unit -v
.\.venv\Scripts\ruff check app tests
```

预期：所有单元测试通过，Ruff 无错误。

- [ ] **步骤 5：中文提交**

```powershell
git add app/domain/parameters.py tests/unit/test_parameters.py
git commit -m "功能：实现三级粘性参数解析"
```

## 任务四：任务创建、查询与参数接口

**文件：**
- 新建：`app/api/__init__.py`
- 新建：`app/api/schemas.py`
- 新建：`app/services/__init__.py`
- 新建：`app/services/tasks.py`
- 新建：`app/api/routes.py`
- 新建：`app/main.py`
- 新建：`tests/integration/test_tasks_api.py`

- [ ] **步骤 1：先写 API 失败测试**

通过 `POST /api/tasks` 创建含三个步骤的任务并断言返回 `201`；随后查询任务列表和参数快照。断言步骤按 `step_index` 排序、初始状态为 `pending`，参数结果符合任务三的规则。补充空步骤列表和重复组名测试。

- [ ] **步骤 2：运行测试并确认接口尚不存在**

运行：`.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v -m integration`

预期：因为应用或路由不存在而失败。

- [ ] **步骤 3：实现 Schema 和任务 Service**

请求模型限制名称长度，参数使用字典，步骤列表至少包含一项。创建 Service 在一次事务中创建任务组、任务和按输入顺序编号的步骤。列表查询预加载有序步骤和日志，避免 N+1 查询。响应包含当前步骤名和日志数量。

- [ ] **步骤 4：组装应用和错误映射**

创建 FastAPI 应用并挂载 `/api` 路由。重复组名映射为 `409`。Session 通过依赖注入提供，便于测试覆盖。

- [ ] **步骤 5：运行接口测试和全量测试**

```powershell
.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v -m integration
.\.venv\Scripts\pytest -v
```

预期：全部测试通过。

- [ ] **步骤 6：中文提交**

```powershell
git add app tests/integration/test_tasks_api.py
git commit -m "功能：提供任务创建查询与参数接口"
```

## 任务五：多进程唯一任务认领

**文件：**
- 新建：`app/services/claiming.py`
- 修改：`app/api/schemas.py`
- 修改：`app/api/routes.py`
- 新建：`tests/integration/test_claiming.py`
- 新建：`scripts/run_claim_evidence.py`

- [ ] **步骤 1：先写单事务认领测试**

创建两个任务，调用 `claim_next_task(session, "worker-a")`，断言最早任务已经提交为 `claimed`，同时保存 worker ID 和时间。两个任务认领后再次调用应返回 `None`。

- [ ] **步骤 2：编写真实多进程攻击测试**

创建 100 个任务，使用 `multiprocessing.get_context("spawn")` 启动 10 个进程。每个进程独立创建 Engine 和连接，循环认领到没有任务为止，并通过进程安全队列返回 ID：

```python
assert len(claimed_ids) == 100
assert len(set(claimed_ids)) == 100
assert set(claimed_ids) == set(seed_ids)
```

- [ ] **步骤 3：运行测试并确认缺少认领逻辑导致失败**

运行：`.\.venv\Scripts\pytest tests/integration/test_claiming.py -v -m integration`

预期：因认领 Service 不存在而失败。

- [ ] **步骤 4：实现显式锁定认领事务**

查询按 `created_at, id` 排序，只取一行，并调用 `.with_for_update(skip_locked=True)`。查询和状态修改必须位于同一个 `session.begin()` 中。提交后返回脱离 Session 的不可变结果，禁止用两个 Session 分别查询和更新。

- [ ] **步骤 5：增加认领接口和证据脚本**

`POST /api/tasks/claim` 接收 `worker_id`；没有 pending 任务时返回 `204`。证据脚本接收任务数、worker 数和重复轮数，只清理自己带标记的样本数据，输出总数、重复数和遗漏数，出现异常时返回非零退出码。

- [ ] **步骤 6：重复执行并发攻击**

```powershell
.\.venv\Scripts\pytest tests/integration/test_claiming.py -v -m integration
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
```

预期：测试通过；十轮累计认领 1000 个任务，重复数为 0，遗漏数为 0。

- [ ] **步骤 7：中文提交**

```powershell
git add app scripts/run_claim_evidence.py tests/integration/test_claiming.py
git commit -m "并发：实现多进程安全任务认领"
```

## 任务六：启动流转与幂等完成上报

**文件：**
- 修改：`app/services/tasks.py`
- 新建：`app/services/completion.py`
- 修改：`app/api/schemas.py`
- 修改：`app/api/routes.py`
- 新建：`tests/integration/test_completion.py`
- 新建：`scripts/run_completion_evidence.py`

- [ ] **步骤 1：先写启动状态流转失败测试**

只有持有任务的 worker 可以把 `claimed` 改为 `running`。错误 worker、pending 任务和终态任务必须抛出领域冲突，并保持数据库状态不变。

- [ ] **步骤 2：先写日志幂等失败测试**

覆盖重复失败、重复成功、失败后成功、成功后失败。每种情况最终都只能有一条日志；成功后失败仍保持成功。重复处理已完成步骤不能再次推进 `current_step_index`。

- [ ] **步骤 3：编写五路并发上报测试**

启动五个线程，每个线程使用独立连接和 Session，通过 Barrier 同时上报同一个 running 步骤。断言只有一条日志、只推进一次，并得到正确任务状态。再测试最后一步成功后任务变成 `done`。

- [ ] **步骤 4：运行测试并确认服务尚不存在**

运行：`.\.venv\Scripts\pytest tests/integration/test_completion.py -v -m integration`

预期：因为启动和完成逻辑尚未实现而失败。

- [ ] **步骤 5：实现带条件保护的启动与完成事务**

启动使用包含任务 ID、`claimed` 状态和 worker ID 的条件更新。完成操作校验步骤存在并锁定任务行，使用 MySQL `insert(...).on_duplicate_key_update(...)` 保证成功状态为“已有成功 OR 新上报成功”，随后仅在状态为 `running` 且当前步骤序号与上报步骤相等时推进。提交后返回持久化日志和最终任务状态。

- [ ] **步骤 6：增加接口和证据脚本**

增加启动和完成接口，统一映射 `404` 与 `409`。证据脚本对演示中的 running 任务同时发出五次完成请求，输出请求数、日志数、推进次数和最终状态。

- [ ] **步骤 7：运行测试和幂等证据**

```powershell
.\.venv\Scripts\pytest tests/integration/test_completion.py -v -m integration
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

预期：测试全部通过；五次上报只产生一条日志和一次状态推进。

- [ ] **步骤 8：中文提交**

```powershell
git add app scripts/run_completion_evidence.py tests/integration/test_completion.py
git commit -m "幂等：保证步骤完成日志单行且成功单调"
```

## 任务七：极简操作看板

**文件：**
- 新建：`app/static/index.html`
- 新建：`app/static/styles.css`
- 新建：`app/static/app.js`
- 修改：`app/main.py`
- 修改：`app/api/routes.py`
- 新建：`tests/integration/test_dashboard.py`

- [ ] **步骤 1：先写看板交付失败测试**

断言 `/` 返回包含任务表和操作控件的 HTML；CSS 和 JS 返回 `200`；`/api/demo/seed` 只在演示任务不存在时创建确定性样本。

- [ ] **步骤 2：运行测试并确认静态资源不存在**

运行：`.\.venv\Scripts\pytest tests/integration/test_dashboard.py -v -m integration`

预期：因为静态资源和演示接口尚不存在而失败。

- [ ] **步骤 3：实现操作看板**

构建一个紧凑的操作页面，包含状态统计、worker ID 输入、任务表、刷新/创建样本/认领按钮、按状态出现的启动与完成按钮，以及参数详情区域。页面每秒轮询。`并发完成 x5` 使用 `Promise.allSettled` 同时发送五个请求，然后刷新并展示汇总结果。

- [ ] **步骤 4：实现静态资源托管和演示数据**

挂载 `/static`，根路径返回 `index.html`。演示任务固定包含三个步骤，覆盖 base、group、粘性覆盖、空字符串和新增 key。

- [ ] **步骤 5：运行测试和浏览器冒烟检查**

```powershell
.\.venv\Scripts\pytest tests/integration/test_dashboard.py -v -m integration
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

预期：测试通过；`http://127.0.0.1:8000` 正常加载且无控制台错误，并发完成后日志数量为一。

- [ ] **步骤 6：中文提交**

```powershell
git add app/static app/main.py app/api/routes.py tests/integration/test_dashboard.py
git commit -m "界面：完成任务状态看板与五次并发演示"
```

## 任务八：交付文档与最终验证

**文件：**
- 新建：`README.md`
- 新建：`docs/test-evidence.md`
- 修改：`.gitignore`

- [ ] **步骤 1：编写一页以内的中文 README**

说明前置条件、MySQL 初始化、`.env`、迁移、启动、测试、架构、选择 Python/MySQL 的理由、多进程测试为何是真并发、参数边界、InnoDB 锁机制、明确删减项和实际耗时。原始证据放入 `docs/test-evidence.md`，避免 README 过长。

- [ ] **步骤 2：采集最新验证证据**

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

预期：Ruff 无错误、所有测试通过、重复/遗漏认领均为 0、完成日志数量为 1。

- [ ] **步骤 3：审计 Git 安全和变更内容**

```powershell
git diff --check
git status --short --ignored
git check-ignore -v 实习笔试apikey.txt .env
git grep -n -I -E "api[_-]?key|password|secret" -- . ':!*.example' ':!kGroup实习生笔试题-候选人版-2026-08-10.md'
```

预期：没有空白错误；API Key 和 `.env` 均被忽略；已跟踪文件中不存在真实凭证。

- [ ] **步骤 4：提交最终文档**

```powershell
git add README.md docs/test-evidence.md .gitignore
git commit -m "文档：补充运行说明与测试证据"
```

- [ ] **步骤 5：检查中文提交历史**

运行：`git log --oneline --decorate --reverse`

预期：提交按照小型里程碑排列，提交信息均为中文，不包含凭证和空协作提交。
