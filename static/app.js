const state = {
  answerMode: "polish",
  defaultAnswerMode: "fast",
  lastResponse: null,
  openaiConfigured: false,
  messages: [],
  dashboardSummary: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function setView(view) {
  $$(".view").forEach((item) => item.classList.remove("active"));
  $$(".nav-button").forEach((item) => item.classList.remove("active"));
  $(`#${view}-view`).classList.add("active");
  $(`[data-view="${view}"]`).classList.add("active");
}

function clearNode(node) {
  node.replaceChildren();
}

function appendText(parent, tagName, text, className = "") {
  const element = document.createElement(tagName);
  element.textContent = text;
  if (className) element.className = className;
  parent.appendChild(element);
  return element;
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  const placeholders = [];
  const store = (value) => `\u0000${placeholders.push(value) - 1}\u0000`;
  let html = escapeHtml(text);

  html = html.replace(/`([^`\n]+)`/g, (_, code) => store(`<code>${code}</code>`));
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, label, url) => store(
      `<a href="${url}" target="_blank" rel="noreferrer noopener">${label}</a>`,
    ),
  );
  html = html.replace(/\*\*([^\s*](?:[\s\S]*?[^\s*])?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^\s*](?:[\s\S]*?[^\s*])?)\*/g, "<em>$1</em>");
  html = html.replace(/~~([^\s~](?:[\s\S]*?[^\s~])?)~~/g, "<del>$1</del>");

  return html.replace(/\u0000(\d+)\u0000/g, (_, index) => placeholders[Number(index)]);
}

function isMarkdownBlockStart(line) {
  return (
    /^\s*```/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^\s*>\s?/.test(line) ||
    /^\s{0,3}#{1,6}\s+/.test(line)
  );
}

function consumeList(lines, startIndex, ordered) {
  const pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*+]\s+/;
  const tag = ordered ? "ol" : "ul";
  const items = [];
  let index = startIndex;

  while (index < lines.length && pattern.test(lines[index])) {
    const itemLines = [lines[index].replace(pattern, "").trim()];
    index += 1;

    while (
      index < lines.length &&
      lines[index].trim() &&
      !pattern.test(lines[index]) &&
      !isMarkdownBlockStart(lines[index])
    ) {
      itemLines.push(lines[index].trim());
      index += 1;
    }

    items.push(`<li>${renderInlineMarkdown(itemLines.join(" "))}</li>`);
  }

  return { html: `<${tag}>${items.join("")}</${tag}>`, nextIndex: index };
}

