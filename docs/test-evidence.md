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
Python 全量测试：31 passed
Python 编译检查：通过
JavaScript 语法检查：通过
FastAPI 根页面访问：HTTP 200
```

完整 `pytest -v` 实际结果：

```text
31 passed
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

## 浏览器端到端演示

2026-09-02 使用真实浏览器执行以下操作：

1. 打开任务调度看板。
2. 打开“新建任务”弹窗，添加第三个步骤。
3. 创建第一个自定义任务，再创建第二个不同任务。
4. 输入非法 JSON，确认页面阻止提交并保留弹窗。
5. 使用 `dashboard-worker` 认领演示任务并启动。
6. 对三个步骤分别点击一次 `并发完成 x5`。
7. 点击“重置演示任务”，确认演示任务重新变成 `pending`。
8. 点击任务的“参数”，查看 L1/L2/L3 来源和最终生效值。
9. 查看最终任务状态。

实际结果：两个自定义任务同时出现在列表；非法 JSON 没有产生请求；参数面板正确展示 `24度 -> 20度`、L2 的 `2档` 和步骤 2 的“空字符串，沿用当前值”；每轮五个完成请求均返回成功，任务每轮只推进一个步骤，日志数依次为 1、2、3；重置后演示任务得到新的 ID、状态为 `pending` 且日志数为 0；浏览器控制台无脚本错误。

最终页面截图：`docs/dashboard-final.png`。
参数矩阵截图：`docs/parameter-matrix.png`。
