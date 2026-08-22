const fixtureEntities = [
  {
    id: "omlx",
    name: "oMLX",
    mark: "oM",
    tone: "",
    status: "RISING",
    score: 91,
    trend: "+14",
    description: "Native Apple Silicon inference server for local LLMs.",
    category: "Local LLM · Inference",
    detected: "2 days ago",
    sources: "GitHub + HN",
    summary: "oMLX turns Apple Silicon hardware into a fast, local inference server. It is small enough to be an early project, but its recent star acceleration and Show HN discussion suggest developer attention is moving quickly.",
    why: "The project crossed from a single-source GitHub signal into a cross-source signal within 24 hours.",
    evidence: [["+420", "GitHub stars / 24h"], ["3.2×", "star velocity"], ["140", "HN points"]],
    links: [["GitHub", "https://github.com/"], ["Show HN", "https://news.ycombinator.com/"]]
  },
  {
    id: "herdr",
    name: "Herdr",
    mark: "H",
    tone: "violet",
    status: "RISING",
    score: 86,
    trend: "+9",
    description: "A lightweight agent runtime for coordinating local workflows.",
    category: "Agent Runtime · Orchestration",
    detected: "2 days ago",
    sources: "GitHub + Reddit",
    summary: "Herdr is an early-stage agent runtime focused on practical coordination between tools and local processes. Radar is seeing unusually concentrated discussion for its current repository size.",
    why: "Independent mentions appeared in two configured communities while repository activity accelerated.",
    evidence: [["+188", "GitHub stars / 24h"], ["2", "Reddit communities"], ["4.6×", "mention velocity"]],
    links: [["GitHub", "https://github.com/"], ["Reddit", "https://www.reddit.com/"]]
  },
  {
    id: "agent-forge",
    name: "Agent Forge",
    mark: "AF",
    tone: "amber",
    status: "RISING",
    score: 79,
    trend: "+7",
    description: "Composable multi-agent workflows with a local-first developer loop.",
    category: "Multi-agent · Developer Tooling",
    detected: "4 days ago",
    sources: "GitHub + HN",
    summary: "Agent Forge packages multi-agent experiments into a repeatable local development loop. It is not yet broadly discussed, which keeps the saturation penalty low.",
    why: "A new release created a second velocity spike after the initial repository discovery.",
    evidence: [["+97", "GitHub stars / 24h"], ["2.1×", "fork velocity"], ["76", "HN points"]],
    links: [["GitHub", "https://github.com/"], ["Hacker News", "https://news.ycombinator.com/"]]
  },
  {
    id: "mcp-relay",
    name: "MCP Relay",
    mark: "MR",
    tone: "coral",
    status: "TRENDING",
    score: 74,
    trend: "+2",
    description: "A hosted gateway for connecting MCP tools across environments.",
    category: "MCP · Infrastructure",
    detected: "11 days ago",
    sources: "GitHub + Product Hunt",
    summary: "MCP Relay has meaningful cross-source evidence, but its older first-seen date and growing discussion volume reduce its early-signal score.",
    why: "It remains relevant, but the evidence now looks closer to an established trend than a weak early signal.",
    evidence: [["+62", "GitHub stars / 24h"], ["#8", "Product Hunt launch"], ["11d", "days detected"]],
    links: [["GitHub", "https://github.com/"], ["Product Hunt", "https://www.producthunt.com/"]]
  },
  {
    id: "prompt-dock",
    name: "Prompt Dock",
    mark: "PD",
    tone: "violet",
    status: "NEW",
    score: 63,
    trend: "new",
    description: "Versioned prompt and context experiments for small teams.",
    category: "Prompt Infrastructure",
    detected: "8 hours ago",
    sources: "GitHub",
    summary: "Prompt Dock is too new for strong confidence, but its repository metadata fits the topic and its first snapshot is worth watching.",
    why: "A clean first signal with high topic relevance, awaiting a second source or another metric snapshot.",
    evidence: [["+31", "GitHub stars / 8h"], ["1", "source"], ["8h", "first detected"]],
    links: [["GitHub", "https://github.com/"]]
  },
  {
    id: "open-eval-kit",
    name: "Open Eval Kit",
    mark: "OE",
    tone: "",
    status: "WATCHLIST",
    score: 58,
    trend: "−3",
    description: "Open evaluation harness for agent and model-serving projects.",
    category: "Evaluation · AI Infrastructure",
    detected: "19 days ago",
    sources: "GitHub + RSS",
    summary: "Open Eval Kit is useful and relevant, but recent velocity has cooled. It stays on the watchlist while the next release cycle develops.",
    why: "Strong relevance and official-source confirmation, offset by negative recent acceleration.",
    evidence: [["+12", "GitHub stars / 24h"], ["1", "official feed"], ["−0.4×", "acceleration"]],
    links: [["GitHub", "https://github.com/"], ["Changelog", "https://example.com/"]]
  },
  {
    id: "context-lens",
    name: "Context Lens",
    mark: "CL",
    tone: "amber",
    status: "NEW",
    score: 55,
    trend: "new",
    description: "A visual context window inspector for agent developers.",
    category: "Context Infrastructure",
    detected: "6 hours ago",
    sources: "GitHub",
    summary: "Context Lens is an early repository signal for inspecting what an agent can see before a run. It is relevant but has not yet accumulated enough history for a confident ranking.",
    why: "The topic match is strong; Radar is waiting for a second source and another daily metric snapshot.",
    evidence: [["+24", "GitHub stars / 6h"], ["0", "cross-source matches"], ["6h", "first detected"]],
    links: [["GitHub", "https://github.com/"]]
  },
  {
    id: "flow-mcp",
    name: "Flow MCP",
    mark: "FM",
    tone: "",
    status: "NEW",
    score: 51,
    trend: "new",
    description: "A small MCP server toolkit for repeatable automation flows.",
    category: "MCP · AI Automation",
    detected: "3 hours ago",
    sources: "GitHub",
    summary: "Flow MCP is a small but on-topic toolkit with an early burst of repository activity. It is a watch candidate until engagement becomes more durable.",
    why: "A new project with good keyword relevance but only one source so far.",
    evidence: [["+18", "GitHub stars / 3h"], ["1", "source"], ["3h", "first detected"]],
    links: [["GitHub", "https://github.com/"]]
  },
  {
    id: "eval-garden",
    name: "Eval Garden",
    mark: "EG",
    tone: "violet",
    status: "WATCHLIST",
    score: 49,
    trend: "−1",
    description: "Community templates for evaluating agent workflows.",
    category: "Evaluation · Agent Tooling",
    detected: "27 days ago",
    sources: "GitHub",
    summary: "Eval Garden is relevant and useful, but its recent activity is steady rather than accelerating.",
    why: "The signal is credible but not yet early or fast-moving enough for the daily digest.",
    evidence: [["+8", "GitHub stars / 24h"], ["1", "source"], ["27d", "days detected"]],
    links: [["GitHub", "https://github.com/"]]
  },
  {
    id: "tiny-agent-os",
    name: "Tiny Agent OS",
    mark: "TA",
    tone: "coral",
    status: "WATCHLIST",
    score: 46,
    trend: "−2",
    description: "Minimal runtime experiments for embedded agent tasks.",
    category: "Agent Runtime",
    detected: "34 days ago",
    sources: "GitHub + RSS",
    summary: "Tiny Agent OS has official-source confirmation, but its attention curve has flattened after an earlier release.",
    why: "Source quality is positive; current acceleration is not.",
    evidence: [["+5", "GitHub stars / 24h"], ["1", "official feed"], ["−0.2×", "acceleration"]],
    links: [["GitHub", "https://github.com/"], ["Release notes", "https://example.com/"]]
  },
  {
    id: "trace-loop",
    name: "Trace Loop",
    mark: "TL",
    tone: "amber",
    status: "WATCHLIST",
    score: 43,
    trend: "−4",
    description: "Local observability helpers for tool-using agents.",
    category: "AI Observability",
    detected: "41 days ago",
    sources: "GitHub",
    summary: "Trace Loop is a useful adjacent project, though attention has cooled and cross-source confirmation is still missing.",
    why: "It remains stored for future Hermes research, but should not compete with emerging signals today.",
    evidence: [["+3", "GitHub stars / 24h"], ["1", "source"], ["−0.6×", "acceleration"]],
    links: [["GitHub", "https://github.com/"]]
  }
];

