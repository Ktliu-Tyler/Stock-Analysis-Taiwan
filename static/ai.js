const aiState = {
  models: [],
  defaultModel: "",
  positions: [],
};

const aiElements = {
  meta: document.querySelector("#aiMeta"),
  status: document.querySelector("#ollamaStatus"),
  stockSelect: document.querySelector("#stockSelect"),
  modelSelect: document.querySelector("#modelSelect"),
  savedPositionSelect: document.querySelector("#savedPositionSelect"),
  stockQuestion: document.querySelector("#stockQuestion"),
  stockAnalyzeBtn: document.querySelector("#stockAnalyzeBtn"),
  stockOutput: document.querySelector("#stockOutput"),
  stockOutputMeta: document.querySelector("#stockOutputMeta"),
  sharesInput: document.querySelector("#sharesInput"),
  averageCostInput: document.querySelector("#averageCostInput"),
  positionStatus: document.querySelector("#positionStatus"),
  horizonInput: document.querySelector("#horizonInput"),
  riskProfile: document.querySelector("#riskProfile"),
  positionNotes: document.querySelector("#positionNotes"),
  positionAnalyzeBtn: document.querySelector("#positionAnalyzeBtn"),
  positionOutput: document.querySelector("#positionOutput"),
  positionOutputMeta: document.querySelector("#positionOutputMeta"),
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function initAIPage() {
  showLoading("載入 AI 分析頁");
  await loadAIStatus();
  await loadPositions();
  await loadStocks();
  applyPositionFromUrl();
  hideLoading();
}

async function loadAIStatus() {
  const payload = await fetchJson("/api/ai/status");
  aiState.models = payload.models || [];
  aiState.defaultModel = payload.default_model || "";
  if (payload.available) {
    aiElements.status.textContent = "Ollama 可用";
    aiElements.meta.textContent = `已連線 ${payload.host}，預設模型 ${payload.default_model}`;
  } else {
    aiElements.status.textContent = "Ollama 未連線";
    aiElements.meta.textContent = payload.error ? `Ollama 錯誤：${payload.error}` : "找不到可用模型";
  }
  renderModels();
}

function renderModels() {
  if (!aiState.models.length) {
    aiElements.modelSelect.innerHTML = `<option value="${escapeHtml(aiState.defaultModel)}">${escapeHtml(aiState.defaultModel || "qwen3.5:9b")}</option>`;
    return;
  }
  aiElements.modelSelect.innerHTML = aiState.models
    .map((model) => {
      const label = `${model.name}${model.parameter_size ? ` · ${model.parameter_size}` : ""}${model.quantization_level ? ` · ${model.quantization_level}` : ""}`;
      return `<option value="${escapeHtml(model.name)}">${escapeHtml(label)}</option>`;
    })
    .join("");
  aiElements.modelSelect.value = aiState.defaultModel || aiState.models[0].name;
}

async function loadStocks() {
  const payload = await fetchJson("/api/screener/today?min_score=0&exclude_high_risk=0");
  const items = payload.items || [];
  aiElements.stockSelect.innerHTML = items.length
    ? items.map((item) => `<option value="${escapeHtml(item.stock_id)}">${item.stock_id} ${escapeHtml(item.name)} · ${escapeHtml(item.decision)}</option>`).join("")
    : `<option value="">沒有可用股票，請先回篩選頁更新資料</option>`;
}

async function loadPositions() {
  const payload = await fetchJson("/api/portfolio");
  aiState.positions = payload.items || [];
  aiElements.savedPositionSelect.innerHTML = `<option value="">不使用保存持股</option>${aiState.positions
    .map((item) => `<option value="${escapeHtml(item.id)}">${item.stock_id} ${escapeHtml(item.name)} · ${formatNumber(item.shares)}股 · 損益 ${formatPct(item.unrealized_pnl_pct)}</option>`)
    .join("")}`;
}

function applyPositionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const positionId = params.get("position_id");
  if (!positionId) return;
  aiElements.savedPositionSelect.value = positionId;
  applySavedPosition(positionId);
}

function applySavedPosition(positionId) {
  const position = aiState.positions.find((item) => String(item.id) === String(positionId));
  if (!position) return;
  aiElements.stockSelect.value = position.stock_id;
  aiElements.sharesInput.value = position.shares || "";
  aiElements.averageCostInput.value = position.average_cost || "";
  aiElements.positionStatus.value = position.position_status || "已持有";
  aiElements.horizonInput.value = position.horizon || "短線1-5日";
  aiElements.riskProfile.value = position.risk_profile || "中等";
  aiElements.positionNotes.value = position.notes || "";
}

