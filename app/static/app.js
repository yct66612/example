const state = { tasks: [], selectedTaskId: null };
const statuses = ["pending", "claimed", "running", "done", "failed"];
const $ = (selector) => document.querySelector(selector);
const taskDialog = $("#task-dialog");
const workerId = () => $("#worker-id").value.trim() || "dashboard-worker";

function showResult(message, error = false) {
  const element = $("#operation-result");
  element.textContent = message;
  element.classList.toggle("error", error);
}

function renderSummary() {
  const counts = Object.fromEntries(statuses.map((status) => [status, 0]));
  state.tasks.forEach((task) => { counts[task.status] += 1; });
  $("#status-summary").innerHTML = statuses.map((status) => `
    <div class="summary-item ${status}">
      <strong>${counts[status]}</strong>
      <span>${status}</span>
    </div>
  `).join("");
}

function actionButtons(task) {
  const buttons = [
    `<button type="button" data-action="parameters" data-id="${task.id}">参数</button>`,
  ];
  if (task.status === "claimed" && task.worker_id === workerId()) {
    buttons.push(`<button type="button" data-action="start" data-id="${task.id}">启动</button>`);
  }
  if (task.status === "running" && task.worker_id === workerId()) {
    buttons.push(`<button type="button" data-action="complete-five" data-id="${task.id}">并发完成 x5</button>`);
  }
  return buttons.join("");
}

function renderTasks() {
  const body = $("#task-table-body");
  if (!state.tasks.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-state">暂无任务，请创建演示任务。</td></tr>';
    return;
  }
  body.innerHTML = state.tasks.map((task) => {
    const step = task.steps[task.current_step_index];
    return `<tr>
      <td><div class="task-name">${escapeHtml(task.name)}</div><div class="task-meta">#${task.id} · ${escapeHtml(task.group_name)}</div></td>
      <td><span class="status status-${task.status}">${task.status}</span></td>
      <td>${step ? `${task.current_step_index + 1}. ${escapeHtml(step.name)}` : "已完成"}</td>
      <td>${escapeHtml(task.worker_id || "-")}</td>
      <td>${task.log_count}</td>
      <td><div class="row-actions">${actionButtons(task)}</div></td>
    </tr>`;
  }).join("");
}

function renderParameters(taskId, snapshots) {
  state.selectedTaskId = taskId;
  const task = state.tasks.find((item) => item.id === taskId);
  $("#selected-task").textContent = task ? `任务 #${task.id} · ${task.name}` : `任务 #${taskId}`;
  $("#parameter-detail").classList.remove("empty-state");
  $("#parameter-detail").innerHTML = `<div class="parameter-list">${snapshots.map((snapshot, index) => `
    <div class="parameter-step"><strong>步骤 ${index + 1}</strong><pre>${escapeHtml(JSON.stringify(snapshot, null, 2))}</pre></div>
  `).join("")}</div>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
}

function setTaskFormError(message = "") {
  $("#task-form-error").textContent = message;
}

function createStepEditor(index, name = `步骤 ${index + 1}`, overrides = "{}") {
  const editor = document.createElement("div");
  editor.className = "step-editor";
  editor.innerHTML = `
    <div class="step-editor-header">
      <span class="step-number">步骤 ${index + 1}</span>
      <button class="remove-step-button" type="button">删除步骤</button>
    </div>
    <div class="step-fields">
      <label>步骤名称<input class="step-name" maxlength="150" value="${escapeHtml(name)}" required></label>
      <label>L3 步骤覆盖 JSON<textarea class="step-overrides" rows="3" spellcheck="false">${escapeHtml(overrides)}</textarea></label>
    </div>
  `;
  editor.querySelector(".remove-step-button").addEventListener("click", () => {
    const editors = document.querySelectorAll(".step-editor");
    if (editors.length <= 1) {
      setTaskFormError("至少需要保留一个步骤");
      return;
    }
    editor.remove();
    renumberStepEditors();
    setTaskFormError();
  });
  return editor;
}

function renumberStepEditors() {
  document.querySelectorAll(".step-editor").forEach((editor, index) => {
    editor.querySelector(".step-number").textContent = `步骤 ${index + 1}`;
  });
}

function resetTaskForm() {
  $("#group-name").value = "新客户组";
  $("#task-name").value = "新任务";
  $("#base-parameters").value = "{}";
  $("#group-overrides").value = "{}";
  $("#steps-container").replaceChildren(
    createStepEditor(0, "准备步骤", "{}"),
    createStepEditor(1, "执行步骤", "{}"),
  );
  setTaskFormError();
}

function openTaskDialog() {
  resetTaskForm();
  taskDialog.showModal();
  $("#group-name").focus();
}

function closeTaskDialog() {
  taskDialog.close();
  setTaskFormError();
}

function parseObjectJson(value, label) {
  const source = value.trim() || "{}";
  let parsed;
  try {
    parsed = JSON.parse(source);
  } catch {
    throw new Error(`${label}必须是合法 JSON`);
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label}必须是 JSON 对象`);
  }
  return parsed;
}