const housingFixtureEntities = [
  { id: "beituo-life", name: "北投學區生活圈", mark: "北", tone: "amber", status: "RISING", score: 84, trend: "+11", description: "成交、新掛牌與交通建設訊號同步增加。", category: "School District · Transaction", detected: "2 days ago", sources: "實價登錄 + RSS", summary: "北投學區生活圈出現成交、新掛牌與交通建設的交叉訊號。這是 fixture preview，不代表即時市場結論。", why: "多個獨立來源在短時間內提到住宅、學區與捷運訊號，且供給與討論速度同步上升。", evidence: [["+28%", "新掛牌 / 7 days"], ["+3.4%", "成交單價變化"], ["3", "獨立來源"]], links: [["Market feed", "https://example.com/"]], entity_type: "residential_project" },
  { id: "songshan-rental", name: "松山租賃市場", mark: "松", tone: "violet", status: "RISING", score: 76, trend: "+8", description: "租金與出租物件數出現初步變化。", category: "Rental · Transaction", detected: "3 days ago", sources: "RSS + Market data", summary: "松山租賃市場正在累積早期供需訊號，仍需要更多成交樣本確認。", why: "租金與物件供給訊號跨來源出現，且討論速度高於前一週。", evidence: [["+12%", "租金討論 / 7 days"], ["+18", "相關物件"], ["2", "獨立來源"]], links: [["Market feed", "https://example.com/"]], entity_type: "rental" },
  { id: "new-project", name: "○○捷運站周邊新案", mark: "案", tone: "coral", status: "EMERGING", score: 68, trend: "+5", description: "新案價格與公共建設關鍵字開始擴散。", category: "Residential Project · Infrastructure", detected: "5 days ago", sources: "RSS", summary: "一個新案與周邊交通建設訊號開始被不同來源同時提及。", why: "目前仍以單一來源為主，但新案與基礎建設的關聯值得追蹤。", evidence: [["+19", "新案 mentions"], ["2.1×", "討論速度"], ["5d", "首次偵測"]], links: [["Project feed", "https://example.com/"]], entity_type: "residential_project" },
  { id: "school-watch", name: "文山學區租屋", mark: "文", tone: "", status: "WATCHLIST", score: 51, trend: "−1", description: "學區租屋供給有變化，但成交證據仍不足。", category: "School District · Rental", detected: "19 days ago", sources: "RSS", summary: "文山學區租屋仍在觀察名單，當前訊號尚不足以判斷持續性趨勢。", why: "相關性高，但來源數量與歷史樣本仍不足。", evidence: [["+4", "新物件 / 7 days"], ["1", "來源"], ["19d", "首次偵測"]], links: [["Market feed", "https://example.com/"]], entity_type: "school_district" }
];

