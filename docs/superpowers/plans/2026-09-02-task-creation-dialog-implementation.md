# 新建任务弹窗与演示任务重置实施计划

> **执行要求：** 按任务顺序逐项完成。每个行为先写失败测试、确认失败原因，再写最小实现；每个里程碑使用中文提交信息。源码详细说明文档 `docs/代码详细说明.md` 只保存在本地，不加入 Git。

**目标：** 在现有任务调度看板中增加真正的新建任务弹窗，并把演示任务按钮改为可重复重置的操作。

**架构：** 复用已有 `POST /api/tasks` 创建接口，前端弹窗只负责把表单转换成已存在的请求结构；后端 `POST /api/demo/seed` 改为删除旧演示任务并在同一事务中重新创建。前端使用原生 HTML/JavaScript，不引入新框架。

**技术栈：** FastAPI、SQLAlchemy 2.x、MySQL 8 InnoDB、pytest、原生 HTML/CSS/JavaScript、agent-browser 浏览器验收。

---

## 文件规划

- 修改：`app/api/routes.py`：将演示接口改为事务内重置，并保留真实创建接口。
- 修改：`app/static/index.html`：增加新建任务弹窗、步骤编辑器和重置按钮文案。
- 修改：`app/static/styles.css`：增加弹窗、表单、步骤编辑布局。
- 修改：`app/static/app.js`：增加弹窗开关、动态步骤、JSON 校验、创建任务和重置操作。
- 修改：`tests/integration/test_dashboard.py`：验证演示重置和页面静态契约。
- 新建：`tests/integration/test_task_creation_ui.py`：验证前端创建接口所需的静态元素和脚本契约。
- 修改：`docs/test-evidence.md`：记录新的浏览器演示流程和测试数量。
- 修改：`docs/代码详细说明.md`：只在本地同步源码解读，不提交。

## 任务一：演示任务重置后端

**文件：**
- 修改：`app/api/routes.py`
- 修改：`tests/integration/test_dashboard.py`

- [ ] **步骤 1：先写重置行为失败测试**

在测试库中通过接口创建演示任务，完成三个步骤使其成为 `done`，再次调用 `POST /api/demo/seed`，断言：

```python
assert reset.status_code == 201
assert reset.json()["id"] != first.json()["id"]
assert reset.json()["status"] == "pending"
assert reset.json()["current_step_index"] == 0
assert reset.json()["log_count"] == 0
```

同时查询任务列表，确认只有一个名称为“看板演示任务”的任务。

- [ ] **步骤 2：运行测试确认当前复用逻辑失败**

运行：

```powershell
.\.venv\Scripts\pytest tests/integration/test_dashboard.py::test_seed_endpoint_resets_completed_demo_task -v
```

预期：FAIL，因为当前接口会返回已有任务、状态为 `200`，不会创建新任务。

- [ ] **步骤 3：实现事务内重置**

修改 `seed_demo_endpoint`：

1. 在同一个 Session 事务中按固定名称查询旧演示任务。
2. 删除旧任务；利用任务关系的级联删除步骤和日志。
3. 如果旧演示任务所属组没有其他任务，删除旧组。
4. 创建新的演示组、任务和三个步骤。
5. 提交事务后返回新的任务对象和 HTTP `201`。

删除和创建不能分成两个独立提交，避免中间只剩空数据。

- [ ] **步骤 4：运行重置测试和现有看板测试**

运行：

```powershell
.\.venv\Scripts\pytest tests/integration/test_dashboard.py -v
```

预期：重置测试和现有页面测试全部通过。

- [ ] **步骤 5：中文提交**

```powershell
git add app/api/routes.py tests/integration/test_dashboard.py
git commit -m "功能：支持演示任务事务重置"
```

## 任务二：新建任务弹窗静态契约

**文件：**
- 新建：`tests/integration/test_task_creation_ui.py`
- 修改：`app/static/index.html`

- [ ] **步骤 1：先写页面契约失败测试**

通过 FastAPI `TestClient` 请求根页面和 JavaScript，断言页面必须包含：

```python
assert "新建任务" in page.text
assert "重置演示任务" in page.text
assert 'id="task-dialog"' in page.text
assert 'id="task-form"' in page.text
assert 'id="add-step-button"' in page.text
assert "POST /api/tasks"  # 在脚本内容或等价创建逻辑中验证
```

脚本契约同时检查 `task-form`、`steps-container`、`base-parameters`、`group-overrides` 和 `create-task-button` 等稳定 ID。

- [ ] **步骤 2：运行测试确认当前页面缺少弹窗**

运行：`.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v`

预期：FAIL，因为现有页面没有新建任务表单。

- [ ] **步骤 3：在页面中增加弹窗结构**

在 `index.html` 中增加：

- 顶部“新建任务”按钮。
- 原演示按钮改名为“重置演示任务”。
- `dialog` 或等价模态容器。
- 任务组名称输入框。
- 任务名称输入框。
- L1 基础参数 JSON 文本框。
- L2 组级覆盖 JSON 文本框。
- 默认两个步骤，每步包含名称和 L3 JSON 文本框。
- 添加步骤、取消和创建按钮。
- 弹窗内错误提示区域。

每个控件使用稳定 ID，方便浏览器演示和自动化测试。