function collectTaskPayload() {
  const groupName = $("#group-name").value.trim();
  const taskName = $("#task-name").value.trim();
  if (!groupName) throw new Error("任务组名称不能为空");
  if (!taskName) throw new Error("任务名称不能为空");
  const editors = [...document.querySelectorAll(".step-editor")];
  if (!editors.length) throw new Error("至少需要一个步骤");
  return {
    group_name: groupName,
    group_overrides: parseObjectJson($("#group-overrides").value, "L2 组级覆盖"),
    name: taskName,
    base_parameters: parseObjectJson($("#base-parameters").value, "L1 基础参数"),
    steps: editors.map((editor, index) => {
      const name = editor.querySelector(".step-name").value.trim();
      if (!name) throw new Error(`步骤 ${index + 1} 名称不能为空`);
      return {
        name,
        overrides: parseObjectJson(editor.querySelector(".step-overrides").value, `步骤 ${index + 1} 的 L3 覆盖`),
      };
    }),
  };
}

async function loadTasks() {
  const response = await fetch("/api/tasks");
  if (!response.ok) throw new Error("任务列表加载失败");
  state.tasks = await response.json();
  renderSummary();
  renderTasks();
  $("#last-updated").textContent = `最近刷新：${new Date().toLocaleTimeString()}`;
}

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok && response.status !== 204) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `请求失败（${response.status}）`);
  }
  return response.status === 204 ? null : response.json();
}

async function runAction(action, taskId) {
  try {
    if (action === "parameters") {
      const data = await request(`/api/tasks/${taskId}/parameters`);
      renderParameters(taskId, data.snapshots);
      return;
    }
    if (action === "start") {
      await request(`/api/tasks/${taskId}/start?worker_id=${encodeURIComponent(workerId())}`, { method: "POST" });
      showResult(`任务 #${taskId} 已启动`);
    }
    if (action === "complete-five") {
      const task = state.tasks.find((item) => item.id === taskId);
      const stepIndex = task.current_step_index;
      const payload = JSON.stringify({ worker_id: workerId(), success: true });
      const results = await Promise.allSettled(Array.from({ length: 5 }, () => request(
        `/api/tasks/${taskId}/steps/${stepIndex}/complete`, { method: "POST", body: payload },
      )));
      const succeeded = results.filter((result) => result.status === "fulfilled").length;
      showResult(`已发送 5 次，成功响应 ${succeeded} 次`);
    }
    await loadTasks();
  } catch (error) {
    showResult(error.message, true);
  }
}

$("#task-table-body").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (button) runAction(button.dataset.action, Number(button.dataset.id));
});
$("#refresh-button").addEventListener("click", () => loadTasks().catch((error) => showResult(error.message, true)));
$("#open-task-dialog").addEventListener("click", openTaskDialog);
$("#close-task-dialog").addEventListener("click", closeTaskDialog);
$("#cancel-task-dialog").addEventListener("click", closeTaskDialog);
taskDialog.addEventListener("click", (event) => {
  if (event.target === taskDialog) closeTaskDialog();
});
taskDialog.addEventListener("cancel", () => setTaskFormError());
$("#add-step-button").addEventListener("click", () => {
  const container = $("#steps-container");
  container.appendChild(createStepEditor(container.children.length));
  renumberStepEditors();
});
$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#create-task-button");
  button.disabled = true;
  setTaskFormError();
  try {
    const task = await request("/api/tasks", { method: "POST", body: JSON.stringify(collectTaskPayload()) });
    closeTaskDialog();
    showResult(`已创建任务 #${task.id}`);
    await loadTasks();
  } catch (error) {
    setTaskFormError(error.message);
  } finally {
    button.disabled = false;
  }
});
$("#reset-demo-button").addEventListener("click", async () => {
  try { await request("/api/demo/seed", { method: "POST" }); showResult("演示任务已重置"); await loadTasks(); }
  catch (error) { showResult(error.message, true); }
});
$("#claim-button").addEventListener("click", async () => {
  try {
    const task = await request("/api/tasks/claim", { method: "POST", body: JSON.stringify({ worker_id: workerId() }) });
    showResult(task ? `已认领任务 #${task.id}` : "暂无可认领任务");
    await loadTasks();
  } catch (error) { showResult(error.message, true); }
});

loadTasks().catch((error) => showResult(error.message, true));
setInterval(() => loadTasks().catch((error) => showResult(error.message, true)), 1000);