let entities = fixtureEntities;
let currentTopic = "ai_tools";
let currentTopicLabel = "AI Tools";
let currentFilter = "RISING";
const filterLabels = { RISING: "Rising", NEW: "New Signals", WATCHLIST: "Watchlist", ALL: "All signals" };
const entityList = document.querySelector("#entityList");
const detailModal = document.querySelector("#detailModal");
const digestModal = document.querySelector("#digestModal");
const healthModal = document.querySelector("#healthModal");
const settingsModal = document.querySelector("#settingsModal");

function statusClass(status) { return status.toLowerCase(); }

function visibleEntities(filter) {
  if (filter === "ALL") return entities;
  if (filter === "WATCHLIST") return entities.filter((entity) => entity.status === "WATCHLIST");
  return entities.filter((entity) => entity.status === filter);
}

function renderEntities(filter = "RISING") {
  const visible = visibleEntities(filter);
  entityList.innerHTML = visible.length ? visible.map((entity, index) => `
    <button class="entity-row" data-entity-id="${entity.id}" aria-label="查看 ${entity.name} 詳情">
      <span class="entity-rank">${String(index + 1).padStart(2, "0")}</span>
      <span class="entity-logo ${entity.tone}">${entity.mark}</span>
      <span class="entity-main">
        <span class="entity-title-line"><strong>${entity.name}</strong><span class="status-pill ${statusClass(entity.status)}">${entity.status}</span></span>
        <span class="entity-description">${entity.description}</span>
        <span class="entity-meta"><span>${entity.sources}</span><span>·</span><span>First detected ${entity.detected}</span></span>
      </span>
      <span class="entity-score-block"><span class="score">${entity.score}</span><span class="score-trend ${entity.trend.startsWith("−") ? "down" : ""}">${entity.trend === "new" ? "new signal" : `↑ ${entity.trend.replace("+", "")}`}</span></span>
    </button>`).join("") : `<div class="empty-state">No signals in this view yet.</div>`;
  entityList.querySelectorAll("[data-entity-id]").forEach((row) => row.addEventListener("click", () => openDetail(row.dataset.entityId)));
}