async function analyzeStock() {
  const stockId = aiElements.stockSelect.value;
  if (!stockId) return;
  setBusy(aiElements.stockAnalyzeBtn, true, "AI 分析中");
  showLoading("Ollama 正在生成單檔分析");
  aiElements.stockOutputMeta.textContent = "Ollama 生成中";
  setOutputMessage(aiElements.stockOutput, "模型正在閱讀技術面、籌碼面、情緒面與風控資料...", "isLoading");
  try {
    const payload = await fetchJson("/api/ai/analyze-stock", {
      method: "POST",
      body: JSON.stringify({
        stock_id: stockId,
        model: aiElements.modelSelect.value,
        question: aiElements.stockQuestion.value,
      }),
    });
    renderAIResult(payload, aiElements.stockOutput, aiElements.stockOutputMeta);
  } catch (error) {
    aiElements.stockOutputMeta.textContent = "分析失敗";
    setOutputMessage(aiElements.stockOutput, error.message, "isError");
  } finally {
    setBusy(aiElements.stockAnalyzeBtn, false, "分析該檔股票");
    hideLoading();
  }
}

async function analyzePosition() {
  const savedPosition = aiState.positions.find((item) => String(item.id) === String(aiElements.savedPositionSelect.value));
  const stockId = aiElements.stockSelect.value || savedPosition?.stock_id || "";
  if (!stockId && !savedPosition) return;
  setBusy(aiElements.positionAnalyzeBtn, true, "AI 分析中");
  showLoading("Ollama 正在生成持股策略");
  aiElements.positionOutputMeta.textContent = "Ollama 生成中";
  setOutputMessage(aiElements.positionOutput, "模型正在整合持股成本、系統分數與風控條件...", "isLoading");
  try {
    const payload = await fetchJson("/api/ai/analyze-position", {
      method: "POST",
      body: JSON.stringify({
        stock_id: stockId,
        model: aiElements.modelSelect.value,
        position_id: aiElements.savedPositionSelect.value,
        shares: aiElements.sharesInput.value,
        average_cost: aiElements.averageCostInput.value,
        position_status: aiElements.positionStatus.value,
        horizon: aiElements.horizonInput.value,
        risk_profile: aiElements.riskProfile.value,
        notes: aiElements.positionNotes.value,
      }),
    });
    renderAIResult(payload, aiElements.positionOutput, aiElements.positionOutputMeta);
  } catch (error) {
    aiElements.positionOutputMeta.textContent = "分析失敗";
    setOutputMessage(aiElements.positionOutput, error.message, "isError");
  } finally {
    setBusy(aiElements.positionAnalyzeBtn, false, "分析我的買賣策略");
    hideLoading();
  }
}

function renderAIResult(payload, outputElement, metaElement) {
  if (payload.error) {
    metaElement.textContent = payload.error;
    setOutputMessage(outputElement, payload.message || payload.error, "isError");
    return;
  }
  metaElement.textContent = `${payload.model} · ${payload.analysis_type}`;
  renderAIReport(outputElement, payload.content || "沒有回覆內容");
}

function setOutputMessage(outputElement, message, state = "") {
  outputElement.className = `aiOutput aiOutputMessage ${state}`.trim();
  outputElement.textContent = message;
}

function renderAIReport(outputElement, content) {
  const normalized = String(content || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    setOutputMessage(outputElement, "沒有回覆內容");
    return;
  }
  outputElement.className = "aiOutput aiReportShell";
  outputElement.innerHTML = formatAIReport(normalized);
}