function markdownToHtml(source) {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (/^\s*```/.test(line)) {
      const language = line.trim().slice(3).trim();
      const codeLines = [];
      index += 1;

      while (index < lines.length && !/^\s*```/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) index += 1;

      const languageClass = language ? ` class="language-${escapeHtml(language)}"` : "";
      blocks.push(
        `<pre><code${languageClass}>${escapeHtml(codeLines.join("\n"))}</code></pre>`,
      );
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const list = consumeList(lines, index, false);
      blocks.push(list.html);
      index = list.nextIndex;
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const list = consumeList(lines, index, true);
      blocks.push(list.html);
      index = list.nextIndex;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quoteLines = [];

      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }

      blocks.push(`<blockquote>${markdownToHtml(quoteLines.join("\n"))}</blockquote>`);
      continue;
    }

    const headingMatch = line.match(/^\s{0,3}(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2].trim())}</h${level}>`);
      index += 1;
      continue;
    }

    const paragraphLines = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !isMarkdownBlockStart(lines[index])
    ) {
      paragraphLines.push(lines[index].trimEnd());
      index += 1;
    }

    blocks.push(`<p>${paragraphLines.map(renderInlineMarkdown).join("<br>")}</p>`);
  }

  return blocks.join("");
}

function renderMessageBody(parent, role, text) {
  const content = document.createElement("div");
  content.className = "message-content";

  if (role === "assistant") {
    content.innerHTML = markdownToHtml(text);
  } else {
    appendText(content, "p", text);
  }

  parent.appendChild(content);
}

function addMessage(role, text, track = true) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.dataset.rawContent = text;
  renderMessageBody(article, role, text);
  $("#messages").appendChild(article);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  if (track) {
    state.messages.push({ role, content: text });
  }
}

function visibleConversationHistory() {
  return $$("#messages .message")
    .map((item) => {
      const role = item.classList.contains("user") ? "user" : "assistant";
      return { role, content: item.dataset.rawContent ?? item.textContent.trim() };
    })
    .filter((item) => item.content);
}

function currentConversationHistory() {
  const visibleMessages = visibleConversationHistory();
  return visibleMessages.length > state.messages.length
    ? visibleMessages
    : state.messages.slice();
}

function modeLabel(mode) {
  if (mode === "chat") return "Chat";
  if (mode === "polish") return "Polish";
  return "Fast";
}

function setAnswerMode(mode) {
  state.answerMode = mode;
  $$(".mode-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.answerMode === mode);
  });
}

function renderRunSummary(result = null) {
  if (!result) {
    $("#run-mode").textContent = modeLabel(state.answerMode);
    $("#run-route").textContent = "Idle";
    $("#run-latency").textContent = "--";
    $("#run-confidence").textContent = "--";
    $("#run-openai").textContent = state.openaiConfigured ? "Ready" : "Off";
    $("#technical-summary").textContent = `Mode ${modeLabel(state.answerMode)}`;
    return;
  }

  $("#run-mode").textContent = modeLabel(result.answer_mode);
  $("#run-route").textContent = result.route;
  $("#run-latency").textContent = `${Math.round(result.latency_ms)} ms`;
  $("#run-confidence").textContent = `${Math.round(result.confidence * 100)}%`;
  $("#run-openai").textContent = result.used_openai ? "Used" : "Off";

  const parts = [
    result.route,
    result.sql ? `${result.sql.rows.length} rows` : "No SQL",
    `${result.citations.length} docs`,
    `${result.trace.length} steps`,
  ];
  $("#technical-summary").textContent = parts.join(" · ");
}

function renderSql(sql) {
  if (!sql) {
    $("#sql-count").textContent = "No query";
    $("#sql-preview").textContent = "No SQL was needed for this answer.";
    return;
  }
  $("#sql-count").textContent = `${sql.rows.length} rows`;
  $("#sql-preview").textContent = `${sql.query}\n\n${JSON.stringify(sql.rows, null, 2)}`;
}

function renderCitations(citations) {
  $("#citation-count").textContent = `${citations.length} docs`;
  const target = $("#citations");
  clearNode(target);
  if (!citations.length) {
    target.textContent = "No citations returned.";
    target.classList.add("muted");
    return;
  }
  target.classList.remove("muted");
  citations.forEach((citation) => {
    const item = document.createElement("article");
    item.className = "detail-item";
    appendText(item, "strong", citation.title);
    appendText(item, "p", citation.snippet);
    target.appendChild(item);
  });
}

function renderTrace(trace) {
  $("#trace-count").textContent = `${trace.length} steps`;
  const target = $("#trace");
  clearNode(target);
  if (!trace.length) {
    target.textContent = "Trace is disabled for this response.";
    target.classList.add("muted");
    return;
  }
  target.classList.remove("muted");
  trace.forEach((step) => {
    const item = document.createElement("article");
    item.className = "detail-item";
    const duration = step.duration_ms === null || step.duration_ms === undefined
      ? ""
      : ` (${step.duration_ms} ms)`;
    appendText(item, "strong", `${step.agent} - ${step.tool}${duration}`);
    appendText(item, "p", `${step.status}: ${step.output_preview}`);
    target.appendChild(item);
  });
}

function renderStats(stats) {
  const target = $("#stat-grid");
  clearNode(target);
  stats.forEach((stat) => {
    const item = document.createElement("article");
    item.className = `stat-item tone-${stat.tone ?? "steady"}`;
    appendText(item, "span", stat.label, "stat-label");
    appendText(item, "strong", stat.value, "stat-value");
    appendText(item, "p", stat.context, "stat-context");
    target.appendChild(item);
  });
}

function renderTrend(summary) {
  const trend = summary.trend ?? [];
  if (!trend.length) {
    $("#trend-chart").textContent = "Trend data unavailable.";
    $("#trend-period").textContent = "No data";
    $("#trend-caption").textContent = "Trend data unavailable.";
    $("#severity-caption").textContent = "";
    return;
  }

  const width = 420;
  const height = 220;
  const padding = 26;
  const bottomPad = 34;
  const chartHeight = height - padding - bottomPad;
  const step = trend.length > 1 ? (width - padding * 2) / (trend.length - 1) : 0;
  const backlogMax = Math.max(...trend.map((row) => row.total_backlog));
  const satValues = trend.map((row) => row.avg_satisfaction);
  const satMin = Math.min(...satValues) - 0.08;
  const satMax = Math.max(...satValues) + 0.08;

  const bars = trend.map((row, index) => {
    const x = padding + (index * step) - 16;
    const barHeight = (row.total_backlog / backlogMax) * (chartHeight - 8);
    const y = height - bottomPad - barHeight;
    return `
      <rect x="${x}" y="${y}" width="32" height="${barHeight}" rx="12"></rect>
      <text x="${padding + (index * step)}" y="${height - 10}" text-anchor="middle">${row.month.slice(5)}</text>
    `;
  }).join("");

  const linePoints = trend.map((row, index) => {
    const x = padding + (index * step);
    const ratio = (row.avg_satisfaction - satMin) / (satMax - satMin || 1);
    const y = height - bottomPad - (ratio * (chartHeight - 10));
    return `${x},${y}`;
  }).join(" ");

  const circles = trend.map((row, index) => {
    const x = padding + (index * step);
    const ratio = (row.avg_satisfaction - satMin) / (satMax - satMin || 1);
    const y = height - bottomPad - (ratio * (chartHeight - 10));
    return `<circle cx="${x}" cy="${y}" r="4.5"></circle>`;
  }).join("");

  $("#trend-chart").innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="trend-svg" aria-hidden="true">
      <g class="trend-grid">
        <line x1="${padding}" y1="${height - bottomPad}" x2="${width - padding}" y2="${height - bottomPad}"></line>
        <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}"></line>
      </g>
      <g class="trend-bars">${bars}</g>
      <polyline class="trend-line" points="${linePoints}"></polyline>
      <g class="trend-points">${circles}</g>
    </svg>
  `;

  const latest = trend[trend.length - 1];
  $("#trend-period").textContent = `${trend[0].month} - ${latest.month}`;
  $("#trend-caption").textContent = (
    `Backlog total ${latest.total_backlog} pada ${latest.month}, `
    + `kepuasan rata-rata ${latest.avg_satisfaction}.`
  );
  $("#severity-caption").textContent = (
    `${summary.high_severity_count} high severity complaints tercatat pada ${summary.snapshot_month}.`
  );
}