function openDetail(id) {
  const entity = entities.find((item) => item.id === id);
  if (!entity) return;
  document.querySelector("#detailTitle").textContent = entity.name;
  document.querySelector("#detailContent").innerHTML = `
    <div class="detail-body">
      <div class="detail-summary"><div><span class="status-pill ${statusClass(entity.status)}">${entity.status}</span><p style="margin-top: 10px">${entity.category} · First detected ${entity.detected}</p></div><div class="detail-score">${entity.score}<small>${entity.trend === "new" ? "new signal" : `↑ ${entity.trend.replace("+", "")} today`}</small></div></div>
      <div class="detail-section"><h3>What it is</h3><p>${entity.summary}</p></div>
      <div class="detail-section"><h3>Why Radar detected it</h3><p>${entity.why}</p><div class="evidence-grid" style="margin-top: 13px">${entity.evidence.map(([value, label]) => `<div class="evidence-card"><b>${value}</b><span>${label}</span></div>`).join("")}</div></div>
      <div class="detail-section"><h3>Score history</h3><div class="score-track"><span style="width: ${Math.min(entity.score, 96)}%"></span></div><p style="margin-top: 8px; color: var(--muted); font-size: 10px">Momentum and acceleration are weighted above absolute popularity.</p></div>
      <div class="detail-section"><h3>Source evidence</h3><div class="detail-links">${entity.links.map(([label, href]) => `<a class="detail-link" href="${href}" target="_blank" rel="noreferrer">↗ ${label}</a>`).join("")}</div></div>
    </div>`;
  detailModal.showModal();
}

function openDigest() {
  const digestStats = {
    rising: entities.filter((entity) => ["RISING", "TRENDING"].includes(entity.status)).length,
    fresh: entities.filter((entity) => ["NEW", "EMERGING"].includes(entity.status)).length,
    watchlist: entities.filter((entity) => ["WATCHLIST", "COOLING"].includes(entity.status)).length
  };
  document.querySelector("#digestContent").innerHTML = `
    <div class="telegram-header"><span>INFORMATION RADAR</span><span>2026.08.21</span></div>
    <h3>🔥 ${currentTopicLabel} · Morning Digest</h3>
    ${entities.slice(0, 4).map((entity, index) => `<div class="digest-item"><strong>#${index + 1} ${entity.name} · ${entity.score} ${entity.status === "RISING" ? "↑" : ""}</strong><p>${entity.summary}</p><div class="digest-meta">${entity.sources} · ${entity.detected} · ${entity.category}</div></div>`).join("")}
    <div style="padding-top: 14px; color: var(--faint); font-size: 9px">Radar found ${digestStats.rising} rising signals, ${digestStats.fresh} new discoveries, and ${digestStats.watchlist} watchlist items.</div>`;
  digestModal.showModal();
}

function openHealth() { healthModal.showModal(); }
function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2600);
}

function normalizeRemoteEntity(entity) {
  return {
    ...entity,
    mark: entity.mark || (entity.name || "?").slice(0, 2),
    tone: entity.tone || "",
    sources: Array.isArray(entity.sources) ? entity.sources.map((source) => source === "hackernews" ? "HN" : source).join(" + ") : (entity.sources || "Unknown"),
    detected: entity.detected || "recently",
    description: entity.description || entity.summary || "Signal detected by Radar.",
    summary: entity.summary || entity.description || "Signal detected by Radar.",
    why: entity.why || "Cross-source attention is being evaluated.",
    evidence: entity.evidence || [],
    links: entity.links || []
  };
}

function updateText(id, value) {
  const element = document.querySelector(`#${id}`);
  if (element) element.textContent = value;
}