function formatAIReport(content) {
  const lines = content.split("\n");
  let html = `<article class="aiReport">`;
  let inList = false;
  let listType = "ul";
  let paragraphCount = 0;

  const closeList = () => {
    if (!inList) return;
    html += `</${listType}>`;
    inList = false;
  };

  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line || /^[-*_]{3,}$/.test(line)) {
      closeList();
      return;
    }

    const heading = parseHeading(line);
    if (heading) {
      closeList();
      html += `<div class="aiSectionTitle ${toneClass(line)}">${formatInline(heading)}</div>`;
      return;
    }

    const ordered = line.match(/^\d+[.)、]\s+(.+)$/);
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    if (ordered || bullet) {
      const nextType = ordered ? "ol" : "ul";
      if (!inList || listType !== nextType) {
        closeList();
        listType = nextType;
        html += `<${listType} class="aiList">`;
        inList = true;
      }
      html += `<li class="${toneClass(line)}">${formatInline((ordered || bullet)[1])}</li>`;
      return;
    }

    const fact = parseFactLine(line);
    if (fact) {
      closeList();
      html += `<div class="aiFact ${toneClass(line)}"><span>${escapeHtml(fact.label)}</span><p>${formatInline(fact.value)}</p></div>`;
      return;
    }

    closeList();
    paragraphCount += 1;
    html += `<p class="aiParagraph${paragraphCount === 1 ? " isLead" : ""} ${toneClass(line)}">${formatInline(line)}</p>`;
  });

  closeList();
  html += `</article>`;
  return html;
}

function parseHeading(line) {
  const hashHeading = line.match(/^#{1,4}\s+(.+)$/);
  if (hashHeading) return stripMarkdown(hashHeading[1]);

  const boldHeading = line.match(/^\*\*(.{2,36})\*\*[:：]?$/);
  if (boldHeading) return stripMarkdown(boldHeading[1]);

  const numberedHeading = line.match(/^\d+[.)、]\s*(.{2,28})[:：]?$/);
  if (numberedHeading && !numberedHeading[1].includes("：") && !numberedHeading[1].includes(":")) {
    return stripMarkdown(numberedHeading[1]);
  }

  const plainHeading = line.match(/^([^：:]{2,24})[：:]$/);
  if (plainHeading) return stripMarkdown(plainHeading[1]);

  return "";
}

function parseFactLine(line) {
  const match = line.match(/^([^：:]{2,14})[：:]\s*(.+)$/);
  if (!match) return null;
  return {
    label: stripMarkdown(match[1]),
    value: match[2],
  };
}

function stripMarkdown(value) {
  return String(value || "").replaceAll("*", "").replaceAll("#", "").trim();
}

function formatInline(value) {
  let html = escapeHtml(value);
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  [
    ["good", /(適合買入|看多|偏多|續抱|加碼|正向|突破|轉強|有利)/g],
    ["warn", /(觀察|等待|拉回|中性|留意|注意|震盪|資料不足)/g],
    ["bad", /(避開|看空|偏空|減碼|停損|風險|不買|轉弱|跌破|過熱)/g],
  ].forEach(([tone, pattern]) => {
    html = html.replace(pattern, `<span class="aiTag ${tone}">$1</span>`);
  });

  return html;
}

function toneClass(value) {
  const text = String(value || "");
  if (/避開|看空|偏空|減碼|停損|不買|跌破|轉弱|過熱|風險/.test(text)) return "toneBad";
  if (/觀察|等待|拉回|中性|留意|注意|資料不足|震盪/.test(text)) return "toneWarn";
  if (/適合買入|看多|偏多|續抱|加碼|正向|突破|轉強|有利/.test(text)) return "toneGood";
  return "";
}

function setBusy(button, busy, text) {
  button.disabled = busy;
  button.textContent = text;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 0 });
}

function formatPct(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showLoading(message) {
  const toast = ensureLoadingToast();
  toast.querySelector("span:last-child").textContent = message;
  toast.classList.add("isVisible");
}

function hideLoading() {
  const toast = document.querySelector("#loadingToast");
  if (!toast) return;
  toast.classList.remove("isVisible");
}

function ensureLoadingToast() {
  let toast = document.querySelector("#loadingToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "loadingToast";
    toast.className = "loadingToast";
    toast.setAttribute("aria-live", "polite");
    toast.innerHTML = `<span class="spinner"></span><span>載入中</span>`;
    document.body.appendChild(toast);
  }
  return toast;
}

aiElements.savedPositionSelect.addEventListener("change", () => {
  applySavedPosition(aiElements.savedPositionSelect.value);
});
aiElements.stockAnalyzeBtn.addEventListener("click", analyzeStock);
aiElements.positionAnalyzeBtn.addEventListener("click", analyzePosition);

initAIPage().catch((error) => {
  hideLoading();
  aiElements.meta.textContent = `初始化失敗：${error.message}`;
});
