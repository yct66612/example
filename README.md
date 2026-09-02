# 任务调度看板

这是 kGroup 全栈方向笔试题的实现：用 FastAPI、SQLAlchemy 2.x 和 MySQL 8 InnoDB 完成任务创建、步骤参数解析、并发认领、幂等完成日志和状态看板。

## 启动

前置条件：Python 3.11、MySQL 8 InnoDB。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
```

使用有权限的 MySQL 账号执行 `scripts/create_databases.sql`。然后复制环境示例并填入实际密码：

```powershell
Copy-Item .env.example .env
```

确认 `TEST_DATABASE_URL` 的数据库名以 `_test` 结尾，再执行迁移和启动：

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`。页面提供创建演示任务、认领、启动、查看参数和五次并发完成上报。

## 测试

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

没有配置 `TEST_DATABASE_URL` 时，MySQL 集成测试会安全跳过；单元测试仍可运行。并发证据脚本只接受数据库名以 `_test` 结尾的 URL。

## 核心设计

- 参数解析：先复制 L1 base，再按字面值应用 L2 group override；L3 非空覆盖具有粘性，L3 空字符串保留当前有效值。
- 任务认领：同一个事务和连接内执行 `SELECT ... FOR UPDATE SKIP LOCKED` 与状态更新；索引为 `(status, created_at, id)`。每个 worker 进程自己创建 Engine 和连接。
- 幂等日志：`UNIQUE(task_id, step_index)` 防重复行，MySQL Upsert 使用 `已有成功 OR 新上报成功`，成功不能被后续失败降级。
- 状态：`pending -> claimed -> running -> done|failed`；完成推进带当前步骤条件，重复上报不会重复推进。
- 前端：FastAPI 托管原生 HTML/JS，每秒轮询；`并发完成 x5` 用五个同时发出的请求演示幂等性。

常规 CRUD 使用 SQLAlchemy ORM；锁定读取和 MySQL Upsert 使用 SQLAlchemy 的显式 Core/方言 API，保留事务与并发语义，同时避免手工拼接 SQL。

## 明确边界

本题未实现认证、外部消息队列、分布式锁、worker 租约、失联任务回收和生产级监控。题目规模下使用 MySQL 行锁即可，避免引入不必要的基础设施。当前实现默认 worker 在完成任务前保持在线；生产版本需要增加租约、超时回收和权限控制。

原始测试输出记录在 `docs/test-evidence.md`。