function renderHotspots(hotspots) {
  $("#hotspot-count").textContent = `${hotspots.length} hotspots`;
  const target = $("#hotspots");
  clearNode(target);
  if (!hotspots.length) {
    target.textContent = "No hotspots found.";
    target.classList.add("muted");
    return;
  }

  target.classList.remove("muted");
  hotspots.forEach((item) => {
    const article = document.createElement("article");
    article.className = "context-item";

    const head = document.createElement("div");
    head.className = "context-head";
    appendText(head, "strong", `${item.region} · ${item.service}`);
    appendText(head, "span", `Backlog ${item.backlog_count}`, "context-pill");
    article.appendChild(head);

    appendText(
      article,
      "p",
      `Avg resolution ${item.avg_resolution_days} hari, SLA ${item.sla_days} hari, `
      + `${item.high_severity_count} high severity complaints, satisfaction ${item.satisfaction_score}.`,
    );
    target.appendChild(article);
  });
}

function renderBudgetWatchlist(items) {
  $("#budget-count").textContent = `${items.length} items`;
  const target = $("#budget-watchlist");
  clearNode(target);
  if (!items.length) {
    target.textContent = "No budget watchlist items.";
    target.classList.add("muted");
    return;
  }

  target.classList.remove("muted");
  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "context-item";

    const head = document.createElement("div");
    head.className = "context-head";
    appendText(head, "strong", `${item.region} · ${item.service}`);
    appendText(head, "span", `${item.spend_pct}%`, "context-pill");
    article.appendChild(head);

    appendText(article, "p", `Program status ${item.program_status}. Realisasi belanja ${item.spend_pct}%.`);
    target.appendChild(article);
  });
}

