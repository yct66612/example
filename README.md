# 任务调度看板

这是 kGroup 全栈方向笔试题实现：用 FastAPI、SQLAlchemy 2.x 和 MySQL 8 InnoDB 完成任务创建、参数解析、并发认领、幂等日志和状态看板。

## 启动

前置条件：Python 3.11、MySQL 8 InnoDB。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
Get-Content .\scripts\create_databases.sql | mysql -uroot -p
Copy-Item .env.example .env
```

编辑 `.env` 填入实际密码，确认 `TEST_DATABASE_URL` 以 `_test` 数据库结尾，然后运行：

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000`。页面支持新建任务、重置演示任务、认领、启动、查看参数和五次并发完成上报。

点击任务的“参数”可以查看 L1 基础值、L2 组级覆盖、每个步骤的 L3 覆盖和最终生效值；例如 L1 的 `温度=24度` 经步骤 1 覆盖后变为 `20度`，步骤 2 的空字符串会显示为“沿用当前值”。参数面板会把这些来源按表格横向对齐，便于答辩时解释每一步的变化。

## 多实例压测

仓库包含 `docker-compose.distributed.yml`、三个 FastAPI 实例、Nginx、共享 MySQL、两份 JMeter 计划和数据库校验脚本。本机没有 Docker 时可运行 `.\.venv\Scripts\python scripts\run_local_distributed.py` 启动等价的三实例轮询环境。完整操作见 `docs/distributed-load-test.md`。

## 选型与架构

- **Python 3.11**：团队熟悉，FastAPI 类型清晰、开发快；pytest 适合本题需要的单元、集成和多进程测试。
- **MySQL 8 InnoDB**：支持事务、行锁、`FOR UPDATE SKIP LOCKED`、唯一约束和 Upsert；题目规模下不需要 Redis 等外部中间件。
- **SQLAlchemy 2.x**：普通 CRUD 使用 ORM；锁定读取和 Upsert 使用显式 API，事务边界清晰且避免手写 SQL 字符串。
- **并发模型**：每个 worker 使用独立进程、Engine、Session 和 MySQL 连接；任务认领在同一事务内完成锁定读取与状态更新。
- **前端**：FastAPI 托管原生 HTML/CSS/JavaScript，每秒轮询，无额外构建流程。

## 已验证边界

- L2/L3 对嵌套 JSON 递归深度合并，不会覆盖整个对象；L2 空字符串按字面值覆盖，L3 任意层级空字符串表示不覆盖；L3 非空值向后粘性生效并可新增 key。
- 参数值支持字符串、数字、布尔值、数组和嵌套对象；数组作为整体值替换，不按下标合并。
- 未来步骤、未启动任务不能上报；错误 worker 不能启动或完成任务；`running` 任务不能重复启动。
- 同一步骤重复上报只有一条日志；成功日志不能被失败覆盖；重复请求只推进一次。
- MySQL `1205/1213` 会回滚并有限重试；重置演示任务不会删除其他组的同名自定义任务。

## 测试与证据

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts\run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts\run_completion_evidence.py
.\.venv\Scripts\python scripts\run_distributed_completion_evidence.py --processes 5 --runs 10
```

证据脚本默认在校验后删除本批测试数据。答辩时追加 `--keep-data` 可保留记录，并在控制台输出任务 ID 或批次前缀：

```powershell
.\.venv\Scripts\python scripts\run_claim_evidence.py --tasks 100 --workers 10 --keep-data
.\.venv\Scripts\python scripts\run_completion_evidence.py --keep-data
.\.venv\Scripts\python scripts\run_distributed_completion_evidence.py --processes 5 --runs 10 --keep-data
```

已验证：`60 passed`；10 个真实进程累计认领 1000 个任务，重复 0、遗漏 0；HTTP 多实例测试 100 次认领无重复无遗漏，20 次同步完成最终只有 1 条日志和 1 次推进。详细输出和截图见 `docs/test-evidence.md`。

## 明确删减项

未实现认证、外部队列、分布式锁、worker 租约、失联任务回收、任务取消、真实消息发送和生产监控。原因是题目规模下 MySQL 行锁已足够，且这些不属于硬性要求；生产版本应补充租约、超时回收、权限和监控。