function applyTopicState(state) {
  const localStats = {
    rising: entities.filter((entity) => entity.status === "RISING").length,
    new: entities.filter((entity) => entity.status === "NEW").length,
    watchlist: entities.filter((entity) => entity.status === "WATCHLIST").length,
    all: entities.length
  };
  const stats = state?.stats || localStats;
  updateText("breadcrumbTopic", currentTopicLabel);
  updateText("metricRisingCount", stats.rising);
  updateText("metricNewCount", stats.new);
  updateText("metricWatchlistCount", stats.watchlist);
  updateText("navCount", stats.all);
  updateText("filterRisingCount", stats.rising);
  updateText("filterNewCount", stats.new);
  updateText("filterWatchlistCount", stats.watchlist);
  updateText("filterAllCount", stats.all);
  if (state?.runs?.length) {
    const latestRuns = {};
    state.runs.forEach((run) => { if (!latestRuns[run.source]) latestRuns[run.source] = run; });
    document.querySelectorAll(".source-row[data-source]").forEach((row) => {
      const run = latestRuns[row.dataset.source];
      if (!run) return;
      const status = row.querySelector(".status-ok, .status-warn");
      const detail = row.querySelector("small");
      const healthy = run.status === "SUCCESS";
      if (status) { status.className = healthy ? "status-ok" : "status-warn"; status.textContent = healthy ? "Operational" : run.status; }
      if (detail) detail.textContent = `${run.items_accepted || 0} accepted · ${run.status}`;
    });
  }
  const heroSubtitle = document.querySelector("#heroSubtitle");
  if (heroSubtitle) heroSubtitle.innerHTML = `昨天到今天，有 <strong>${stats.rising} 個新訊號</strong> 正在快速升溫。`;
  const briefLead = document.querySelector(".brief-lead strong");
  const briefText = document.querySelector(".brief-lead p");
  const miniSignals = document.querySelectorAll(".mini-signal");
  if (currentTopic === "housing") {
    if (briefLead) briefLead.textContent = "北投學區生活圈正在升溫";
    if (briefText) briefText.textContent = "成交、新掛牌與交通建設訊號同步出現；目前仍以 fixture preview 示意。";
    entities.slice(0, 2).forEach((entity, index) => {
      const signal = miniSignals[index];
      if (!signal) return;
      signal.querySelector("strong").textContent = entity.name;
      signal.querySelector("p").textContent = `${entity.sources} · 首次偵測 ${entity.detected}`;
      signal.querySelector(".mini-score").textContent = entity.score;
    });
  } else {
    if (briefLead) briefLead.textContent = "oMLX 正在加速";
    if (briefText) briefText.textContent = "GitHub stars 的日增速是前一週的 3.2×，並在 HN 出現 Show HN 討論。";
  }
}

async function loadTopic(topicId) {
  currentTopic = topicId;
  const selector = document.querySelector("#topicSelector");
  currentTopicLabel = selector?.options[selector.selectedIndex]?.text || (topicId === "housing" ? "Housing" : "AI Tools");
  entities = topicId === "housing" ? housingFixtureEntities : fixtureEntities;
  let state = null;
  try {
    const response = await fetch(`/api/state?topic=${encodeURIComponent(topicId)}`);
    if (response.ok) state = await response.json();
    if (state?.entities?.length) entities = state.entities.map(normalizeRemoteEntity);
  } catch (error) {
    // Static-only mode intentionally falls back to local fixture data.
  }
  if (!visibleEntities(currentFilter).length) {
    currentFilter = "ALL";
    document.querySelectorAll(".filter-button").forEach((button) => button.classList.toggle("active", button.dataset.filter === currentFilter));
  }
  applyTopicState(state);
  renderEntities(currentFilter);
  showToast(`${currentTopicLabel} radar loaded${state ? " · API data" : " · fixture preview"}`);
}

