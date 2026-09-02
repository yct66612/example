# 测试证据记录

## 本地环境

- 操作系统：Windows
- Python：3.11
- MySQL：8.0.31
- 分支：`feature/任务调度系统`
- 执行日期：2026-09-02

## 已完成验证

已配置 `TEST_DATABASE_URL` 并执行以下本地验证：

```text
Ruff：通过
Python 全量测试：21 passed
Python 编译检查：通过
JavaScript 语法检查：通过
FastAPI 根页面访问：HTTP 200
```

完整 `pytest -v` 实际结果：

```text
21 passed
```

集成测试使用本地 MySQL 8.0.31 的 `task_scheduler_test` 数据库，包含真实多进程认领和并发幂等上报。

## 采集命令

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

已采集证据：

```text
总认领数：1000
重复认领数：0
遗漏任务数：0
完成上报次数：5
最终日志行数：1
最终任务状态：done
```
