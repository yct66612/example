# 参数来源与生效值面板实施计划

> **执行要求：** 先写失败测试，再实现最小功能；所有 Git 提交信息使用中文。`docs/代码详细说明.md` 只在本地同步，不加入 Git。

**目标：** 让任务参数面板同时展示 L1、L2、每个步骤的 L3 覆盖和最终生效值，直观看出参数如何沿步骤变化。

**架构：** 后端扩展现有参数接口，保留 `snapshots` 兼容字段，同时返回基础参数、组级覆盖、步骤覆盖和逐步生效快照。前端将这些数据渲染成响应式对照表，不改变任务执行和参数解析逻辑。

**技术栈：** FastAPI、Pydantic、pytest、原生 HTML/CSS/JavaScript。

---

## 文件规划

- 修改：`app/api/schemas.py`：增加参数来源和逐步骤生效值响应模型。
- 修改：`app/api/routes.py`：返回参数来源、L3 覆盖和生效快照。
- 修改：`app/static/app.js`：渲染参数对照表和空字符串继承提示。
- 修改：`app/static/styles.css`：增加参数矩阵的响应式样式。
- 修改：`tests/integration/test_tasks_api.py`：验证参数接口返回分层来源和生效值。
- 修改：`tests/integration/test_task_creation_ui.py`：验证前端参数矩阵契约。
- 修改：`README.md`：补充参数面板使用说明。
- 修改：`docs/test-evidence.md`：记录参数来源面板浏览器验证。
- 修改：`docs/代码详细说明.md`：同步新增接口和前端函数，不提交。

## 任务一：后端参数详情接口

- [ ] **步骤 1：先写返回参数来源的失败测试**

创建包含 L1、L2 和两个 L3 步骤的任务，调用 `/api/tasks/{id}/parameters`，断言返回 `base_parameters`、`group_overrides`、逐步骤 `override`、逐步骤 `effective`，并保留原有 `snapshots`。

- [ ] **步骤 2：运行测试确认字段缺失**

```powershell
.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v
```

预期：现有接口缺少分层参数字段而失败。

- [ ] **步骤 3：实现响应模型和路由数据组装**

后端复用已有 `resolve_step_parameters`，将每个步骤的 `parameter_overrides` 与对应快照组合返回，不修改参数解析规则。

- [ ] **步骤 4：运行接口测试**

```powershell
.\.venv\Scripts\pytest tests/integration/test_tasks_api.py -v
```

预期：参数详情测试通过，旧 `snapshots` 测试继续通过。

- [ ] **步骤 5：中文提交**

```powershell
git add app/api/schemas.py app/api/routes.py tests/integration/test_tasks_api.py
git commit -m "接口：返回参数来源与逐步生效值"
```

## 任务二：前端参数对照表

- [ ] **步骤 1：先写前端静态契约失败测试**

断言 `app.js` 包含参数矩阵、L1、L2、L3 和生效值对应的渲染标识。

- [ ] **步骤 2：运行测试确认前端矩阵尚不存在**

```powershell
.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v
```

预期：当前脚本只有逐步骤 JSON 展示，缺少参数矩阵标识。

- [ ] **步骤 3：实现参数矩阵渲染**

点击任务的“参数”按钮后显示：参数名、L1 基础值、L2 组覆盖值，以及每个步骤的 L3 覆盖值和最终生效值。缺失值显示“未设置”，L3 空字符串显示“空字符串，沿用当前值”。所有动态内容经过 HTML 转义。

- [ ] **步骤 4：实现响应式样式**

参数表允许横向滚动，步骤数量增加时不撑破页面；生效值和覆盖值使用不同的视觉标记。

- [ ] **步骤 5：运行静态检查和页面契约测试**

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v
node --check app/static/app.js
```

- [ ] **步骤 6：中文提交**

```powershell
git add app/static/app.js app/static/styles.css tests/integration/test_task_creation_ui.py
git commit -m "界面：展示参数来源与最终生效值"
```

## 任务三：浏览器验收和文档同步

- [ ] **步骤 1：真实浏览器验证**

打开看板，点击任务的“参数”，确认能看到 `24度 -> 20度`、L2 的 `2档` 和步骤 2 空字符串继承；再创建第二个任务，确认面板可以切换查看。

- [ ] **步骤 2：运行完整测试**

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -q
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
node --check app/static/app.js
```

- [ ] **步骤 3：同步交付文档**

README 增加参数面板说明；测试证据记录真实浏览器结果；源码详细说明增加新响应字段和前端渲染函数，但不将源码详细说明加入 Git。

- [ ] **步骤 4：中文提交并推送**

```powershell
git add README.md docs/test-evidence.md
git commit -m "文档：补充参数面板演示说明"
git push origin feature/任务调度系统
```
