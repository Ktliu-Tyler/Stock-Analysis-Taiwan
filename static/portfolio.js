const portfolioState = {
  positions: [],
};

const portfolioElements = {
  meta: document.querySelector("#portfolioMeta"),
  summary: document.querySelector("#portfolioSummary"),
  form: document.querySelector("#positionForm"),
  stockIdInput: document.querySelector("#stockIdInput"),
  stockNameInput: document.querySelector("#stockNameInput"),
  sharesInput: document.querySelector("#sharesInput"),
  averageCostInput: document.querySelector("#averageCostInput"),
  buyDateInput: document.querySelector("#buyDateInput"),
  positionStatus: document.querySelector("#positionStatus"),
  horizonInput: document.querySelector("#horizonInput"),
  riskProfile: document.querySelector("#riskProfile"),
  notesInput: document.querySelector("#notesInput"),
  savePositionBtn: document.querySelector("#savePositionBtn"),
  positionCount: document.querySelector("#positionCount"),
  positionRows: document.querySelector("#positionRows"),
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

async function loadPortfolio() {
  showLoading("載入持股紀錄");
  renderPortfolioSkeleton();
  try {
    const payload = await fetchJson("/api/portfolio");
    portfolioState.positions = payload.items || [];
    renderSummary(payload.summary || {});
    renderPositions();
  } catch (error) {
    portfolioElements.meta.textContent = `載入失敗：${error.message}`;
    portfolioElements.positionRows.innerHTML = `<tr><td colspan="8">載入失敗：${escapeHtml(error.message)}</td></tr>`;
  } finally {
    hideLoading();
  }
}

function renderPortfolioSkeleton() {
  portfolioElements.summary.innerHTML = Array.from({ length: 4 })
    .map(() => `<div class="summaryItem skeletonBlock"><span class="skeleton short"></span><strong><span class="skeleton"></span></strong></div>`)
    .join("");
  portfolioElements.positionRows.innerHTML = Array.from({ length: 5 })
    .map(
      () => `<tr class="skeletonRow">
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton tiny"></span></td>
        <td><span class="skeleton short"></span></td>
        <td><span class="skeleton short"></span></td>
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton"></span></td>
        <td><span class="skeleton short"></span></td>
      </tr>`
    )
    .join("");
}

function renderSummary(summary) {
  portfolioElements.meta.textContent = `目前 ${summary.positions || 0} 筆持股，未實現損益 ${formatMoney(summary.unrealized_pnl)} (${formatPct(summary.unrealized_pnl_pct)})`;
  portfolioElements.summary.innerHTML = `
    <div class="summaryItem"><span>總成本</span><strong>${formatMoney(summary.total_cost)}</strong></div>
    <div class="summaryItem"><span>目前市值</span><strong>${formatMoney(summary.total_value)}</strong></div>
    <div class="summaryItem ${Number(summary.unrealized_pnl || 0) >= 0 ? "profit" : "loss"}"><span>未實現損益</span><strong>${formatMoney(summary.unrealized_pnl)}</strong></div>
    <div class="summaryItem ${Number(summary.unrealized_pnl_pct || 0) >= 0 ? "profit" : "loss"}"><span>損益率</span><strong>${formatPct(summary.unrealized_pnl_pct)}</strong></div>
  `;
}

function renderPositions() {
  portfolioElements.positionCount.textContent = `${portfolioState.positions.length} 筆`;
  if (!portfolioState.positions.length) {
    portfolioElements.positionRows.innerHTML = `<tr><td colspan="8">尚未加入持股</td></tr>`;
    return;
  }
  portfolioElements.positionRows.innerHTML = portfolioState.positions
    .map((item) => {
      const pnlClass = Number(item.unrealized_pnl || 0) >= 0 ? "profitText" : "lossText";
      return `<tr>
        <td><div class="stockName"><strong>${escapeHtml(item.stock_id)} ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.buy_date || "-")}</span></div></td>
        <td>${formatNumber(item.shares)}</td>
        <td>${formatPrice(item.average_cost)}</td>
        <td>${formatPrice(item.latest_price)}</td>
        <td>${formatMoney(item.market_value)}</td>
        <td class="${pnlClass}">${formatMoney(item.unrealized_pnl)}<span class="subValue">${formatPct(item.unrealized_pnl_pct)}</span></td>
        <td>${escapeHtml(item.position_status)}<span class="subValue">${escapeHtml(item.horizon)} · ${escapeHtml(item.risk_profile)}</span></td>
        <td class="rowActions">
          <a class="buttonLink secondary" href="/ai.html?position_id=${encodeURIComponent(item.id)}">AI</a>
          <button type="button" class="danger" data-delete="${item.id}">刪除</button>
        </td>
      </tr>`;
    })
    .join("");
  document.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", () => deletePosition(button.dataset.delete));
  });
}

async function savePosition(event) {
  event.preventDefault();
  portfolioElements.savePositionBtn.disabled = true;
  portfolioElements.savePositionBtn.textContent = "加入中";
  showLoading("新增持股中");
  try {
    await fetchJson("/api/portfolio", {
      method: "POST",
      body: JSON.stringify(readForm()),
    });
    portfolioElements.form.reset();
    setDefaultDate();
    await loadPortfolio();
  } catch (error) {
    portfolioElements.meta.textContent = `加入失敗：${error.message}`;
  } finally {
    portfolioElements.savePositionBtn.disabled = false;
    portfolioElements.savePositionBtn.textContent = "加入持股";
    hideLoading();
  }
}

async function deletePosition(positionId) {
  showLoading("刪除持股中");
  try {
    await fetchJson(`/api/portfolio/${encodeURIComponent(positionId)}/delete`, { method: "POST", body: "{}" });
    await loadPortfolio();
  } catch (error) {
    portfolioElements.meta.textContent = `刪除失敗：${error.message}`;
  } finally {
    hideLoading();
  }
}

function readForm() {
  return {
    stock_id: portfolioElements.stockIdInput.value.trim(),
    name: portfolioElements.stockNameInput.value.trim(),
    shares: portfolioElements.sharesInput.value,
    average_cost: portfolioElements.averageCostInput.value,
    buy_date: portfolioElements.buyDateInput.value,
    position_status: portfolioElements.positionStatus.value,
    horizon: portfolioElements.horizonInput.value,
    risk_profile: portfolioElements.riskProfile.value,
    notes: portfolioElements.notesInput.value,
  };
}

function setDefaultDate() {
  portfolioElements.buyDateInput.value = new Date().toISOString().slice(0, 10);
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function formatPrice(value) {
  return Number(value || 0).toFixed(2);
}

function formatPct(value) {
  return `${Number(value || 0).toFixed(2)}%`;
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

portfolioElements.form.addEventListener("submit", savePosition);
setDefaultDate();
loadPortfolio();
