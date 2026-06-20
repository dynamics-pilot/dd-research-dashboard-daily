(function () {
  "use strict";

  const STATUSES = ["pending", "running", "blocked", "done", "failed"];
  const STATUS_LABELS = {
    pending: "Pending",
    running: "Running",
    blocked: "Blocked",
    done: "Done",
    failed: "Failed",
  };
  const PRIORITY_LABELS = {
    high: "High",
    medium: "Medium",
    low: "Low",
  };
  const REFRESH_MS = 5000;
  const TOKEN_KEY = "research-dashboard-agent-token";
  const isHttp = location.protocol === "http:" || location.protocol === "https:";

  const state = {
    tasks: [],
    metrics: emptyMetrics(),
    serverOnline: false,
    tokenRequired: false,
    lastError: "",
    activeProject: "",
    activeProjectTitle: "",
  };

  function emptyMetrics() {
    const metrics = { total: 0 };
    STATUSES.forEach((status) => {
      metrics[status] = 0;
    });
    return metrics;
  }

  function htmlEscape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function shortText(value, limit) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (text.length <= limit) return text;
    return `${text.slice(0, limit - 1)}…`;
  }

  function readToken() {
    try {
      return sessionStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function writeToken(token) {
    try {
      if (token) {
        sessionStorage.setItem(TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch {
      // Session storage can be unavailable in hardened browser modes.
    }
  }

  function requestJson(url, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const token = readToken();
    if (token) headers["X-Dashboard-Agent-Token"] = token;
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    return fetch(url, Object.assign({}, options, { headers, cache: "no-store" })).then((response) => {
      if (response.status === 401) {
        state.tokenRequired = true;
        throw new Error("需要本次浏览器会话 token");
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    });
  }

  function loadJsonWithXhr(url) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.overrideMimeType("application/json");
      xhr.open("GET", url, true);
      xhr.onload = () => {
        if (xhr.status === 0 || (xhr.status >= 200 && xhr.status < 300)) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch (error) {
            reject(error);
          }
        } else {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error("XHR failed"));
      xhr.send();
    });
  }

  async function loadStaticTasks() {
    const url = `dashboard-data.json?t=${Date.now()}`;
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch {
      return loadJsonWithXhr(url);
    }
  }

  function normalizeMetrics(tasks, metrics) {
    const next = emptyMetrics();
    if (metrics && typeof metrics === "object") {
      STATUSES.forEach((status) => {
        next[status] = Number(metrics[status] || 0);
      });
      next.total = Number(metrics.total || tasks.length || 0);
      return next;
    }

    tasks.forEach((task) => {
      if (STATUSES.includes(task.status)) next[task.status] += 1;
    });
    next.total = tasks.length;
    return next;
  }

  function setTasks(tasks, metrics) {
    state.tasks = Array.isArray(tasks) ? tasks : [];
    state.metrics = normalizeMetrics(state.tasks, metrics);
    renderTaskConsole();
    renderProjectTasks();
  }

  async function refreshTasks() {
    if (isHttp) {
      try {
        const data = await requestJson(`/api/tasks?t=${Date.now()}`);
        state.serverOnline = true;
        state.tokenRequired = false;
        state.lastError = "";
        setTasks(data.tasks, data.metrics);
        return;
      } catch (error) {
        state.serverOnline = false;
        state.lastError = error.message || String(error);
      }
    }

    try {
      const data = await loadStaticTasks();
      setTasks(data.tasks, data.task_metrics);
    } catch (error) {
      state.lastError = error.message || String(error);
      setTasks([], null);
    }
  }

  function createStyle() {
    if (document.getElementById("dashboardTaskStyle")) return;
    const style = document.createElement("style");
    style.id = "dashboardTaskStyle";
    style.textContent = `
      .task-console {
        background: #ffffff;
        border: 1px solid var(--line, #d9ded7);
        border-radius: 8px;
        box-shadow: var(--shadow, 0 16px 44px rgba(37, 44, 51, 0.08));
        margin: 0 0 12px;
        padding: 10px 12px;
      }

      .task-console-head,
      .task-quickbar,
      .task-status-grid,
      .task-token-form,
      .task-form-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }

      .task-console-title {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin-right: auto;
      }

      .task-console-title strong {
        font-size: 0.98rem;
      }

      .task-service-state {
        color: var(--muted, #66717d);
        font-size: 0.82rem;
      }

      .task-service-state.online {
        color: var(--green, #2f7d57);
      }

      .task-service-state.offline {
        color: var(--muted, #66717d);
      }

      .task-token-form {
        width: 100%;
        margin-top: 8px;
      }

      .task-token-form[hidden],
      .task-modal-backdrop[hidden] {
        display: none;
      }

      .task-token-form input {
        flex: 1 1 240px;
        min-width: 180px;
      }

      .task-status-grid {
        margin-top: 8px;
      }

      .task-status-chip {
        border: 1px solid var(--line, #d9ded7);
        border-radius: 999px;
        background: #f7f9f5;
        color: var(--muted, #66717d);
        padding: 2px 8px;
        font-size: 0.78rem;
        font-weight: 700;
      }

      .task-status-chip strong {
        color: var(--text, #1c2228);
        margin-left: 4px;
      }

      .task-status-pending { border-color: #e1c36d; background: #fff8dd; }
      .task-status-running { border-color: #7fb0ce; background: #e8f3f8; }
      .task-status-blocked { border-color: #d8957c; background: #fff0e9; }
      .task-status-done { border-color: #91c7a6; background: #e9f6ef; }
      .task-status-failed { border-color: #d68b96; background: #fae8eb; }

      .task-global-list {
        display: grid;
        gap: 6px;
        margin-top: 10px;
      }

      .task-row {
        border: 1px solid var(--line, #d9ded7);
        border-radius: 7px;
        background: #fbfcfa;
        overflow: hidden;
      }

      .task-row summary {
        cursor: pointer;
        list-style: none;
        padding: 7px 9px;
      }

      .task-row summary::-webkit-details-marker {
        display: none;
      }

      .task-row-title {
        display: grid;
        grid-template-columns: auto auto minmax(0, 1fr) auto;
        gap: 7px;
        align-items: center;
        font-size: 0.86rem;
      }

      .task-row-title .title {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .task-priority {
        color: var(--muted, #66717d);
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
      }

      .task-time {
        color: var(--muted, #66717d);
        font-size: 0.76rem;
        white-space: nowrap;
      }

      .task-row-body {
        border-top: 1px solid var(--line, #d9ded7);
        padding: 8px 9px 10px;
        color: var(--text, #1c2228);
        font-size: 0.84rem;
      }

      .task-row-body p {
        margin: 0 0 7px;
      }

      .task-json-path {
        color: var(--muted, #66717d);
        font-size: 0.78rem;
        word-break: break-all;
      }

      .project-summary .task-quickbar {
        margin-top: 8px;
      }

      .task-card-count {
        color: var(--muted, #66717d);
        font-size: 0.82rem;
        margin-right: auto;
      }

      .task-create-button {
        min-height: 28px;
        padding: 3px 8px;
        border-color: #d3dbd4;
        background: #ffffff;
        color: #354250;
        font-size: 0.8rem;
        font-weight: 650;
      }

      .task-create-button:disabled {
        cursor: not-allowed;
        opacity: 0.48;
      }

      .project-task-panel {
        border-top: 1px solid var(--line, #d9ded7);
        margin-top: 10px;
        padding-top: 10px;
      }

      .project-task-panel h3 {
        margin: 0 0 7px;
        color: #27313a;
        font-size: 0.9rem;
        font-weight: 800;
      }

      .project-task-list {
        display: grid;
        gap: 6px;
      }

      .task-muted {
        color: var(--muted, #66717d);
        font-size: 0.84rem;
      }

      .task-modal-backdrop {
        position: fixed;
        inset: 0;
        z-index: 1000;
        display: grid;
        place-items: center;
        padding: 20px;
        background: rgba(20, 27, 34, 0.42);
      }

      .task-modal {
        width: min(720px, 100%);
        max-height: min(760px, calc(100vh - 40px));
        overflow: auto;
        background: #ffffff;
        border: 1px solid var(--line, #d9ded7);
        border-radius: 8px;
        box-shadow: 0 24px 70px rgba(20, 27, 34, 0.28);
      }

      .task-modal header {
        background: #ffffff;
        color: var(--text, #1c2228);
        border-bottom: 1px solid var(--line, #d9ded7);
        padding: 14px 16px;
      }

      .task-modal h2 {
        margin: 0;
        font-size: 1.08rem;
      }

      .task-modal form {
        padding: 14px 16px 16px;
        display: grid;
        gap: 10px;
      }

      .task-field {
        display: grid;
        gap: 4px;
      }

      .task-field label,
      .task-permissions legend {
        color: #27313a;
        font-size: 0.84rem;
        font-weight: 750;
      }

      .task-field input,
      .task-field select,
      .task-field textarea {
        width: 100%;
      }

      .task-field textarea {
        min-height: 116px;
        border: 1px solid var(--line, #d9ded7);
        border-radius: 7px;
        padding: 7px 9px;
        resize: vertical;
        font: inherit;
      }

      .task-field .short-textarea {
        min-height: 74px;
      }

      .task-permissions {
        border: 1px solid var(--line, #d9ded7);
        border-radius: 7px;
        padding: 9px;
      }

      .task-permission-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 7px 10px;
        margin-top: 7px;
      }

      .task-checkbox {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        color: var(--text, #1c2228);
        font-size: 0.84rem;
      }

      .task-checkbox input {
        margin-top: 0.22rem;
      }

      .task-form-message {
        color: var(--muted, #66717d);
        font-size: 0.84rem;
      }

      .task-form-message.error {
        color: var(--red, #b13d4b);
      }

      .task-form-actions {
        justify-content: flex-end;
      }

      @media (max-width: 760px) {
        .task-row-title {
          grid-template-columns: auto minmax(0, 1fr);
        }

        .task-time {
          grid-column: 2;
        }

        .task-permission-grid {
          grid-template-columns: 1fr;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createTaskConsole() {
    if (document.getElementById("taskConsole")) return;
    const metrics = document.querySelector(".metrics");
    if (!metrics || !metrics.parentNode) return;

    const section = document.createElement("section");
    section.className = "task-console";
    section.id = "taskConsole";
    section.setAttribute("aria-label", "remote task queue");
    section.innerHTML = `
      <div class="task-console-head">
        <div class="task-console-title">
          <strong>远程任务队列</strong>
          <span class="task-service-state offline" id="taskServiceState">静态模式：启动本地任务服务后可布置任务</span>
        </div>
        <button type="button" id="taskRefreshButton">刷新任务</button>
      </div>
      <form class="task-token-form" id="taskTokenForm" hidden>
        <input id="taskTokenInput" type="password" autocomplete="off" placeholder="输入本次会话 token">
        <button type="submit">连接</button>
      </form>
      <div class="task-status-grid" id="taskStatusGrid"></div>
      <div class="task-global-list" id="taskGlobalList"></div>
    `;
    metrics.insertAdjacentElement("afterend", section);

    document.getElementById("taskRefreshButton").addEventListener("click", refreshTasks);
    document.getElementById("taskTokenForm").addEventListener("submit", (event) => {
      event.preventDefault();
      writeToken(document.getElementById("taskTokenInput").value.trim());
      state.tokenRequired = false;
      refreshTasks();
    });
  }

  function createTaskModal() {
    if (document.getElementById("taskModalBackdrop")) return;
    const modal = document.createElement("div");
    modal.className = "task-modal-backdrop";
    modal.id = "taskModalBackdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="task-modal" role="dialog" aria-modal="true" aria-labelledby="taskModalTitle">
        <header>
          <h2 id="taskModalTitle">布置任务</h2>
        </header>
        <form id="taskCreateForm">
          <input type="hidden" name="project">
          <div class="task-field">
            <label for="taskTitleInput">任务标题</label>
            <input id="taskTitleInput" name="title" type="text" maxlength="120" required>
          </div>
          <div class="task-field">
            <label for="taskInstructionInput">详细说明</label>
            <textarea id="taskInstructionInput" name="instruction" required></textarea>
          </div>
          <div class="task-field">
            <label for="taskPriorityInput">优先级</label>
            <select id="taskPriorityInput" name="priority">
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div class="task-field">
            <label for="taskExpectedInput">期望输出</label>
            <textarea id="taskExpectedInput" class="short-textarea" name="expected_output">更新对应项目 Markdown，并在任务 JSON 中写 result_summary。</textarea>
          </div>
          <fieldset class="task-permissions">
            <legend>权限选项</legend>
            <div class="task-permission-grid">
              <label class="task-checkbox"><input type="checkbox" name="allow_code_edit" checked>允许修改项目文件或代码</label>
              <label class="task-checkbox"><input type="checkbox" name="allow_shell" checked>允许运行本地命令</label>
              <label class="task-checkbox"><input type="checkbox" name="allow_network">允许联网检索</label>
              <label class="task-checkbox"><input type="checkbox" name="allow_long_running">允许长时间运行</label>
              <label class="task-checkbox"><input type="checkbox" name="allow_delete_files">允许删除单个文件</label>
              <label class="task-checkbox"><input type="checkbox" name="requires_confirmation">需要人工确认后执行</label>
            </div>
          </fieldset>
          <p class="task-form-message" id="taskFormMessage"></p>
          <div class="task-form-actions">
            <button type="button" id="taskCancelButton">取消</button>
            <button type="submit" id="taskSubmitButton">提交任务</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);

    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeTaskDialog();
    });
    document.getElementById("taskCancelButton").addEventListener("click", closeTaskDialog);
    document.getElementById("taskCreateForm").addEventListener("submit", submitTaskForm);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) closeTaskDialog();
    });
  }

  function serviceLabel() {
    if (state.serverOnline) return "本地任务服务已连接，可从网页写入任务队列";
    if (state.tokenRequired) return "服务需要本次会话 token";
    if (isHttp && state.lastError) return `未连接任务服务：${state.lastError}`;
    return "静态模式：启动本地任务服务后可布置任务";
  }

  function renderTaskConsole() {
    const service = document.getElementById("taskServiceState");
    const tokenForm = document.getElementById("taskTokenForm");
    const statusGrid = document.getElementById("taskStatusGrid");
    const list = document.getElementById("taskGlobalList");
    if (!service || !statusGrid || !list) return;

    service.textContent = serviceLabel();
    service.classList.toggle("online", state.serverOnline);
    service.classList.toggle("offline", !state.serverOnline);
    tokenForm.hidden = !state.tokenRequired;

    statusGrid.innerHTML = STATUSES.map((status) => {
      const count = state.metrics[status] || 0;
      return `<span class="task-status-chip task-status-${status}">${STATUS_LABELS[status]} <strong>${count}</strong></span>`;
    }).join("");

    const latest = state.tasks.slice(0, 6);
    list.innerHTML = latest.length
      ? latest.map((task) => taskRowHtml(task, true)).join("")
      : '<p class="task-muted">暂无任务队列记录。</p>';
  }

  function taskRowHtml(task, includeProject) {
    const status = STATUSES.includes(task.status) ? task.status : "pending";
    const title = htmlEscape(task.title || "未命名任务");
    const priority = htmlEscape(PRIORITY_LABELS[task.priority] || task.priority || "Medium");
    const updated = htmlEscape(task.updated_at || task.created_at || "");
    const project = includeProject ? `<span class="task-priority">${htmlEscape(task.project || "no-project")}</span>` : "";
    const instruction = htmlEscape(task.instruction || "无详细说明");
    const expected = htmlEscape(task.expected_output || "未设置期望输出");
    const result = task.result_summary ? `<p><strong>结果：</strong>${htmlEscape(task.result_summary)}</p>` : "";
    const error = task.error_summary ? `<p><strong>错误：</strong>${htmlEscape(task.error_summary)}</p>` : "";
    const path = task.path ? `<p class="task-json-path">JSON: ${htmlEscape(task.path)}</p>` : "";
    const log = task.log_path ? `<p class="task-json-path">Log: ${htmlEscape(task.log_path)}</p>` : "";

    return `
      <details class="task-row">
        <summary>
          <span class="task-row-title">
            <span class="task-status-chip task-status-${status}">${STATUS_LABELS[status]}</span>
            <span class="task-priority">${priority}</span>
            <span class="title" title="${title}">${title}</span>
            <span class="task-time">${updated}</span>
            ${project}
          </span>
        </summary>
        <div class="task-row-body">
          <p><strong>指令：</strong>${instruction}</p>
          <p><strong>期望输出：</strong>${expected}</p>
          ${result}
          ${error}
          ${path}
          ${log}
        </div>
      </details>
    `;
  }

  function groupTasksByProject() {
    const byProject = new Map();
    state.tasks.forEach((task) => {
      const project = task.project || "";
      if (!byProject.has(project)) byProject.set(project, []);
      byProject.get(project).push(task);
    });
    return byProject;
  }

  function ensureProjectControls(card) {
    if (!card || !card.dataset || !card.dataset.slug) return;
    const summary = card.querySelector(".project-summary");
    const body = card.querySelector(".project-body");
    if (!summary || !body) return;

    if (!summary.querySelector(".task-quickbar")) {
      const quickbar = document.createElement("div");
      quickbar.className = "task-quickbar";
      quickbar.innerHTML = `
        <span class="task-card-count">任务队列: 0</span>
        <button class="task-create-button" type="button">布置任务</button>
      `;
      const button = quickbar.querySelector("button");
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!state.serverOnline) return;
        const titleNode = card.querySelector("h2");
        openTaskDialog(card.dataset.slug, titleNode ? titleNode.textContent.trim() : card.dataset.slug);
      });
      summary.appendChild(quickbar);
    }

    if (!body.querySelector(".project-task-panel")) {
      const panel = document.createElement("section");
      panel.className = "project-task-panel";
      panel.innerHTML = `
        <h3>任务队列</h3>
        <div class="project-task-list"></div>
      `;
      const source = body.querySelector(".source");
      if (source) {
        body.insertBefore(panel, source);
      } else {
        body.appendChild(panel);
      }
    }
  }

  function wireProjectCards() {
    document.querySelectorAll(".project-card").forEach(ensureProjectControls);
    renderProjectTasks();
  }

  function renderProjectTasks() {
    const byProject = groupTasksByProject();
    document.querySelectorAll(".project-card").forEach((card) => {
      ensureProjectControls(card);
      const slug = card.dataset.slug;
      const tasks = byProject.get(slug) || [];
      const activeTasks = tasks.filter((task) => task.status !== "done");
      const count = card.querySelector(".task-card-count");
      const button = card.querySelector(".task-create-button");
      const list = card.querySelector(".project-task-list");

      if (count) {
        const pending = tasks.filter((task) => task.status === "pending").length;
        const running = tasks.filter((task) => task.status === "running").length;
        const blocked = tasks.filter((task) => task.status === "blocked").length;
        const parts = [`${tasks.length} 条`];
        if (pending) parts.push(`${pending} pending`);
        if (running) parts.push(`${running} running`);
        if (blocked) parts.push(`${blocked} blocked`);
        count.textContent = `任务队列: ${parts.join(" / ")}`;
      }

      if (button) {
        button.disabled = !state.serverOnline;
        button.title = state.serverOnline ? "给这个研究项目写入一条新任务" : "启动本地任务服务后可提交任务";
      }

      if (list) {
        const displayTasks = activeTasks.length ? activeTasks : tasks.slice(0, 3);
        list.innerHTML = displayTasks.length
          ? displayTasks.slice(0, 5).map((task) => taskRowHtml(task, false)).join("")
          : '<p class="task-muted">暂无关联任务。</p>';
      }
    });
  }

  function openTaskDialog(project, projectTitle) {
    state.activeProject = project;
    state.activeProjectTitle = projectTitle;
    const modal = document.getElementById("taskModalBackdrop");
    const form = document.getElementById("taskCreateForm");
    const message = document.getElementById("taskFormMessage");
    if (!modal || !form) return;

    form.reset();
    form.elements.project.value = project;
    form.elements.title.value = `${projectTitle} - 新任务`;
    form.elements.expected_output.value = "更新对应项目 Markdown，并在任务 JSON 中写 result_summary。";
    form.elements.allow_code_edit.checked = true;
    form.elements.allow_shell.checked = true;
    form.elements.allow_network.checked = false;
    form.elements.allow_long_running.checked = false;
    form.elements.allow_delete_files.checked = false;
    form.elements.requires_confirmation.checked = false;
    message.textContent = state.serverOnline ? "" : "本地任务服务未连接，暂不能提交任务。";
    message.classList.toggle("error", !state.serverOnline);
    modal.hidden = false;
    form.elements.title.focus();
  }

  function closeTaskDialog() {
    const modal = document.getElementById("taskModalBackdrop");
    if (modal) modal.hidden = true;
  }

  async function submitTaskForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = document.getElementById("taskFormMessage");
    const submit = document.getElementById("taskSubmitButton");
    if (!state.serverOnline) {
      message.textContent = "本地任务服务未连接，无法写入任务队列。";
      message.classList.add("error");
      return;
    }

    const permissions = {
      allow_code_edit: Boolean(form.elements.allow_code_edit.checked),
      allow_shell: Boolean(form.elements.allow_shell.checked),
      allow_network: Boolean(form.elements.allow_network.checked),
      allow_long_running: Boolean(form.elements.allow_long_running.checked),
      allow_delete_files: Boolean(form.elements.allow_delete_files.checked),
    };

    const payload = {
      project: form.elements.project.value,
      title: form.elements.title.value.trim(),
      instruction: form.elements.instruction.value.trim(),
      priority: form.elements.priority.value,
      expected_output: form.elements.expected_output.value.trim(),
      permissions,
      requires_confirmation: Boolean(form.elements.requires_confirmation.checked),
    };

    if (!payload.instruction) {
      message.textContent = "请填写详细说明。";
      message.classList.add("error");
      return;
    }

    submit.disabled = true;
    message.textContent = "正在写入任务队列...";
    message.classList.remove("error");

    try {
      const data = await requestJson("/api/tasks", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.serverOnline = true;
      state.lastError = "";
      setTasks(data.tasks, data.metrics);
      closeTaskDialog();
    } catch (error) {
      message.textContent = `提交失败：${error.message || error}`;
      message.classList.add("error");
      renderTaskConsole();
    } finally {
      submit.disabled = false;
    }
  }

  function observeProjectGrid() {
    const grid = document.getElementById("projectGrid");
    if (!grid) return;
    const observer = new MutationObserver(() => {
      wireProjectCards();
    });
    observer.observe(grid, { childList: true });
  }

  function init() {
    createStyle();
    createTaskConsole();
    createTaskModal();
    wireProjectCards();
    observeProjectGrid();
    refreshTasks();
    window.setInterval(refreshTasks, REFRESH_MS);
  }

  init();
})();
