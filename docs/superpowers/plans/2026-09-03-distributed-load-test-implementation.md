# 多实例分布式压测实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加 Nginx + 三 FastAPI 实例 + MySQL 的容器编排，以及可实际运行和校验的 JMeter 并发测试。

**Architecture:** 应用通过响应头暴露实例身份；Docker Compose 统一启动共享数据库、迁移服务、三个无状态应用实例和 Nginx。JMeter 测试计划只通过 HTTP 访问应用，准备与校验脚本负责生成隔离数据并核对 MySQL 最终状态。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、MySQL 8、Docker Compose、Nginx、Apache JMeter 5.6.3。

---

### Task 1: 实例可观测性

**Files:**
- Modify: `app/config.py`
- Modify: `app/main.py`
- Modify: `tests/unit/test_config.py`
- Create: `tests/integration/test_observability.py`

- [ ] **Step 1: 编写失败测试**

```python
def test_settings_has_local_instance_name():
    assert Settings(...).app_instance == "local"

def test_health_and_instance_headers(client):
    response = client.get("/healthz")
    assert response.json()["status"] == "ok"
    assert response.headers["X-App-Instance"]
    assert response.headers["X-Request-ID"]
```

- [ ] **Step 2: 运行测试并确认缺少字段和路由而失败**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_config.py tests/integration/test_observability.py`

- [ ] **Step 3: 实现配置、健康检查和响应头**

在 `Settings` 中增加默认值为 `local` 的 `app_instance`。在 FastAPI 中间件中读取或生成请求 ID，写入两个响应头并记录方法、路径、状态、耗时和实例名；增加 `/healthz`。

- [ ] **Step 4: 运行定向测试**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_config.py tests/integration/test_observability.py`

### Task 2: 容器和负载均衡

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.distributed.yml`
- Create: `deploy/nginx.conf`
- Create: `deploy/mysql/01-test-database.sql`

- [ ] **Step 1: 编写静态契约测试**

创建 `tests/unit/test_distributed_deployment.py`，断言 Compose 包含 `mysql`、`migrate`、`app-1`、`app-2`、`app-3`、`nginx`，三个应用实例具有不同 `APP_INSTANCE`，Nginx 上游包含三个实例并透传请求 ID。

- [ ] **Step 2: 运行测试并确认配置文件不存在而失败**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_distributed_deployment.py`

- [ ] **Step 3: 实现部署文件**

迁移服务等待 MySQL 健康后执行 `alembic upgrade head`；三个应用服务共享数据库但使用不同实例名；Nginx 暴露 `8080` 并轮询三个上游。

- [ ] **Step 4: 运行静态契约测试**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_distributed_deployment.py`

### Task 3: 压测准备与结果校验

**Files:**
- Create: `scripts/prepare_http_load_test.py`
- Create: `scripts/verify_http_load_test.py`
- Create: `tests/unit/test_http_load_test_scripts.py`

- [ ] **Step 1: 编写失败测试**

测试上下文 JSON 读写、认领结果去重和遗漏计算、完成日志校验，以及只允许 `_test` 数据库。

- [ ] **Step 2: 运行测试并确认模块不存在而失败**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_http_load_test_scripts.py`

- [ ] **Step 3: 实现脚本**

准备脚本创建随机前缀认领任务和一个已启动完成任务，输出 `load-test-results/context.json`。校验脚本读取 JMeter CSV 与数据库，输出总响应、唯一任务 ID、遗漏、实例分布、日志数和最终任务状态。

- [ ] **Step 4: 运行脚本单元测试**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_http_load_test_scripts.py`

### Task 4: JMeter 测试计划

**Files:**
- Create: `tests/jmeter/claim-concurrency.jmx`
- Create: `tests/jmeter/completion-idempotency.jmx`

- [ ] **Step 1: 创建 JMX 静态测试**

在部署契约测试中解析 XML，断言认领计划包含并发线程组和任务 ID 结果记录器，完成计划包含 Synchronizing Timer、相同任务步骤请求和实例响应头记录器。

- [ ] **Step 2: 运行测试确认 JMX 不存在而失败**

Run: `.\.venv\Scripts\pytest -q tests/unit/test_distributed_deployment.py`

- [ ] **Step 3: 实现两份 JMX**

所有主机、端口、线程数、循环数、上下文和结果文件通过 `-J` 参数传入；结果使用 JSR223 PostProcessor 追加为 CSV。

- [ ] **Step 4: 使用 JMeter CLI 实际执行**

先启动使用测试数据库的本地 Uvicorn，再执行两份 JMX，随后运行校验脚本。预期认领无重复无遗漏，完成日志一条且任务只推进一次。

### Task 5: 文档与最终验证

**Files:**
- Modify: `README.md`
- Modify: `docs/test-evidence.md`
- Modify locally only: `docs/代码详细说明.md`

- [ ] **Step 1: 写启动和答辩命令**

记录 `docker compose -f docker-compose.distributed.yml up --build`、JMeter CLI、数据库查询和实例分布查看方式。

- [ ] **Step 2: 运行完整验证**

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -q
.\.venv\Scripts\python -m compileall -q app scripts tests
node --check app/static/app.js
git diff --check
```

- [ ] **Step 3: 中文提交并推送**

仅提交源码、部署配置、JMX、测试和交付文档，不提交 `docs/代码详细说明.md`。