- [ ] **步骤 4：运行静态契约测试**

运行：`.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v`

预期：页面结构测试通过。

- [ ] **步骤 5：中文提交**

```powershell
git add app/static/index.html tests/integration/test_task_creation_ui.py
git commit -m "界面：增加新建任务弹窗结构"
```

## 任务三：弹窗样式与表单逻辑

**文件：**
- 修改：`app/static/styles.css`
- 修改：`app/static/app.js`
- 修改：`tests/integration/test_task_creation_ui.py`

- [ ] **步骤 1：补充失败的 JavaScript 契约测试**

检查 JavaScript 源码包含以下行为对应的稳定函数或标识：

```python
assert "task-dialog" in script.text
assert "steps-container" in script.text
assert "JSON.parse" in script.text
assert "/api/tasks" in script.text
assert "Promise.allSettled" in script.text or "add-step-button" in script.text
```

页面交互通过浏览器实测验证，不把纯字符串检查当作最终行为证明。

- [ ] **步骤 2：运行测试确认脚本行为尚不存在**

运行：`.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v`

预期：FAIL，因为现有脚本没有弹窗、动态步骤和任务创建逻辑。

- [ ] **步骤 3：实现 CSS 弹窗和步骤编辑布局**

弹窗使用固定最大宽度、内部滚动和响应式布局。表单在桌面端双列排列参数区域，在窄屏端改为单列。步骤行保持稳定间距，删除按钮不能让最后一个步骤被删光。

- [ ] **步骤 4：实现弹窗开关和动态步骤**

在 `app.js` 中实现：

- 打开、关闭和 Escape 关闭弹窗。
- 点击遮罩关闭弹窗。
- 添加步骤。
- 删除步骤，但至少保留一个步骤。
- 打开时重置为两个默认步骤。

- [ ] **步骤 5：实现 JSON 解析和请求组装**

提交时：

1. 读取任务组名和任务名。
2. 空 JSON 文本按 `{}` 处理。
3. 用 `JSON.parse` 解析 L1、L2 和每个 L3。
4. 要求解析结果是普通对象，数组、字符串和数字都视为非法。
5. 至少保留一个步骤，并检查步骤名非空。
6. 组装成现有 `POST /api/tasks` 请求结构。
7. 提交期间禁用创建按钮。
8. 成功后关闭弹窗、清空表单、刷新列表并提示新任务 ID。
9. 失败时保留输入并展示中文错误。

- [ ] **步骤 6：把演示按钮改成重置动作**

前端点击“重置演示任务”时调用 `POST /api/demo/seed`，成功后刷新列表并提示任务已重置。

- [ ] **步骤 7：运行静态检查和页面测试**

运行：

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest tests/integration/test_task_creation_ui.py -v
node --check app/static/app.js
```

预期：Ruff、页面契约测试和 JavaScript 语法检查通过。

- [ ] **步骤 8：中文提交**

```powershell
git add app/static/styles.css app/static/app.js tests/integration/test_task_creation_ui.py
git commit -m "界面：完成新建任务弹窗交互与参数校验"
```

## 任务四：浏览器端到端验收

**文件：**
- 修改：`docs/test-evidence.md`
- 修改：`docs/代码详细说明.md`（本地，不提交）

- [ ] **步骤 1：启动服务并清空运行库演示数据**

确保服务运行在 `http://127.0.0.1:8000`，运行库中没有旧演示任务。

- [ ] **步骤 2：浏览器创建第一个自定义任务**

在弹窗输入：

```text
任务组：华东客户组
任务名：新品通知任务
L1：{"tone":"formal","retry":1}
L2：{"channel":"email"}
步骤 1：准备消息，{"tone":"friendly"}
步骤 2：发送消息，{"tone":"","retry":3}
```

提交后确认任务列表出现 `pending` 任务。

- [ ] **步骤 3：创建第二个不同任务**

使用不同组名和任务名再次提交，确认列表同时出现两个任务，证明前端已经可以创建多个任务。

- [ ] **步骤 4：验证非法 JSON 被前端拦截**

在任意 JSON 输入框填入 `{bad`，点击创建，确认没有新增任务且弹窗内显示错误。

- [ ] **步骤 5：验证演示任务重置**

让演示任务进入 `done`，点击“重置演示任务”，确认它变成新的 `pending` 任务，日志数为 0。

- [ ] **步骤 6：记录证据并更新本地说明**

把浏览器操作结果、截图路径和最新测试数写入 `docs/test-evidence.md`。在未提交的 `docs/代码详细说明.md` 中同步新增接口和前端函数说明。

- [ ] **步骤 7：运行最终验证**

```powershell
.\.venv\Scripts\ruff check app tests scripts
.\.venv\Scripts\pytest -q
.\.venv\Scripts\python scripts/run_claim_evidence.py --tasks 100 --workers 10 --runs 10
.\.venv\Scripts\python scripts/run_completion_evidence.py
node --check app/static/app.js
```

预期：所有测试通过，认领重复和遗漏均为 0，完成证据最终状态为 `done`。

- [ ] **步骤 8：中文提交并推送**

```powershell
git add docs/test-evidence.md
git commit -m "测试：记录新建任务与演示重置验收"
git push origin feature/任务调度系统
```

本地源码解读文档不加入 `git add`。
