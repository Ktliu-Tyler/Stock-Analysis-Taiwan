const state = {
  items: [],
  selectedStockId: "",
  industriesLoaded: false,
  analysisMode: "short",
};

const chartColors = {
  up: "#ff5d66",
  upSoft: "rgba(255, 93, 102, 0.26)",
  down: "#29c77a",
  downSoft: "rgba(41, 199, 122, 0.24)",
  grid: "#253448",
  muted: "#8d9aae",
};

const elements = {
  runMeta: document.querySelector("#runMeta"),
  refreshBtn: document.querySelector("#refreshBtn"),
  modeButtons: [...document.querySelectorAll("[data-mode]")],
  industryFilter: document.querySelector("#industryFilter"),
  scoreFilter: document.querySelector("#scoreFilter"),
  directionFilter: document.querySelector("#directionFilter"),
  adviceFilter: document.querySelector("#adviceFilter"),
  volumeFilter: document.querySelector("#volumeFilter"),
  techFilter: document.querySelector("#techFilter"),
  chipScoreFilter: document.querySelector("#chipScoreFilter"),
  sentimentFilter: document.querySelector("#sentimentFilter"),
  riskScoreFilter: document.querySelector("#riskScoreFilter"),
  modelConfidenceFilter: document.querySelector("#modelConfidenceFilter"),
  flowFilter: document.querySelector("#flowFilter"),
  riskFilter: document.querySelector("#riskFilter"),
  maFilter: document.querySelector("#maFilter"),
  macdFilter: document.querySelector("#macdFilter"),
  volumeBreakoutFilter: document.querySelector("#volumeBreakoutFilter"),
  breakoutFilter: document.querySelector("#breakoutFilter"),
  sentimentPositiveFilter: document.querySelector("#sentimentPositiveFilter"),
  modelBullishFilter: document.querySelector("#modelBullishFilter"),
  resultCount: document.querySelector("#resultCount"),
  stockRows: document.querySelector("#stockRows"),
  detailTitle: document.querySelector("#detailTitle"),
  detailDecision: document.querySelector("#detailDecision"),
  fullDetailLink: document.querySelector("#fullDetailLink"),
  detailEmpty: document.querySelector("#detailEmpty"),
  detailBody: document.querySelector("#detailBody"),
  scoreGrid: document.querySelector("#scoreGrid"),
  directionText: document.querySelector("#directionText"),
  investmentAdvice: document.querySelector("#investmentAdvice"),
  priceChart: document.querySelector("#priceChart"),
  flowChart: document.querySelector("#flowChart"),
  localModelPanel: document.querySelector("#localModelPanel"),
  indicatorBreakdown: document.querySelector("#indicatorBreakdown"),
  buyReason: document.querySelector("#buyReason"),
  avoidReason: document.querySelector("#avoidReason"),
  newsList: document.querySelector("#newsList"),
  backtestStrategy: document.querySelector("#backtestStrategy"),
  backtestRows: document.querySelector("#backtestRows"),
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

function params() {
  const query = new URLSearchParams();
  query.set("mode", state.analysisMode);
  query.set("industry", elements.industryFilter.value || "all");
  query.set("min_score", elements.scoreFilter.value || "0");
  query.set("direction", elements.directionFilter.value || "all");
  query.set("advice", elements.adviceFilter.value || "all");
  query.set("min_volume", elements.volumeFilter.value || "0");
  query.set("min_technical", elements.techFilter.value || "0");
  query.set("min_chip", elements.chipScoreFilter.value || "0");
  query.set("min_sentiment", elements.sentimentFilter.value || "0");
  query.set("min_risk", elements.riskScoreFilter.value || "0");
  query.set("min_model_confidence", elements.modelConfidenceFilter.value || "0");
  query.set("foreign_or_trust_only", elements.flowFilter.checked ? "1" : "0");
  query.set("exclude_high_risk", elements.riskFilter.checked ? "1" : "0");
  query.set("ma_bullish", elements.maFilter.checked ? "1" : "0");
  query.set("macd_bullish", elements.macdFilter.checked ? "1" : "0");
  query.set("volume_breakout", elements.volumeBreakoutFilter.checked ? "1" : "0");
  query.set("breakout_20d", elements.breakoutFilter.checked ? "1" : "0");
  query.set("sentiment_positive", elements.sentimentPositiveFilter.checked ? "1" : "0");
  query.set("local_model_bullish", elements.modelBullishFilter.checked ? "1" : "0");
  return query.toString();
}

async function loadToday() {
  showLoading("載入篩選結果中");
  elements.runMeta.textContent = "載入篩選結果中";
  if (!state.items.length) {
    renderTableSkeleton();
  }
  try {
    const payload = await fetchJson(`/api/screener/today?${params()}`);
    state.items = payload.items || [];
    const modeLabel = modeLabelText(payload.analysis_mode || state.analysisMode);
    elements.runMeta.textContent = `正式資料 · ${modeLabel}模式 · 掃描日期 ${payload.run_date || "-"}，目前 ${payload.count || 0} 檔符合條件`;
    elements.resultCount.textContent = `${payload.count || 0} 檔`;
    if (!state.industriesLoaded) {
      renderIndustries(payload.industries || []);
      state.industriesLoaded = true;
    }
    renderRows();
    if (!state.selectedStockId && state.items.length) {
      await loadReport(state.items[0].stock_id);
    }
    if (state.selectedStockId && !state.items.some((item) => item.stock_id === state.selectedStockId)) {
      clearDetail("目前篩選條件下沒有選取中的股票");
    }
  } catch (error) {
    elements.runMeta.textContent = `載入失敗：${error.message}`;
    elements.stockRows.innerHTML = `<tr><td colspan="11">載入失敗：${escapeHtml(error.message)}</td></tr>`;
  } finally {
    hideLoading();
  }
}

function renderTableSkeleton(rows = 8) {
  elements.stockRows.innerHTML = Array.from({ length: rows })
    .map(
      () => `<tr class="skeletonRow">
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton short"></span></td>
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton short"></span></td>
        <td><span class="skeleton short"></span></td>
        <td><span class="skeleton"></span></td>
      </tr>`
    )
    .join("");
}

function renderIndustries(industries) {
  const current = elements.industryFilter.value;
  elements.industryFilter.innerHTML = `<option value="all">全部</option>${industries
    .map((industry) => `<option value="${escapeHtml(industry)}">${escapeHtml(industry)}</option>`)
    .join("")}`;
  elements.industryFilter.value = current || "all";
}

function renderRows() {
  if (!state.items.length) {
    elements.stockRows.innerHTML = `<tr><td colspan="11">沒有符合條件的股票</td></tr>`;
    return;
  }
  elements.stockRows.innerHTML = state.items
    .map((item) => {
      const details = item.details || {};
      const decisionClass = decisionClassName(item.decision);
      const direction = details.direction || "-";
      const model = details.local_model || {};
      return `<tr data-stock="${item.stock_id}" class="${state.selectedStockId === item.stock_id ? "selected" : ""}">
        <td><div class="stockName"><strong>${item.stock_id} ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.industry)}</span></div></td>
        <td><span class="direction ${directionClassName(direction)}">${escapeHtml(direction)}</span></td>
        <td><span class="badge ${decisionClass}">${escapeHtml(item.decision)}</span><span class="modelMini">${escapeHtml(model.label || "")}</span></td>
        <td class="score">${formatScore(item.buy_score)}</td>
        <td>${formatScore(item.technical_score)}</td>
        <td>${formatScore(item.chip_score)}</td>
        <td>${formatScore(item.sentiment_score)}</td>
        <td>${formatScore(item.risk_score)}</td>
        <td>${formatPrice(item.entry_watch_price)}</td>
        <td>${formatPrice(item.stop_loss_price)}</td>
        <td>${escapeHtml(item.data_freshness)}</td>
      </tr>`;
    })
    .join("");
  document.querySelectorAll("tbody tr[data-stock]").forEach((row) => {
    row.addEventListener("click", () => loadReport(row.dataset.stock));
  });
}

async function loadReport(stockId) {
  state.selectedStockId = stockId;
  renderRows();
  showLoading(`載入 ${stockId} 分析`);
  elements.detailDecision.textContent = "載入中";
  elements.detailEmpty.hidden = false;
  elements.detailBody.hidden = true;
  elements.detailEmpty.innerHTML = `<span class="inlineLoader">載入 ${escapeHtml(stockId)} 分析中</span>`;
  try {
    const report = await fetchJson(`/api/stocks/${encodeURIComponent(stockId)}/report?mode=${encodeURIComponent(state.analysisMode)}`);
    if (report.error) {
      clearDetail("找不到股票資料");
      return;
    }
    elements.detailEmpty.hidden = true;
    elements.detailBody.hidden = false;
    const score = report.score;
    const details = score.details || {};
    elements.detailTitle.textContent = `${score.stock_id} ${score.name}`;
    elements.detailDecision.textContent = score.decision;
    elements.fullDetailLink.hidden = false;
    elements.fullDetailLink.href = `/stock.html?id=${encodeURIComponent(score.stock_id)}&mode=${encodeURIComponent(state.analysisMode)}`;
    elements.directionText.textContent = details.direction || "-";
    elements.directionText.className = directionClassName(details.direction || "");
    elements.investmentAdvice.textContent = details.investment_advice || "";
    renderScoreGrid(score);
    renderLocalModel(details.local_model || {});
    renderIndicatorBreakdown(details.indicator_breakdown || {});
    elements.buyReason.textContent = score.buy_reason;
    elements.avoidReason.textContent = score.avoid_reason;
    renderNews(report.news || []);
    drawPriceChart(elements.priceChart, report.prices || []);
    drawFlowChart(elements.flowChart, report.institutional_flows || [], report.margin_balances || []);
  } catch (error) {
    clearDetail(`分析載入失敗：${error.message}`);
  } finally {
    hideLoading();
  }
}

function clearDetail(message) {
  state.selectedStockId = "";
  elements.detailEmpty.hidden = false;
  elements.detailBody.hidden = true;
  elements.detailEmpty.textContent = message;
  elements.fullDetailLink.hidden = true;
  renderRows();
}

function renderScoreGrid(score) {
  const metrics = [
    ["總分", score.buy_score],
    ["技術", score.technical_score],
    ["籌碼", score.chip_score],
    ["情緒", score.sentiment_score],
    ["風控", score.risk_score],
  ];
  elements.scoreGrid.innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${formatScore(value)}</strong></div>`)
    .join("");
}

function renderLocalModel(model) {
  if (!model.label) {
    elements.localModelPanel.innerHTML = `<h3>本地模型分析</h3><p>尚無模型分析資料</p>`;
    return;
  }
  elements.localModelPanel.innerHTML = `
    <div class="modelHeader">
      <h3>本地模型分析</h3>
      <span>${escapeHtml(model.label)} · 信心 ${formatScore(model.confidence)}%</span>
    </div>
    <div class="probGrid">
      <div class="isBull"><span>偏多</span><strong>${formatScore(model.bullish_probability)}%</strong></div>
      <div class="isNeutral"><span>中性</span><strong>${formatScore(model.neutral_probability)}%</strong></div>
      <div class="isBear"><span>偏空</span><strong>${formatScore(model.bearish_probability)}%</strong></div>
    </div>
    <ul class="evidenceList">${(model.evidence || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <p class="modelNote">${escapeHtml(model.note || "")}</p>
  `;
}

function renderIndicatorBreakdown(breakdown) {
  const groups = ["technical", "chip", "sentiment", "risk"];
  elements.indicatorBreakdown.innerHTML = groups
    .map((key) => {
      const group = breakdown[key];
      if (!group) return "";
      const items = group.indicators || [];
      return `<section class="breakdownGroup">
        <div class="breakdownHead">
          <h4>${escapeHtml(group.label)}</h4>
          <span>${formatScore(group.score)} · ${escapeHtml(group.direction)}</span>
        </div>
        <p>${escapeHtml(group.summary || "")}</p>
        ${items
          .map(
            (item) => `<div class="indicatorItem ${stateClassName(item.state)}">
              <div>
                <strong>${escapeHtml(item.label)}</strong>
                <span>${escapeHtml(item.explanation || "")}</span>
              </div>
              <div class="indicatorValue">
                <span>${formatIndicatorValue(item.value, item.unit)}</span>
                <b>${item.impact > 0 ? "+" : ""}${formatScore(item.impact)}</b>
              </div>
            </div>`
          )
          .join("")}
      </section>`;
    })
    .join("");
}

function renderNews(news) {
  if (!news.length) {
    elements.newsList.innerHTML = `<li><strong>無近期新聞/公告</strong><span>情緒分以中性處理</span></li>`;
    return;
  }
  elements.newsList.innerHTML = news
    .map(
      (item) => `<li><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.source || "-")} · ${escapeHtml(
        item.published_at || "-"
      )}</span></li>`
    )
    .join("");
}

function drawPriceChart(canvas, prices) {
  const ctx = prepareCanvas(canvas, 320);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!prices.length) {
    drawEmpty(ctx, canvas, "無價格資料");
    return;
  }
  const padding = { top: 24, right: 18, bottom: 34, left: 46 };
  const highs = prices.map((item) => item.high);
  const lows = prices.map((item) => item.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const priceRange = maxPrice - minPrice || 1;
  const chartWidth = canvas.width - padding.left - padding.right;
  const chartHeight = canvas.height - padding.top - padding.bottom;
  const candleWidth = Math.max(4, (chartWidth / prices.length) * 0.58);

  drawGrid(ctx, canvas, padding);
  prices.forEach((item, index) => {
    const x = padding.left + (index + 0.5) * (chartWidth / prices.length);
    const highY = padding.top + ((maxPrice - item.high) / priceRange) * chartHeight;
    const lowY = padding.top + ((maxPrice - item.low) / priceRange) * chartHeight;
    const openY = padding.top + ((maxPrice - item.open) / priceRange) * chartHeight;
    const closeY = padding.top + ((maxPrice - item.close) / priceRange) * chartHeight;
    const up = item.close >= item.open;
    ctx.strokeStyle = up ? chartColors.up : chartColors.down;
    ctx.fillStyle = up ? chartColors.upSoft : chartColors.downSoft;
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    const bodyY = Math.min(openY, closeY);
    const bodyHeight = Math.max(2, Math.abs(openY - closeY));
    ctx.fillRect(x - candleWidth / 2, bodyY, candleWidth, bodyHeight);
    ctx.strokeRect(x - candleWidth / 2, bodyY, candleWidth, bodyHeight);
  });
  drawAxisText(ctx, `${prices[0].date} - ${prices[prices.length - 1].date}`, padding.left, canvas.height - 10);
  drawAxisText(ctx, maxPrice.toFixed(2), 6, padding.top + 4);
  drawAxisText(ctx, minPrice.toFixed(2), 6, canvas.height - padding.bottom);
}

function drawFlowChart(canvas, flows, margins) {
  const ctx = prepareCanvas(canvas, 180);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!flows.length) {
    drawEmpty(ctx, canvas, "無籌碼資料");
    return;
  }
  const padding = { top: 22, right: 18, bottom: 28, left: 46 };
  const values = flows.map((item) => item.total_net);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const chartWidth = canvas.width - padding.left - padding.right;
  const chartHeight = canvas.height - padding.top - padding.bottom;
  const zeroY = padding.top + chartHeight / 2;
  drawGrid(ctx, canvas, padding);
  ctx.strokeStyle = chartColors.muted;
  ctx.beginPath();
  ctx.moveTo(padding.left, zeroY);
  ctx.lineTo(canvas.width - padding.right, zeroY);
  ctx.stroke();
  const barWidth = Math.max(4, (chartWidth / flows.length) * 0.62);
  flows.forEach((item, index) => {
    const x = padding.left + (index + 0.5) * (chartWidth / flows.length);
    const height = (Math.abs(item.total_net) / maxAbs) * (chartHeight / 2 - 8);
    ctx.fillStyle = item.total_net >= 0 ? chartColors.up : chartColors.down;
    ctx.fillRect(x - barWidth / 2, item.total_net >= 0 ? zeroY - height : zeroY, barWidth, height);
  });
  drawAxisText(ctx, "法人買賣超", padding.left, 15);
  if (margins.length) {
    drawAxisText(ctx, `融資餘額 ${Math.round(margins[margins.length - 1].margin_balance).toLocaleString()}`, canvas.width - 178, 15);
  }
}

function prepareCanvas(canvas, fallbackHeight) {
  const width = Math.max(320, Math.floor(canvas.clientWidth || canvas.width));
  const height = Math.floor(fallbackHeight || canvas.height);
  canvas.width = width;
  canvas.height = height;
  return canvas.getContext("2d");
}

function drawGrid(ctx, canvas, padding) {
  ctx.strokeStyle = chartColors.grid;
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding.top + i * ((canvas.height - padding.top - padding.bottom) / 3);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(canvas.width - padding.right, y);
    ctx.stroke();
  }
}

function drawAxisText(ctx, text, x, y) {
  ctx.fillStyle = chartColors.muted;
  ctx.font = "12px Segoe UI, Arial";
  ctx.fillText(text, x, y);
}

function drawEmpty(ctx, canvas, text) {
  ctx.fillStyle = chartColors.muted;
  ctx.font = "14px Segoe UI, Arial";
  ctx.fillText(text, 20, 36);
}

async function runScreener() {
  elements.refreshBtn.disabled = true;
  showLoading("更新市場資料中");
  elements.runMeta.textContent = "更新資料中";
  try {
    const payload = await fetchJson("/api/screener/run", {
      method: "POST",
      body: JSON.stringify({ mode: "manual", analysis_mode: state.analysisMode }),
    });
    elements.runMeta.textContent = `完成 ${payload.run_date}，來源 ${payload.source}，共 ${payload.count} 檔`;
    state.selectedStockId = "";
    await loadToday();
    await loadBacktest();
  } catch (error) {
    elements.runMeta.textContent = `更新失敗：${error.message}`;
  } finally {
    elements.refreshBtn.disabled = false;
    hideLoading();
  }
}

async function loadBacktest() {
  elements.backtestStrategy.textContent = "載入中";
  elements.backtestRows.innerHTML = Array.from({ length: 3 })
    .map(() => `<div class="backtestItem skeletonBlock"><span class="skeleton short"></span><span class="skeleton"></span><span class="skeleton"></span></div>`)
    .join("");
  try {
    const payload = await fetchJson(`/api/backtest?mode=${encodeURIComponent(state.analysisMode)}`);
    elements.backtestStrategy.textContent = payload.strategy || "-";
    elements.backtestRows.innerHTML = (payload.results || [])
      .map(
        (item) => `<div class="backtestItem">
          <strong>${item.horizon_days} 日</strong>
          <span>交易 ${item.trades} 筆</span>
          <span>勝率 ${item.win_rate}% · 平均 ${item.average_return}% · MDD ${item.max_drawdown}%</span>
        </div>`
      )
      .join("");
  } catch (error) {
    elements.backtestStrategy.textContent = `回測載入失敗：${error.message}`;
    elements.backtestRows.innerHTML = "";
  }
}

function setAnalysisMode(mode) {
  state.analysisMode = ["short", "swing", "long"].includes(mode) ? mode : "short";
  elements.modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.analysisMode);
  });
  state.selectedStockId = "";
  loadToday().then(loadBacktest);
}

function modeLabelText(mode) {
  if (mode === "swing") return "波段";
  if (mode === "long") return "長線";
  return "短線";
}

function initAnalysisMode() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("mode") || params.get("analysis_mode");
  if (["short", "swing", "long"].includes(requested)) {
    state.analysisMode = requested;
  }
  elements.modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.analysisMode);
  });
}

function decisionClassName(value) {
  if (value === "適合買入") return "buy";
  if (value === "觀察" || value === "等待拉回") return "watch";
  return "avoid";
}

function directionClassName(value) {
  if (value === "看多" || value === "偏多") return "bull";
  if (value === "偏空" || value === "看空") return "bear";
  return "flat";
}

function stateClassName(value) {
  if (value === "bullish" || value === "slightly_bullish") return "isBull";
  if (value === "bearish" || value === "slightly_bearish") return "isBear";
  return "isNeutral";
}

function formatIndicatorValue(value, unit) {
  if (value === null || value === undefined || value === "") return "-";
  const suffix = unit ? ` ${unit}` : "";
  return `${escapeHtml(value)}${escapeHtml(suffix)}`;
}

function formatScore(value) {
  return Number(value || 0).toFixed(1);
}

function formatPrice(value) {
  return Number(value || 0).toFixed(2);
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

elements.refreshBtn.addEventListener("click", runScreener);
elements.modeButtons.forEach((button) => {
  button.addEventListener("click", () => setAnalysisMode(button.dataset.mode));
});
[
  elements.industryFilter,
  elements.scoreFilter,
  elements.directionFilter,
  elements.adviceFilter,
  elements.volumeFilter,
  elements.techFilter,
  elements.chipScoreFilter,
  elements.sentimentFilter,
  elements.riskScoreFilter,
  elements.modelConfidenceFilter,
  elements.flowFilter,
  elements.riskFilter,
  elements.maFilter,
  elements.macdFilter,
  elements.volumeBreakoutFilter,
  elements.breakoutFilter,
  elements.sentimentPositiveFilter,
  elements.modelBullishFilter,
].forEach((element) => {
  element.addEventListener("change", loadToday);
});

initAnalysisMode();
loadToday().then(loadBacktest);