function renderSuggestedQuestions(questions) {
  const target = $("#suggested-questions");
  clearNode(target);

  (questions ?? []).forEach((question) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "question-chip";
    button.textContent = question;
    button.addEventListener("click", () => {
      if ($("#send-button").disabled) return;
      submitQuestion(question);
    });
    target.appendChild(button);
  });
}

function renderDashboardSummary(summary) {
  state.dashboardSummary = summary;
  $("#snapshot-month-label").textContent = summary.snapshot_month;
  $("#summary-heading").textContent = `${summary.snapshot_month} operating picture`;

  const leadHotspot = summary.hotspots?.[0];
  $("#summary-note").textContent = leadHotspot
    ? `${leadHotspot.region} pada ${leadHotspot.service} saat ini menjadi tekanan utama dengan backlog ${leadHotspot.backlog_count}.`
    : "Operational summary loaded.";

  renderStats(summary.stats ?? []);
  renderTrend(summary);
  renderHotspots(summary.hotspots ?? []);
  renderBudgetWatchlist(summary.budget_watchlist ?? []);
  renderSuggestedQuestions(summary.suggested_questions ?? []);
}

function renderDatasetCatalog(data) {
  const target = $("#datasets-content");
  clearNode(target);

  const totalRows = Object.values(data.tables).reduce((sum, table) => sum + table.row_count, 0);

  const overview = document.createElement("section");
  overview.className = "catalog-overview";
  overview.innerHTML = `
    <article class="stat-item tone-steady">
      <span class="stat-label">Structured rows</span>
      <strong class="stat-value">${totalRows}</strong>
      <p class="stat-context">Across ${Object.keys(data.tables).length} tables.</p>
    </article>
    <article class="stat-item tone-watch">
      <span class="stat-label">Policy documents</span>
      <strong class="stat-value">${data.documents.length}</strong>
      <p class="stat-context">Governance, SLA, budget, and quality references.</p>
    </article>
  `;
  target.appendChild(overview);

  const sections = document.createElement("div");
  sections.className = "catalog-sections";
  target.appendChild(sections);

  const tablesSection = document.createElement("section");
  tablesSection.className = "catalog-column";
  tablesSection.innerHTML = `
    <div class="section-heading">
      <h3>Structured tables</h3>
      <span>${Object.keys(data.tables).length} sources</span>
    </div>
  `;
  sections.appendChild(tablesSection);

  Object.entries(data.tables).forEach(([name, table]) => {
    const item = document.createElement("article");
    item.className = "catalog-item";
    appendText(item, "strong", name);
    appendText(item, "p", `${table.row_count} rows`);
    appendText(item, "p", `Columns: ${table.columns.join(", ")}`);
    tablesSection.appendChild(item);
  });

  const docsSection = document.createElement("section");
  docsSection.className = "catalog-column";
  docsSection.innerHTML = `
    <div class="section-heading">
      <h3>Reference documents</h3>
      <span>${data.documents.length} docs</span>
    </div>
  `;
  sections.appendChild(docsSection);

  data.documents.forEach((doc) => {
    const item = document.createElement("article");
    item.className = "catalog-item";
    appendText(item, "strong", doc.title);
    appendText(item, "p", doc.source);
    appendText(item, "p", `${doc.size_bytes} bytes`);
    docsSection.appendChild(item);
  });
}

function renderEvalState(result = null) {
  if (!result) {
    $("#eval-pass-rate").textContent = "--";
    $("#eval-summary").textContent = "Run the suite to inspect routing, grounding, and guardrail coverage.";
    return;
  }

  $("#eval-pass-rate").textContent = `${Math.round(result.pass_rate * 100)}%`;
  $("#eval-summary").textContent = (
    `${result.passed}/${result.total} passed. `
    + `Target met: ${result.target_met ? "yes" : "no"}.`
  );
}

