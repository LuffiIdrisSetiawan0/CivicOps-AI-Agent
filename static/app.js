const state = {
  lastResponse: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function setView(view) {
  $$(".view").forEach((item) => item.classList.remove("active"));
  $$(".nav-button").forEach((item) => item.classList.remove("active"));
  $(`#${view}-view`).classList.add("active");
  $(`[data-view="${view}"]`).classList.add("active");
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  article.appendChild(paragraph);
  $("#messages").appendChild(article);
  $("#messages").scrollTop = $("#messages").scrollHeight;
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
  target.innerHTML = "";
  if (!citations.length) {
    target.textContent = "No citations returned.";
    target.classList.add("muted");
    return;
  }
  target.classList.remove("muted");
  citations.forEach((citation) => {
    const item = document.createElement("article");
    item.className = "evidence-item";
    item.innerHTML = `<strong>${citation.title}</strong><p>${citation.snippet}</p>`;
    target.appendChild(item);
  });
}

function renderTrace(trace) {
  $("#trace-count").textContent = `${trace.length} steps`;
  const target = $("#trace");
  target.innerHTML = "";
  if (!trace.length) {
    target.textContent = "Trace is disabled for this response.";
    target.classList.add("muted");
    return;
  }
  target.classList.remove("muted");
  trace.forEach((step) => {
    const item = document.createElement("article");
    item.className = "evidence-item";
    item.innerHTML = `<strong>${step.agent} - ${step.tool}</strong><p>${step.output_preview}</p>`;
    target.appendChild(item);
  });
}

async function sendQuestion(question) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, include_trace: true }),
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
    $("#status-dot").classList.add("ok");
    $("#health-text").textContent = health.openai_configured
      ? `Online with ${health.app}`
      : "Online in fallback mode";
  } catch (error) {
    $("#health-text").textContent = "Service unavailable";
  }
}

async function loadDatasets() {
  const target = $("#datasets-content");
  target.textContent = "Loading dataset metadata.";
  const response = await fetch("/api/datasets/preview");
  const data = await response.json();
  target.innerHTML = "";

  Object.entries(data.tables).forEach(([name, table]) => {
    const item = document.createElement("article");
    item.className = "catalog-item";
    item.innerHTML = `<strong>${name}</strong><p>${table.row_count} rows. Columns: ${table.columns.join(", ")}</p>`;
    target.appendChild(item);
  });

  data.documents.forEach((doc) => {
    const item = document.createElement("article");
    item.className = "catalog-item";
    item.innerHTML = `<strong>${doc.title}</strong><p>${doc.source}, ${doc.size_bytes} bytes</p>`;
    target.appendChild(item);
  });
}

async function runEval() {
  $("#eval-summary").textContent = "Running evaluation.";
  $("#eval-results").textContent = "Please wait.";
  const response = await fetch("/api/eval/run", { method: "POST" });
  const result = await response.json();
  $("#eval-summary").textContent = `${result.passed}/${result.total} passed. Target met: ${result.target_met}.`;
  const target = $("#eval-results");
  target.innerHTML = "";
  result.cases.forEach((testCase) => {
    const item = document.createElement("article");
    item.className = `eval-case ${testCase.passed ? "pass" : "fail"}`;
    item.innerHTML = `<strong>${testCase.id} - ${testCase.passed ? "PASS" : "FAIL"}</strong><p>${testCase.question}</p><p>${testCase.answer_preview}</p>`;
    target.appendChild(item);
  });
}

$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#question-input");
  const question = input.value.trim();
  if (!question) return;

  addMessage("user", question);
  input.value = "";
  $("#send-button").disabled = true;
  $("#send-button").textContent = "Running";
  try {
    const result = await sendQuestion(question);
    state.lastResponse = result;
    addMessage("assistant", result.answer);
    renderSql(result.sql);
    renderCitations(result.citations);
    renderTrace(result.trace);
  } catch (error) {
    addMessage("assistant", `Request failed: ${error.message}`);
  } finally {
    $("#send-button").disabled = false;
    $("#send-button").textContent = "Run Agent";
  }
});

$("#clear-button").addEventListener("click", () => {
  $("#messages").innerHTML = "";
  addMessage("assistant", "Workspace cleared. Ask a new regional operations question.");
  renderSql(null);
  renderCitations([]);
  renderTrace([]);
});

$$(".nav-button").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

$("#refresh-datasets").addEventListener("click", loadDatasets);
$("#run-eval").addEventListener("click", runEval);

loadHealth();
loadDatasets();

