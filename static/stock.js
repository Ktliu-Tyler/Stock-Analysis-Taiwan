const chartColors = {
  up: "#ff5d66",
  upSoft: "rgba(255, 93, 102, 0.26)",
  down: "#29c77a",
  downSoft: "rgba(41, 199, 122, 0.24)",
  accent: "#78b7ff",
  amber: "#f3b24e",
  teal: "#65d6c6",
  grid: "#253448",
  muted: "#8d9aae",
  ink: "#edf4ff",
};

const stockState = {
  report: null,
  stockId: "",
  analysisMode: "short",
  range: "90",
  chartType: "candle",
  indicator: "rsi",
  showMA5: true,
  showMA10: true,
  showMA20: true,
  showVolume: true,
  tool: "inspect",
  hoverIndex: null,
  selectedIndex: null,
  pendingTrend: null,
  drawings: [],
  chartArea: null,
  yScale: null,
};

const stockElements = {
  title: document.querySelector("#stockPageTitle"),
  meta: document.querySelector("#stockPageMeta"),
  aiLink: document.querySelector("#stockAiLink"),
  modeButtons: [...document.querySelectorAll("[data-stock-mode]")],
  chartStatus: document.querySelector("#chartStatus"),
  rangeSelect: document.querySelector("#rangeSelect"),
  chartTypeSelect: document.querySelector("#chartTypeSelect"),
  indicatorSelect: document.querySelector("#indicatorSelect"),
  ma5Toggle: document.querySelector("#ma5Toggle"),
  ma10Toggle: document.querySelector("#ma10Toggle"),
  ma20Toggle: document.querySelector("#ma20Toggle"),
  volumeToggle: document.querySelector("#volumeToggle"),
  inspectTool: document.querySelector("#inspectTool"),
  trendTool: document.querySelector("#trendTool"),
  clearDrawingsBtn: document.querySelector("#clearDrawingsBtn"),
  infoBar: document.querySelector("#chartInfoBar"),
  chart: document.querySelector("#stockChart"),
  indicatorChart: document.querySelector("#indicatorChart"),
  sideDecision: document.querySelector("#sideDecision"),
  sideDirection: document.querySelector("#sideDirection"),
  sideAdviceText: document.querySelector("#sideAdviceText"),
  scoreGrid: document.querySelector("#stockScoreGrid"),
  pricePlanMeta: document.querySelector("#pricePlanMeta"),
  entryPrice: document.querySelector("#entryPrice"),
  stopPrice: document.querySelector("#stopPrice"),
  targetZone: document.querySelector("#targetZone"),
  quickBuyMeta: document.querySelector("#quickBuyMeta"),
  quickBuyForm: document.querySelector("#quickBuyForm"),
  quickBuyPrice: document.querySelector("#quickBuyPrice"),
  quickBuyShares: document.querySelector("#quickBuyShares"),
  quickBuyHorizon: document.querySelector("#quickBuyHorizon"),
  quickBuyStatus: document.querySelector("#quickBuyStatus"),
  quickBuyBtn: document.querySelector("#quickBuyBtn"),
  buyReason: document.querySelector("#stockBuyReason"),
  avoidReason: document.querySelector("#stockAvoidReason"),
  breakdown: document.querySelector("#stockIndicatorBreakdown"),
  breakdownMeta: document.querySelector("#breakdownMeta"),
  newsList: document.querySelector("#stockNewsList"),
  newsMeta: document.querySelector("#newsMeta"),
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

async function initStockPage() {
  const params = new URLSearchParams(window.location.search);
  const stockId = params.get("id") || params.get("stock_id");
  stockState.stockId = stockId || "";
  stockState.analysisMode = normalizeMode(params.get("mode") || params.get("analysis_mode") || "short");
  updateModeButtons();
  if (!stockId) {
    stockElements.meta.textContent = "缺少股票代號";
    stockElements.chartStatus.textContent = "無資料";
    stockElements.infoBar.textContent = "請從首頁選擇股票並開啟完整圖表。";
    return;
  }
  showLoading(`載入 ${stockId} 完整分析`);
  try {
    const report = await fetchJson(`/api/stocks/${encodeURIComponent(stockId)}/report?mode=${encodeURIComponent(stockState.analysisMode)}`);
    if (report.error) {
      throw new Error(report.error);
    }
    stockState.report = report;
    renderStockPage();
  } catch (error) {
    stockElements.meta.textContent = `載入失敗：${error.message}`;
    stockElements.chartStatus.textContent = "載入失敗";
    stockElements.infoBar.textContent = error.message;
  } finally {
    hideLoading();
  }
}

function renderStockPage() {
  const report = stockState.report;
  const score = report.score || {};
  const details = score.details || {};
  const prices = report.prices || [];
  const latest = prices[prices.length - 1] || {};
  const modeLabel = details.analysis_mode_label || modeLabelText(stockState.analysisMode);
  stockElements.title.textContent = `${score.stock_id || ""} ${score.name || ""}`.trim() || "個股完整分析";
  stockElements.meta.textContent = `${modeLabel}模式 · ${score.industry || "-"} · ${score.market || "-"} · 最新資料 ${latest.date || score.data_freshness || "-"}`;
  stockElements.aiLink.href = `/ai.html?stock_id=${encodeURIComponent(score.stock_id || "")}&mode=${encodeURIComponent(stockState.analysisMode)}`;
  stockElements.chartStatus.textContent = `${prices.length} 筆價格資料`;
  renderSidePanels();
  prepareQuickBuy();
  renderBreakdown(details.indicator_breakdown || {});
  renderNews(report.news || []);
  renderCharts();
}

async function reloadForMode(mode) {
  stockState.analysisMode = normalizeMode(mode);
  stockState.hoverIndex = null;
  stockState.selectedIndex = null;
  stockState.pendingTrend = null;
  updateModeButtons();
  const url = new URL(window.location.href);
  url.searchParams.set("mode", stockState.analysisMode);
  window.history.replaceState({}, "", url);
  showLoading(`切換為${modeLabelText(stockState.analysisMode)}模式`);
  try {
    const report = await fetchJson(`/api/stocks/${encodeURIComponent(stockState.stockId)}/report?mode=${encodeURIComponent(stockState.analysisMode)}`);
    if (report.error) throw new Error(report.error);
    stockState.report = report;
    renderStockPage();
  } catch (error) {
    stockElements.meta.textContent = `切換失敗：${error.message}`;
  } finally {
    hideLoading();
  }
}

function visiblePrices() {
  const prices = (stockState.report?.prices || []).slice();
  if (stockState.range === "all") return prices;
  return prices.slice(-Number(stockState.range || 90));
}

function renderCharts() {
  const prices = visiblePrices();
  if (!prices.length) {
    drawEmptyChart(stockElements.chart, "無價格資料");
    drawEmptyChart(stockElements.indicatorChart, "無指標資料");
    return;
  }
  renderMainChart(prices);
  renderIndicatorChart(prices);
  const activeIndex = stockState.hoverIndex ?? stockState.selectedIndex ?? prices.length - 1;
  updateInfoBar(prices, activeIndex);
  updateToolbarState();
}

function renderMainChart(prices) {
  const canvas = stockElements.chart;
  const ctx = prepareCanvas(canvas, 620);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const padding = { top: 26, right: 76, bottom: 34, left: 62 };
  const volumeHeight = stockState.showVolume ? 118 : 0;
  const priceArea = {
    left: padding.left,
    right: canvas.width - padding.right,
    top: padding.top,
    bottom: canvas.height - padding.bottom - volumeHeight,
  };
  const volumeArea = {
    left: padding.left,
    right: canvas.width - padding.right,
    top: canvas.height - padding.bottom - volumeHeight + 18,
    bottom: canvas.height - padding.bottom,
  };
  const highs = prices.map((item) => Number(item.high || item.close || 0));
  const lows = prices.map((item) => Number(item.low || item.close || 0));
  let maxPrice = Math.max(...highs);
  let minPrice = Math.min(...lows);
  const pad = (maxPrice - minPrice || maxPrice * 0.04 || 1) * 0.08;
  maxPrice += pad;
  minPrice = Math.max(0, minPrice - pad);
  stockState.chartArea = priceArea;
  stockState.yScale = { min: minPrice, max: maxPrice };

  drawGrid(ctx, priceArea, 5, 4);
  drawPriceAxis(ctx, priceArea, minPrice, maxPrice);
  drawDateAxis(ctx, priceArea, prices);

  if (stockState.chartType === "line") {
    drawCloseLine(ctx, priceArea, prices, minPrice, maxPrice);
  } else {
    drawCandles(ctx, priceArea, prices, minPrice, maxPrice);
  }
  if (stockState.showMA5) drawMovingAverage(ctx, priceArea, prices, 5, chartColors.accent, minPrice, maxPrice);
  if (stockState.showMA10) drawMovingAverage(ctx, priceArea, prices, 10, chartColors.amber, minPrice, maxPrice);
  if (stockState.showMA20) drawMovingAverage(ctx, priceArea, prices, 20, chartColors.teal, minPrice, maxPrice);
  if (stockState.showVolume) drawVolume(ctx, volumeArea, prices);
  drawDrawings(ctx, priceArea, prices, minPrice, maxPrice);
  drawCrosshair(ctx, priceArea, prices, minPrice, maxPrice);
}

function renderIndicatorChart(prices) {
  const canvas = stockElements.indicatorChart;
  const ctx = prepareCanvas(canvas, 220);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const area = { left: 62, right: canvas.width - 76, top: 20, bottom: canvas.height - 30 };
  drawGrid(ctx, area, 3, 4);
  if (stockState.indicator === "macd") {
    drawMacd(ctx, area, prices);
  } else if (stockState.indicator === "flow") {
    drawFlow(ctx, area, prices);
  } else {
    drawRsi(ctx, area, prices);
  }
  drawDateAxis(ctx, area, prices);
}

function drawCandles(ctx, area, prices, minPrice, maxPrice) {
  const width = area.right - area.left;
  const candleWidth = Math.max(3, (width / prices.length) * 0.56);
  prices.forEach((item, index) => {
    const x = xForIndex(area, prices.length, index);
    const highY = yForPrice(area, item.high, minPrice, maxPrice);
    const lowY = yForPrice(area, item.low, minPrice, maxPrice);
    const openY = yForPrice(area, item.open, minPrice, maxPrice);
    const closeY = yForPrice(area, item.close, minPrice, maxPrice);
    const up = Number(item.close) >= Number(item.open);
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
}

function drawCloseLine(ctx, area, prices, minPrice, maxPrice) {
  ctx.strokeStyle = chartColors.accent;
  ctx.lineWidth = 2;
  ctx.beginPath();
  prices.forEach((item, index) => {
    const x = xForIndex(area, prices.length, index);
    const y = yForPrice(area, item.close, minPrice, maxPrice);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.lineWidth = 1;
}

function drawMovingAverage(ctx, area, prices, period, color, minPrice, maxPrice) {
  const values = movingAverage(prices.map((item) => Number(item.close)), period);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  values.forEach((value, index) => {
    if (value === null) return;
    const x = xForIndex(area, prices.length, index);
    const y = yForPrice(area, value, minPrice, maxPrice);
    if (!ctx._maStarted) {
      ctx.moveTo(x, y);
      ctx._maStarted = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx._maStarted = false;
  ctx.lineWidth = 1;
}

function drawVolume(ctx, area, prices) {
  const maxVolume = Math.max(1, ...prices.map((item) => Number(item.volume || 0)));
  const width = area.right - area.left;
  const barWidth = Math.max(2, (width / prices.length) * 0.6);
  drawGrid(ctx, area, 2, 4);
  prices.forEach((item, index) => {
    const x = xForIndex(area, prices.length, index);
    const height = (Number(item.volume || 0) / maxVolume) * (area.bottom - area.top);
    const up = Number(item.close) >= Number(item.open);
    ctx.fillStyle = up ? chartColors.upSoft : chartColors.downSoft;
    ctx.fillRect(x - barWidth / 2, area.bottom - height, barWidth, height);
  });
  drawText(ctx, "成交量", area.left, area.top - 5);
}

function drawRsi(ctx, area, prices) {
  const values = rsiSeries(prices.map((item) => Number(item.close)), 14);
  const yForRsi = (value) => area.bottom - (value / 100) * (area.bottom - area.top);
  ctx.strokeStyle = chartColors.amber;
  ctx.beginPath();
  values.forEach((value, index) => {
    if (value === null) return;
    const x = xForIndex(area, prices.length, index);
    const y = yForRsi(value);
    if (!ctx._rsiStarted) {
      ctx.moveTo(x, y);
      ctx._rsiStarted = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx._rsiStarted = false;
  ctx.strokeStyle = "rgba(243, 178, 78, 0.45)";
  [70, 50, 30].forEach((level) => {
    const y = yForRsi(level);
    ctx.beginPath();
    ctx.moveTo(area.left, y);
    ctx.lineTo(area.right, y);
    ctx.stroke();
    drawText(ctx, String(level), area.right + 8, y + 4);
  });
  drawText(ctx, "RSI 14", area.left, area.top - 5);
}

function drawMacd(ctx, area, prices) {
  const closes = prices.map((item) => Number(item.close));
  const macd = macdSeries(closes);
  const values = macd.histogram.filter((item) => item !== null);
  const maxAbs = Math.max(1, ...values.map((item) => Math.abs(item)));
  const zeroY = area.top + (area.bottom - area.top) / 2;
  const barWidth = Math.max(2, ((area.right - area.left) / prices.length) * 0.58);
  ctx.strokeStyle = chartColors.grid;
  ctx.beginPath();
  ctx.moveTo(area.left, zeroY);
  ctx.lineTo(area.right, zeroY);
  ctx.stroke();
  macd.histogram.forEach((value, index) => {
    if (value === null) return;
    const x = xForIndex(area, prices.length, index);
    const height = (Math.abs(value) / maxAbs) * ((area.bottom - area.top) / 2 - 8);
    ctx.fillStyle = value >= 0 ? chartColors.up : chartColors.down;
    ctx.fillRect(x - barWidth / 2, value >= 0 ? zeroY - height : zeroY, barWidth, height);
  });
  drawLineSeries(ctx, area, macd.line, -maxAbs, maxAbs, chartColors.accent);
  drawLineSeries(ctx, area, macd.signal, -maxAbs, maxAbs, chartColors.amber);
  drawText(ctx, "MACD", area.left, area.top - 5);
}

function drawFlow(ctx, area, prices) {
  const flowByDate = new Map((stockState.report?.institutional_flows || []).map((item) => [item.date, Number(item.total_net || 0)]));
  const values = prices.map((item) => flowByDate.get(item.date) || 0);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const zeroY = area.top + (area.bottom - area.top) / 2;
  const barWidth = Math.max(2, ((area.right - area.left) / prices.length) * 0.58);
  ctx.strokeStyle = chartColors.grid;
  ctx.beginPath();
  ctx.moveTo(area.left, zeroY);
  ctx.lineTo(area.right, zeroY);
  ctx.stroke();
  values.forEach((value, index) => {
    const x = xForIndex(area, prices.length, index);
    const height = (Math.abs(value) / maxAbs) * ((area.bottom - area.top) / 2 - 8);
    ctx.fillStyle = value >= 0 ? chartColors.up : chartColors.down;
    ctx.fillRect(x - barWidth / 2, value >= 0 ? zeroY - height : zeroY, barWidth, height);
  });
  drawText(ctx, "法人買賣超", area.left, area.top - 5);
}

function drawLineSeries(ctx, area, values, min, max, color) {
  ctx.strokeStyle = color;
  ctx.beginPath();
  values.forEach((value, index) => {
    if (value === null) return;
    const x = xForIndex(area, values.length, index);
    const y = area.bottom - ((value - min) / (max - min || 1)) * (area.bottom - area.top);
    if (!ctx._seriesStarted) {
      ctx.moveTo(x, y);
      ctx._seriesStarted = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx._seriesStarted = false;
}

function drawDrawings(ctx, area, prices, minPrice, maxPrice) {
  ctx.strokeStyle = chartColors.teal;
  ctx.lineWidth = 1.6;
  stockState.drawings.forEach((line) => {
    drawTrendLine(ctx, area, prices, minPrice, maxPrice, line.start, line.end);
  });
  if (stockState.pendingTrend) {
    const point = stockState.pendingTrend;
    const x = xForIndex(area, prices.length, point.index);
    const y = yForPrice(area, point.price, minPrice, maxPrice);
    ctx.fillStyle = chartColors.teal;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.lineWidth = 1;
}

function drawTrendLine(ctx, area, prices, minPrice, maxPrice, start, end) {
  const startX = xForIndex(area, prices.length, start.index);
  const startY = yForPrice(area, start.price, minPrice, maxPrice);
  const endX = xForIndex(area, prices.length, end.index);
  const endY = yForPrice(area, end.price, minPrice, maxPrice);
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(endX, endY);
  ctx.stroke();
}

function drawCrosshair(ctx, area, prices, minPrice, maxPrice) {
  const index = stockState.hoverIndex ?? stockState.selectedIndex;
  if (index === null || index < 0 || index >= prices.length) return;
  const item = prices[index];
  const x = xForIndex(area, prices.length, index);
  const y = yForPrice(area, item.close, minPrice, maxPrice);
  ctx.strokeStyle = "rgba(237, 244, 255, 0.45)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(x, area.top);
  ctx.lineTo(x, area.bottom);
  ctx.moveTo(area.left, y);
  ctx.lineTo(area.right, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = stockState.selectedIndex === index ? chartColors.accent : chartColors.ink;
  ctx.beginPath();
  ctx.arc(x, y, 4, 0, Math.PI * 2);
  ctx.fill();
}

function drawGrid(ctx, area, rows, columns) {
  ctx.strokeStyle = chartColors.grid;
  ctx.lineWidth = 1;
  for (let row = 0; row <= rows; row += 1) {
    const y = area.top + (row / rows) * (area.bottom - area.top);
    ctx.beginPath();
    ctx.moveTo(area.left, y);
    ctx.lineTo(area.right, y);
    ctx.stroke();
  }
  for (let column = 0; column <= columns; column += 1) {
    const x = area.left + (column / columns) * (area.right - area.left);
    ctx.beginPath();
    ctx.moveTo(x, area.top);
    ctx.lineTo(x, area.bottom);
    ctx.stroke();
  }
}

function drawPriceAxis(ctx, area, minPrice, maxPrice) {
  for (let i = 0; i <= 5; i += 1) {
    const value = maxPrice - (i / 5) * (maxPrice - minPrice);
    const y = area.top + (i / 5) * (area.bottom - area.top);
    drawText(ctx, value.toFixed(2), area.right + 8, y + 4);
  }
}

function drawDateAxis(ctx, area, prices) {
  if (!prices.length) return;
  const marks = [0, Math.floor(prices.length / 2), prices.length - 1];
  marks.forEach((index) => {
    const x = xForIndex(area, prices.length, index);
    drawText(ctx, prices[index].date, Math.min(x, area.right - 74), area.bottom + 20);
  });
}

function drawText(ctx, text, x, y) {
  ctx.fillStyle = chartColors.muted;
  ctx.font = "12px Segoe UI, Arial";
  ctx.fillText(text, x, y);
}

function drawEmptyChart(canvas, text) {
  const ctx = prepareCanvas(canvas, 360);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawText(ctx, text, 24, 40);
}

function xForIndex(area, length, index) {
  if (length <= 1) return area.left;
  return area.left + (index + 0.5) * ((area.right - area.left) / length);
}

function yForPrice(area, price, minPrice, maxPrice) {
  return area.bottom - ((Number(price) - minPrice) / (maxPrice - minPrice || 1)) * (area.bottom - area.top);
}

function priceForY(y) {
  const area = stockState.chartArea;
  const scale = stockState.yScale;
  if (!area || !scale) return 0;
  const ratio = (area.bottom - y) / (area.bottom - area.top);
  return scale.min + ratio * (scale.max - scale.min);
}

function indexForX(x, prices) {
  const area = stockState.chartArea;
  if (!area || !prices.length) return null;
  const step = (area.right - area.left) / prices.length;
  const index = Math.floor((x - area.left) / step);
  return Math.max(0, Math.min(prices.length - 1, index));
}

function prepareCanvas(canvas, fallbackHeight) {
  const width = Math.max(640, Math.floor(canvas.clientWidth || canvas.width));
  canvas.width = width;
  canvas.height = fallbackHeight;
  return canvas.getContext("2d");
}

function canvasPoint(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * canvas.width,
    y: ((event.clientY - rect.top) / rect.height) * canvas.height,
  };
}

function updateInfoBar(prices, index) {
  const item = prices[index];
  if (!item) return;
  const previous = prices[index - 1];
  const change = previous?.close ? ((item.close / previous.close - 1) * 100).toFixed(2) : "0.00";
  const sign = Number(change) >= 0 ? "+" : "";
  const pinned = stockState.selectedIndex === index ? " · 已固定" : "";
  stockElements.infoBar.innerHTML = `
    <strong>${escapeHtml(item.date)}</strong>
    開 ${formatPrice(item.open)}
    高 ${formatPrice(item.high)}
    低 ${formatPrice(item.low)}
    收 ${formatPrice(item.close)}
    量 ${formatNumber(item.volume)}
    漲跌 ${sign}${change}%${pinned}
  `;
}

function renderSidePanels() {
  const score = stockState.report.score || {};
  const details = score.details || {};
  stockElements.sideDecision.textContent = score.decision || "-";
  stockElements.sideDirection.textContent = details.direction || "-";
  stockElements.sideDirection.className = directionClassName(details.direction || "");
  stockElements.sideAdviceText.textContent = details.investment_advice || "";
  stockElements.pricePlanMeta.textContent = score.data_freshness || "-";
  stockElements.entryPrice.textContent = formatPrice(score.entry_watch_price);
  stockElements.stopPrice.textContent = formatPrice(score.stop_loss_price);
  stockElements.targetZone.textContent = score.target_zone || "-";
  stockElements.buyReason.textContent = score.buy_reason || "-";
  stockElements.avoidReason.textContent = score.avoid_reason || "-";
  const metrics = [
    ["總分", score.buy_score],
    ["技術", score.technical_score],
    ["籌碼", score.chip_score],
    ["情緒", score.sentiment_score],
    ["風控", score.risk_score],
  ];
  stockElements.scoreGrid.innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${formatScore(value)}</strong></div>`)
    .join("");
}

function prepareQuickBuy() {
  const score = stockState.report.score || {};
  const details = score.details || {};
  stockElements.quickBuyPrice.value = formatPrice(score.entry_watch_price || details.latest_price || 0);
  stockElements.quickBuyHorizon.value = details.portfolio_horizon || portfolioHorizonForMode(stockState.analysisMode);
  stockElements.quickBuyMeta.textContent = `${modeLabelText(stockState.analysisMode)} / ${stockElements.quickBuyHorizon.value}`;
}

async function quickAddPosition(event) {
  event.preventDefault();
  const score = stockState.report?.score || {};
  if (!score.stock_id) return;
  stockElements.quickBuyBtn.disabled = true;
  stockElements.quickBuyBtn.textContent = "加入中";
  showLoading("加入持股觀察");
  try {
    await fetchJson("/api/portfolio", {
      method: "POST",
      body: JSON.stringify({
        stock_id: score.stock_id,
        name: score.name,
        shares: stockElements.quickBuyShares.value,
        average_cost: stockElements.quickBuyPrice.value,
        buy_date: new Date().toISOString().slice(0, 10),
        position_status: stockElements.quickBuyStatus.value,
        horizon: stockElements.quickBuyHorizon.value,
        risk_profile: "中等",
        notes: `${modeLabelText(stockState.analysisMode)}模式從個股頁加入。觀察價 ${formatPrice(score.entry_watch_price)}，停損 ${formatPrice(score.stop_loss_price)}。`,
      }),
    });
    stockElements.quickBuyMeta.textContent = "已加入持股觀察";
    stockElements.quickBuyShares.value = "";
  } catch (error) {
    stockElements.quickBuyMeta.textContent = `加入失敗：${error.message}`;
  } finally {
    stockElements.quickBuyBtn.disabled = false;
    stockElements.quickBuyBtn.textContent = "加入持股觀察";
    hideLoading();
  }
}

function renderBreakdown(breakdown) {
  const groups = ["technical", "chip", "sentiment", "risk"];
  stockElements.breakdownMeta.textContent = groups.filter((key) => breakdown[key]).length ? "已整理" : "無資料";
  stockElements.breakdown.innerHTML = groups
    .map((key) => {
      const group = breakdown[key];
      if (!group) return "";
      return `<section class="breakdownGroup">
        <div class="breakdownHead">
          <h4>${escapeHtml(group.label)}</h4>
          <span>${formatScore(group.score)} · ${escapeHtml(group.direction)}</span>
        </div>
        <p>${escapeHtml(group.summary || "")}</p>
        ${(group.indicators || [])
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
  stockElements.newsMeta.textContent = `${news.length} 筆`;
  if (!news.length) {
    stockElements.newsList.innerHTML = `<li><strong>無近期新聞/公告</strong><span>情緒分以中性處理</span></li>`;
    return;
  }
  stockElements.newsList.innerHTML = news
    .map(
      (item) => `<li><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.source || "-")} · ${escapeHtml(
        item.published_at || "-"
      )}</span></li>`
    )
    .join("");
}

function onChartMove(event) {
  const prices = visiblePrices();
  const point = canvasPoint(event, stockElements.chart);
  const index = indexForX(point.x, prices);
  if (index === null) return;
  stockState.hoverIndex = index;
  renderCharts();
}

function onChartLeave() {
  stockState.hoverIndex = null;
  renderCharts();
}

function onChartClick(event) {
  const prices = visiblePrices();
  const point = canvasPoint(event, stockElements.chart);
  const index = indexForX(point.x, prices);
  if (index === null) return;
  if (stockState.tool === "trend") {
    const price = priceForY(point.y);
    const nextPoint = { index, price };
    if (!stockState.pendingTrend) {
      stockState.pendingTrend = nextPoint;
    } else {
      stockState.drawings.push({ start: stockState.pendingTrend, end: nextPoint });
      stockState.pendingTrend = null;
    }
  } else {
    stockState.selectedIndex = index;
  }
  renderCharts();
}

function movingAverage(values, period) {
  return values.map((_, index) => {
    if (index + 1 < period) return null;
    const slice = values.slice(index + 1 - period, index + 1);
    return slice.reduce((sum, value) => sum + value, 0) / period;
  });
}

function rsiSeries(values, period = 14) {
  return values.map((_, index) => {
    if (index < period) return null;
    let gains = 0;
    let losses = 0;
    for (let offset = index - period + 1; offset <= index; offset += 1) {
      const diff = values[offset] - values[offset - 1];
      if (diff >= 0) gains += diff;
      else losses += Math.abs(diff);
    }
    if (!losses) return 100;
    const rs = gains / period / (losses / period);
    return 100 - 100 / (1 + rs);
  });
}

function emaSeries(values, period) {
  const alpha = 2 / (period + 1);
  let previous = null;
  return values.map((value, index) => {
    if (index === 0) {
      previous = value;
      return value;
    }
    previous = value * alpha + previous * (1 - alpha);
    return previous;
  });
}

function macdSeries(values) {
  const ema12 = emaSeries(values, 12);
  const ema26 = emaSeries(values, 26);
  const line = values.map((_, index) => ema12[index] - ema26[index]);
  const signal = emaSeries(line, 9);
  const histogram = line.map((value, index) => value - signal[index]);
  return { line, signal, histogram };
}

function updateToolbarState() {
  toggleActive(stockElements.ma5Toggle, stockState.showMA5);
  toggleActive(stockElements.ma10Toggle, stockState.showMA10);
  toggleActive(stockElements.ma20Toggle, stockState.showMA20);
  toggleActive(stockElements.volumeToggle, stockState.showVolume);
  toggleActive(stockElements.inspectTool, stockState.tool === "inspect");
  toggleActive(stockElements.trendTool, stockState.tool === "trend");
}

function toggleActive(button, active) {
  button.classList.toggle("activeTool", active);
}

function updateModeButtons() {
  stockElements.modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.stockMode === stockState.analysisMode);
  });
}

function normalizeMode(mode) {
  return ["short", "swing", "long"].includes(mode) ? mode : "short";
}

function modeLabelText(mode) {
  if (mode === "swing") return "波段";
  if (mode === "long") return "長線";
  return "短線";
}

function portfolioHorizonForMode(mode) {
  if (mode === "swing") return "中期";
  if (mode === "long") return "長期";
  return "短期";
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

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 0 });
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

stockElements.rangeSelect.addEventListener("change", () => {
  stockState.range = stockElements.rangeSelect.value;
  stockState.hoverIndex = null;
  stockState.selectedIndex = null;
  stockState.pendingTrend = null;
  renderCharts();
});
stockElements.chartTypeSelect.addEventListener("change", () => {
  stockState.chartType = stockElements.chartTypeSelect.value;
  renderCharts();
});
stockElements.indicatorSelect.addEventListener("change", () => {
  stockState.indicator = stockElements.indicatorSelect.value;
  renderCharts();
});
stockElements.ma5Toggle.addEventListener("click", () => {
  stockState.showMA5 = !stockState.showMA5;
  renderCharts();
});
stockElements.ma10Toggle.addEventListener("click", () => {
  stockState.showMA10 = !stockState.showMA10;
  renderCharts();
});
stockElements.ma20Toggle.addEventListener("click", () => {
  stockState.showMA20 = !stockState.showMA20;
  renderCharts();
});
stockElements.volumeToggle.addEventListener("click", () => {
  stockState.showVolume = !stockState.showVolume;
  renderCharts();
});
stockElements.inspectTool.addEventListener("click", () => {
  stockState.tool = "inspect";
  stockState.pendingTrend = null;
  renderCharts();
});
stockElements.trendTool.addEventListener("click", () => {
  stockState.tool = "trend";
  renderCharts();
});
stockElements.clearDrawingsBtn.addEventListener("click", () => {
  stockState.drawings = [];
  stockState.pendingTrend = null;
  renderCharts();
});
stockElements.modeButtons.forEach((button) => {
  button.addEventListener("click", () => reloadForMode(button.dataset.stockMode));
});
stockElements.quickBuyForm.addEventListener("submit", quickAddPosition);
stockElements.chart.addEventListener("mousemove", onChartMove);
stockElements.chart.addEventListener("mouseleave", onChartLeave);
stockElements.chart.addEventListener("click", onChartClick);
window.addEventListener("resize", () => {
  if (stockState.report) renderCharts();
});

initStockPage();
