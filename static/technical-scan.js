const state = {
  jobId: "",
  timer: null,
};

const elements = {
  scanMeta: document.querySelector("#scanMeta"),
  marketSelect: document.querySelector("#marketSelect"),
  limitSelect: document.querySelector("#limitSelect"),
  daysInput: document.querySelector("#daysInput"),
  minVolumeInput: document.querySelector("#minVolumeInput"),
  bollingerModeSelect: document.querySelector("#bollingerModeSelect"),
  macdWeakeningCheck: document.querySelector("#macdWeakeningCheck"),
  kdjPreCrossCheck: document.querySelector("#kdjPreCrossCheck"),
  startScanBtn: document.querySelector("#startScanBtn"),
  progressBar: document.querySelector("#progressBar"),
  scanStatus: document.querySelector("#scanStatus"),
  scannedCount: document.querySelector("#scannedCount"),
  matchedCount: document.querySelector("#matchedCount"),
  unmatchedCount: document.querySelector("#unmatchedCount"),
  failedCount: document.querySelector("#failedCount"),
  currentScanText: document.querySelector("#currentScanText"),
  resultMeta: document.querySelector("#resultMeta"),
  technicalRows: document.querySelector("#technicalRows"),
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

function scanConfig() {
  return {
    market: elements.marketSelect.value,
    limit: Number(elements.limitSelect.value || 0),
    days: Number(elements.daysInput.value || 180),
    min_volume: Number(elements.minVolumeInput.value || 0),
    bollinger_mode: elements.bollingerModeSelect.value,
    require_macd_bearish_weakening: elements.macdWeakeningCheck.checked,
    require_kdj_pre_golden_cross: elements.kdjPreCrossCheck.checked,
  };
}

async function startScan() {
  elements.startScanBtn.disabled = true;
  elements.technicalRows.innerHTML = `<tr><td colspan="9">正在建立直接 API 掃描工作</td></tr>`;
  updateProgress({ status: "queued", progress: { scanned: 0, total: 0, matched: 0, unmatched: 0, failed: 0, current: "" }, results: [] });
  try {
    const job = await fetchJson("/api/technical-scanner/run", {
      method: "POST",
      body: JSON.stringify(scanConfig()),
    });
    state.jobId = job.job_id;
    updateProgress(job);
    state.timer = window.setInterval(pollJob, 1800);
    await pollJob();
  } catch (error) {
    elements.startScanBtn.disabled = false;
    elements.scanStatus.textContent = "失敗";
    elements.currentScanText.textContent = `無法開始掃描：${error.message}`;
  }
}

async function pollJob() {
  if (!state.jobId) {
    return;
  }
  try {
    const job = await fetchJson(`/api/technical-scanner/jobs/${encodeURIComponent(state.jobId)}`);
    updateProgress(job);
    if (job.status === "completed" || job.status === "failed") {
      window.clearInterval(state.timer);
      state.timer = null;
      elements.startScanBtn.disabled = false;
    }
  } catch (error) {
    window.clearInterval(state.timer);
    state.timer = null;
    elements.startScanBtn.disabled = false;
    elements.scanStatus.textContent = "失敗";
    elements.currentScanText.textContent = `讀取掃描進度失敗：${error.message}`;
  }
}

function updateProgress(job) {
  const progress = job.progress || {};
  const scanned = Number(progress.scanned || 0);
  const total = Number(progress.total || 0);
  const matched = Number(progress.matched || (job.results || []).length || 0);
  const failed = Number(progress.failed || 0);
  const unmatched = Number(progress.unmatched ?? Math.max(0, scanned - matched - failed));
  const ratio = total ? Math.min(100, Math.round((scanned / total) * 100)) : 0;
  elements.progressBar.style.width = `${ratio}%`;
  elements.scanStatus.textContent = statusLabel(job.status || "queued");
  elements.scannedCount.textContent = `${scanned} / ${total}`;
  elements.matchedCount.textContent = matched.toString();
  elements.unmatchedCount.textContent = unmatched.toString();
  elements.failedCount.textContent = failed.toString();
  elements.currentScanText.textContent = progress.current
    ? `正在掃描：${progress.current}`
    : job.message || "等待掃描";
  const results = job.results || [];
  elements.resultMeta.textContent = job.status === "completed" ? `${results.length} 檔符合條件` : `目前 ${results.length} 檔符合`;
  elements.scanMeta.textContent = job.universe_source
    ? `直接 API · ${job.data_policy || "direct_api_only"} · ${job.universe_source} · ${job.run_at || ""}`
    : "直接 API 掃描日線 KDJ、MACD、布林訊號";
  renderRows(results);
}

function renderRows(results) {
  if (!results.length) {
    elements.technicalRows.innerHTML = `<tr><td colspan="9">目前沒有符合條件的股票</td></tr>`;
    return;
  }
  elements.technicalRows.innerHTML = results
    .map((item) => {
      const indicators = item.indicators || {};
      const reasons = (item.reasons || []).map((reason) => `<span class="reasonPill">${escapeHtml(reason)}</span>`).join("");
      const stockLink = `/stock.html?id=${encodeURIComponent(item.stock_id)}&mode=short`;
      return `<tr>
        <td><a class="stockCellLink" href="${stockLink}"><strong>${escapeHtml(item.stock_id)} ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.industry || "")}</span></a></td>
        <td class="score">${formatNumber(item.pattern_score)}</td>
        <td>${formatNumber(item.close)}</td>
        <td>${formatNumber(indicators.kdj_k)} / ${formatNumber(indicators.kdj_d)} / ${formatNumber(indicators.kdj_gap)}</td>
        <td>${formatNumber(indicators.macd_histogram)} <span class="mutedText">前 ${formatNumber(indicators.macd_previous_histogram)}</span></td>
        <td>${formatNumber(indicators.bollinger_percent_b)}%</td>
        <td>${formatNumber(indicators.volume_ratio)}</td>
        <td><div class="reasonList">${reasons}</div></td>
        <td>${escapeHtml(item.latest_date || "")}</td>
      </tr>`;
    })
    .join("");
}

function statusLabel(status) {
  return {
    queued: "排隊中",
    running: "掃描中",
    completed: "完成",
    failed: "失敗",
  }[status] || status;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.startScanBtn.addEventListener("click", startScan);