async function sendQuestion(question, conversationHistory = []) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      include_trace: true,
      answer_mode: state.answerMode,
      conversation_history: conversationHistory.slice(-12),
    }),
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  return response.json();
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    state.openaiConfigured = Boolean(health.openai_configured);
    state.defaultAnswerMode = health.default_answer_mode ?? (state.openaiConfigured ? "polish" : "fast");

    $("#status-dot").classList.add("ok");
    $("#health-text").textContent = state.openaiConfigured
      ? "Online with AI polish/chat"
      : "Online in fast local mode";
    $("#default-mode-text").textContent = modeLabel(state.defaultAnswerMode);

    $("#mode-chat").disabled = !state.openaiConfigured;
    $("#mode-polish").disabled = !state.openaiConfigured;
    $("#mode-chat").title = state.openaiConfigured
      ? "Use OpenAI for natural chatbot responses."
      : "Set OPENAI_API_KEY to enable chat mode.";
    $("#mode-polish").title = state.openaiConfigured
      ? "Default demo mode: keep grounded local evidence, then polish wording."
      : "Set OPENAI_API_KEY to enable polish mode.";

    setAnswerMode(state.defaultAnswerMode);
    renderRunSummary();
  } catch (error) {
    $("#health-text").textContent = "Service unavailable";
    $("#default-mode-text").textContent = "Unavailable";
  }
}

async function loadDashboardSummary() {
  try {
    const response = await fetch("/api/dashboard/summary");
    const summary = await response.json();
    renderDashboardSummary(summary);
  } catch (error) {
    $("#summary-heading").textContent = "Summary unavailable";
    $("#summary-note").textContent = "Dashboard summary could not be loaded.";
    $("#trend-chart").textContent = "Trend unavailable.";
  }
}

async function loadDatasets() {
  const target = $("#datasets-content");
  target.textContent = "Loading dataset metadata.";
  const response = await fetch("/api/datasets/preview");
  const data = await response.json();
  renderDatasetCatalog(data);
}

async function runEval() {
  $("#eval-summary").textContent = "Running golden-question suite.";
  $("#eval-results").textContent = "Please wait.";
  $("#eval-pass-rate").textContent = "...";
  const response = await fetch("/api/eval/run", { method: "POST" });
  const result = await response.json();
  renderEvalState(result);

  const target = $("#eval-results");
  clearNode(target);
  result.cases.forEach((testCase) => {
    const item = document.createElement("article");
    item.className = `eval-case ${testCase.passed ? "pass" : "fail"}`;
    appendText(item, "strong", `${testCase.id} · ${testCase.passed ? "PASS" : "FAIL"}`);
    appendText(item, "p", testCase.question);
    appendText(item, "p", testCase.answer_preview);
    target.appendChild(item);
  });
}

async function submitQuestion(question) {
  const input = $("#question-input");
  const conversationHistory = currentConversationHistory();
  addMessage("user", question);
  input.value = "";
  $("#send-button").disabled = true;
  $("#send-button").textContent = state.answerMode === "chat" ? "Thinking" : "Running";

  try {
    const result = await sendQuestion(question, conversationHistory);
    state.lastResponse = result;
    addMessage("assistant", result.answer);
    renderRunSummary(result);
    renderSql(result.sql);
    renderCitations(result.citations);
    renderTrace(result.trace);
  } catch (error) {
    addMessage("assistant", `Request failed: ${error.message}`);
  } finally {
    $("#send-button").disabled = false;
    $("#send-button").textContent = "Send";
  }
}

$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("#question-input").value.trim();
  if (!question) return;
  await submitQuestion(question);
});

$("#clear-button").addEventListener("click", () => {
  clearNode($("#messages"));
  state.messages = [];
  addMessage("assistant", "Workspace cleared. Ask a new regional operations question.", false);
  renderRunSummary();
  renderSql(null);
  renderCitations([]);
  renderTrace([]);
  $("#technical-details").open = false;
});

$$(".nav-button").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

$$(".mode-button").forEach((button) => {
  button.addEventListener("click", () => {
    if (!button.disabled) setAnswerMode(button.dataset.answerMode);
  });
});

$("#refresh-datasets").addEventListener("click", loadDatasets);
$("#run-eval").addEventListener("click", runEval);

renderRunSummary();
renderEvalState();
loadHealth();
loadDashboardSummary();
loadDatasets();
