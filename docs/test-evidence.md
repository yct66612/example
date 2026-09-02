# 测试证据记录

## 本地环境

- 操作系统：Windows
- Python：3.11
- MySQL：8.0.31
- 分支：`feature/任务调度系统`

## 已完成验证

在未配置 `TEST_DATABASE_URL` 的情况下，以下本地验证已执行：

```text
Ruff：通过
Python 单元测试：7 passed
Python 编译检查：通过
JavaScript 语法检查：通过
FastAPI 根页面访问：HTTP 200
```

完整 `pytest -v` 当前结果：

```text
7 passed, 14 skipped
```

13 个跳过项是需要专用 MySQL 测试库的集成测试，原因是当前 `.env` 尚未配置 `TEST_DATABASE_URL`。

## 配置测试库后采集

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
```

预期证据：

```text
总认领数：1000
重复认领数：0
遗漏任务数：0
完成上报次数：5
最终日志行数：1
最终任务状态：done
```

运行后请把真实终端输出追加到本文件，并注明执行日期和数据库版本。
