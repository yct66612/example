# 测试证据记录

## 本地环境

- 操作系统：Windows
- Python：3.11
- MySQL：8.0.31
- 分支：`feature/任务调度系统`
- 执行日期：2026-09-03

## 已完成验证

已配置 `TEST_DATABASE_URL` 并执行以下本地验证：

```text
Ruff：通过
Python 全量测试：60 passed
Python 编译检查：通过
JavaScript 语法检查：通过
FastAPI 根页面访问：HTTP 200
```

完整 `pytest -v` 实际结果：

```text
60 passed
```

集成测试使用本地 MySQL 8.0.31 的 `task_scheduler_test` 数据库，包含真实多进程认领和并发幂等上报。

## 采集命令

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\pytest -v
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
.\.venv\Scripts\python scripts/run_distributed_completion_evidence.py --processes 5 --runs 10
```

默认执行会清理本批证据数据。需要在数据库中现场查看时追加 `--keep-data`；认领脚本只处理本次随机前缀对应的任务，不会认领以前保留的数据或其他测试任务。

```sql
SELECT id, name, status, worker_id, claimed_at, current_step_index
FROM tasks
WHERE name LIKE 'evidence-%' OR name LIKE 'completion-evidence-%'
   OR name LIKE 'distributed-evidence-%'
ORDER BY id DESC;

SELECT task_id, step_index, COUNT(*) AS log_count, MAX(success) AS success
FROM step_execution_logs
GROUP BY task_id, step_index
ORDER BY task_id DESC;
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

分布式幂等证据：

```text
真实进程数：5，运行轮数：10
重复上报总数：50
最终日志总数：10
实际推进总数：10
最终任务状态：done
```

每个进程使用独立 Engine、Session 和 MySQL 连接，并通过进程 Barrier 同步后上报同一个步骤。

参数值类型测试覆盖：字符串、整数、布尔值、数组、嵌套对象；数组按整体替换，嵌套对象按 key 递归合并。

## HTTP 多实例实测

2026-09-03 使用三个独立 Uvicorn 进程（`app-1/app-2/app-3`）、本地轮询入口 `127.0.0.1:8080`、共享 MySQL 和 JMeter 5.6.3 执行完整 HTTP 链路。Docker/Nginx 配置已提供，但本机未安装 Docker，因此没有声称完成容器运行验证。

```text
认领请求：100，成功：100，错误：0，重复：0，遗漏：0
认领实例分布：app-1=33，app-2=34，app-3=33
数据库 claimed：100

同一步骤完成请求：20，成功：20，错误：0
完成实例分布：app-1=7，app-2=6，app-3=7
数据库日志：1，current_step_index=1，status=done
最终校验：valid=true
```

JMeter HTML 报告已生成在本地忽略目录 `load-test-results/multi-instance/claim-report` 和 `load-test-results/multi-instance/completion-report`。认领与完成报告错误率均为 0%。

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

参数合并单元测试另外覆盖多层嵌套对象：内层只覆盖一个 key 时，同级 key、祖先对象和更深层对象都保留；嵌套 L3 空字符串继续沿用上一个粘性值。

最终页面截图：`docs/dashboard-final.png`。
参数矩阵截图：`docs/parameter-matrix.png`。