function setSettingsResult(message, kind = "") {
  const result = document.querySelector("#settingsResult");
  if (!result) return;
  result.textContent = message;
  result.className = `settings-result ${kind}`;
}

function renderSettings(items) {
  items.forEach((item) => {
    const status = document.querySelector(`[data-setting-status="${item.key}"]`);
    if (!status) return;
    status.textContent = item.configured ? `${item.source === "environment" ? "Environment" : "Configured"}${item.masked ? ` · ${item.masked}` : ""}` : "Not configured";
    status.classList.toggle("configured", item.configured && item.source === "web");
    status.classList.toggle("environment", item.configured && item.source === "environment");
  });
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) throw new Error("Settings API unavailable");
    const payload = await response.json();
    renderSettings(payload.settings || []);
    setSettingsResult("Settings status loaded.", "success");
  } catch (error) {
    setSettingsResult("Start the Radar server to manage live settings.", "error");
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = {};
  document.querySelectorAll("#settingsForm input[name]").forEach((input) => { payload[input.name] = input.value; });
  setSettingsResult("Saving locally…");
  try {
    const response = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Save failed");
    renderSettings(result.settings || []);
    document.querySelectorAll("#settingsForm input[type=password]").forEach((input) => { input.value = ""; });
    setSettingsResult(`${(result.saved || []).length} setting(s) saved. Secrets were not returned to the browser.`, "success");
  } catch (error) {
    setSettingsResult(error.message, "error");
  }
}

async function verifySetting(button) {
  const target = button.dataset.verify;
  const deliveryTest = button.dataset.deliveryTest === "true";
  if (deliveryTest && !window.confirm(`Send a real test payload to ${target}?`)) return;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Checking…";
  setSettingsResult(`${target} verification in progress…`);
  try {
    const response = await fetch("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, delivery_test: deliveryTest }) });
    const result = await response.json();
    const kind = result.status === "SUCCESS" ? "success" : "error";
    setSettingsResult(`${target}: ${result.message || result.status}`, kind);
    if (result.status === "SUCCESS") showToast(`${target} verification succeeded`);
  } catch (error) {
    setSettingsResult(`${target}: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

document.querySelectorAll(".filter-button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".filter-button").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  currentFilter = button.dataset.filter;
  renderEntities(button.dataset.filter);
}));
document.querySelector("#topicSelector").addEventListener("change", (event) => loadTopic(event.target.value));
function openSettings() { settingsModal.showModal(); loadSettings(); }
document.querySelector("#settingsButton").addEventListener("click", openSettings);
document.querySelector("#settingsTopButton").addEventListener("click", openSettings);
document.querySelector("#settingsForm").addEventListener("submit", saveSettings);
document.querySelectorAll("[data-verify]").forEach((button) => button.addEventListener("click", () => verifySetting(button)));
document.querySelector("#digestButton").addEventListener("click", openDigest);
document.querySelector("#briefDigestButton").addEventListener("click", openDigest);
document.querySelector("#healthButton").addEventListener("click", openHealth);
document.querySelector("#healthDetailsButton").addEventListener("click", openHealth);
document.querySelector("#refreshButton").addEventListener("click", () => loadTopic(currentTopic));
document.querySelector("#allEntitiesButton").addEventListener("click", () => {
  document.querySelector('[data-filter="ALL"]').click();
  document.querySelector(".radar-panel").scrollIntoView({ behavior: "smooth" });
});
document.querySelector("#notificationsButton").addEventListener("click", () => showToast("1 operational notice · Reddit rate limited on the last run"));
document.querySelector("#simulateDeliveryButton").addEventListener("click", (event) => {
  event.currentTarget.textContent = "Delivered ✓";
  event.currentTarget.disabled = true;
  showToast("Telegram delivery simulated successfully");
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => document.querySelector(`#${button.dataset.close}`).close()));
document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); }));
document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach((nav) => nav.classList.remove("active"));
  item.classList.add("active");
  if (item.dataset.view === "digest") openDigest();
  if (item.dataset.view === "history") { document.querySelector('[data-filter="ALL"]').click(); showToast("History preview uses the current fixture snapshot"); }
}));

renderEntities();
loadTopic("ai_tools");
