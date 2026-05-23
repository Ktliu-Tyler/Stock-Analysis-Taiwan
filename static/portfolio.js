const portfolioState = {
  positions: [],
  horizonFilter: "all",
  sellingId: "",
};

const portfolioElements = {
  meta: document.querySelector("#portfolioMeta"),
  summary: document.querySelector("#portfolioSummary"),
  groups: document.querySelector("#portfolioGroups"),
  horizonButtons: [...document.querySelectorAll("[data-horizon-filter]")],
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
  portfolioElements.meta.textContent = `目前 ${summary.positions || 0} 筆持股，已賣出 ${summary.closed_positions || 0} 筆，未實現損益 ${formatMoney(summary.unrealized_pnl)} (${formatPct(summary.unrealized_pnl_pct)})`;
  portfolioElements.summary.innerHTML = `
    <div class="summaryItem"><span>總成本</span><strong>${formatMoney(summary.total_cost)}</strong></div>
    <div class="summaryItem"><span>目前市值</span><strong>${formatMoney(summary.total_value)}</strong></div>
    <div class="summaryItem ${Number(summary.unrealized_pnl || 0) >= 0 ? "profit" : "loss"}"><span>未實現損益</span><strong>${formatMoney(summary.unrealized_pnl)}</strong></div>
    <div class="summaryItem ${Number(summary.realized_pnl || 0) >= 0 ? "profit" : "loss"}"><span>已實現損益</span><strong>${formatMoney(summary.realized_pnl)}</strong></div>
  `;
  renderGroups(summary.by_horizon || {});
}

function renderGroups(groups) {
  const order = ["短期", "中期", "長期"];
  portfolioElements.groups.innerHTML = order
    .map((key) => {
      const item = groups[key] || { label: key, positions: 0, market_value: 0, unrealized_pnl: 0 };
      const pnlClass = Number(item.unrealized_pnl || 0) >= 0 ? "profitText" : "lossText";
      return `<button type="button" class="groupCard ${portfolioState.horizonFilter === key ? "active" : ""}" data-group-filter="${key}">
        <span>${escapeHtml(item.label || key)}</span>
        <strong>${item.positions || 0} 筆</strong>
        <small>市值 ${formatMoney(item.market_value)} · <b class="${pnlClass}">${formatMoney(item.unrealized_pnl)}</b></small>
      </button>`;
    })
    .join("");
  document.querySelectorAll("[data-group-filter]").forEach((button) => {
    button.addEventListener("click", () => setHorizonFilter(button.dataset.groupFilter));
  });
}

function renderPositions() {
  const filtered = portfolioState.horizonFilter === "all"
    ? portfolioState.positions
    : portfolioState.positions.filter((item) => item.horizon_category === portfolioState.horizonFilter);
  portfolioElements.positionCount.textContent = `${filtered.length} 筆`;
  if (!filtered.length) {
    portfolioElements.positionRows.innerHTML = `<tr><td colspan="8">尚未加入持股</td></tr>`;
    return;
  }
  portfolioElements.positionRows.innerHTML = filtered
    .map((item) => {
      const closed = Boolean(item.closed);
      const pnl = closed ? item.realized_pnl : item.unrealized_pnl;
      const pnlPct = closed ? item.realized_pnl_pct : item.unrealized_pnl_pct;
      const pnlClass = Number(pnl || 0) >= 0 ? "profitText" : "lossText";
      const sellRow = portfolioState.sellingId === String(item.id) ? renderSellRow(item) : "";
      return `<tr class="${closed ? "closedPosition" : ""}">
        <td><div class="stockName"><strong>${escapeHtml(item.stock_id)} ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.buy_date || "-")}</span></div></td>
        <td>${formatNumber(item.shares)}</td>
        <td>${formatPrice(item.average_cost)}</td>
        <td>${formatPrice(item.latest_price)}</td>
        <td>${formatMoney(item.market_value)}</td>
        <td class="${pnlClass}">${formatMoney(pnl)}<span class="subValue">${formatPct(pnlPct)}${closed ? " · 已實現" : ""}</span></td>
        <td><span class="horizonPill">${escapeHtml(item.horizon_category || item.horizon)}</span>${escapeHtml(item.position_status)}<span class="subValue">${escapeHtml(item.risk_profile)}</span></td>
        <td class="rowActions">
          <a class="buttonLink secondary" href="/ai.html?position_id=${encodeURIComponent(item.id)}">AI</a>
          ${closed ? "" : `<button type="button" class="secondary" data-sell="${item.id}">賣出</button>`}
          <button type="button" class="danger" data-delete="${item.id}">刪除</button>
        </td>
      </tr>${sellRow}`;
    })
    .join("");
  document.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", () => deletePosition(button.dataset.delete));
  });
  document.querySelectorAll("[data-sell]").forEach((button) => {
    button.addEventListener("click", () => {
      portfolioState.sellingId = portfolioState.sellingId === String(button.dataset.sell) ? "" : String(button.dataset.sell);
      renderPositions();
    });
  });
  document.querySelectorAll("[data-confirm-sell]").forEach((button) => {
    button.addEventListener("click", () => sellPosition(button.dataset.confirmSell));
  });
}

function renderSellRow(item) {
  return `<tr class="sellEditorRow">
    <td colspan="8">
      <div class="sellEditor">
        <label>賣出價<input id="sellPrice-${item.id}" type="number" min="0" step="0.01" value="${formatPrice(item.latest_price || item.average_cost)}" /></label>
        <label>賣出股數<input id="sellShares-${item.id}" type="number" min="1" step="1" value="${formatNumberRaw(item.shares)}" /></label>
        <label>賣出日期<input id="sellDate-${item.id}" type="date" value="${new Date().toISOString().slice(0, 10)}" /></label>
        <button type="button" data-confirm-sell="${item.id}">確認賣出</button>
      </div>
    </td>
  </tr>`;
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

async function sellPosition(positionId) {
  const priceInput = document.querySelector(`#sellPrice-${CSS.escape(String(positionId))}`);
  const sharesInput = document.querySelector(`#sellShares-${CSS.escape(String(positionId))}`);
  const dateInput = document.querySelector(`#sellDate-${CSS.escape(String(positionId))}`);
  showLoading("更新賣出紀錄");
  try {
    await fetchJson(`/api/portfolio/${encodeURIComponent(positionId)}/sell`, {
      method: "POST",
      body: JSON.stringify({
        sell_price: priceInput?.value,
        sell_shares: sharesInput?.value,
        sell_date: dateInput?.value,
      }),
    });
    portfolioState.sellingId = "";
    await loadPortfolio();
  } catch (error) {
    portfolioElements.meta.textContent = `賣出失敗：${error.message}`;
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

function setHorizonFilter(value) {
  portfolioState.horizonFilter = value || "all";
  portfolioState.sellingId = "";
  portfolioElements.horizonButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.horizonFilter === portfolioState.horizonFilter);
  });
  document.querySelectorAll("[data-group-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.groupFilter === portfolioState.horizonFilter);
  });
  renderPositions();
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

function formatNumberRaw(value) {
  return String(Math.round(Number(value || 0)));
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
portfolioElements.horizonButtons.forEach((button) => {
  button.addEventListener("click", () => setHorizonFilter(button.dataset.horizonFilter));
});
setDefaultDate();
loadPortfolio();
