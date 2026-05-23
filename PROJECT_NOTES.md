# 專案注意事項與穩定性檢查

最後整理日期：2026-05-24

## 本輪檢查結論

目前專案主流程可以正常運作：

- 首頁篩選儀表板可載入正式掃描資料。
- 個股完整分析頁可顯示互動 K 線、價量、技術指標與趨勢線工具。
- 持股紀錄可新增、刪除並計算未實現損益。
- AI 分析頁可連線到本機 Ollama 狀態 API。
- 公開網站流程已移除示範資料模式。
- `/api/...` 未知路由會回 JSON 404，不再 fallback 成首頁。
- server 已處理瀏覽器中斷連線造成的 `ConnectionAbortedError` / `BrokenPipeError` 類雜訊。

本輪驗證項目：

```powershell
python -m unittest discover -s tests
python -m compileall app
node --check static\app.js
node --check static\ai.js
node --check static\portfolio.js
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

目前測試結果：12 個單元測試通過。

## 程式流程整理

### 啟動流程

1. `run_app.py` 呼叫 `app.server.main()`。
2. `server.py` 建立 `ScreenerService`、`PortfolioService`、`AIAnalysisService`。
3. HTTP server 開在 `127.0.0.1:8000`。
4. 靜態頁面由 `static/` 提供。
5. API 由 `server.py` route 到對應 service。

### 資料更新流程

1. 前端按下 `更新資料`。
2. `POST /api/screener/run` 呼叫 `ScreenerService.run(use_demo=False)`。
3. `MarketDataClient` 選出股票池。
4. 系統抓日線、法人買賣超、融資融券、新聞。
5. 寫入 SQLite。
6. `score_universe()` 計算分數。
7. 前端重新讀取 `/api/screener/today`。

### 單檔分析流程

1. 使用者點選股票。
2. 前端呼叫 `/api/stocks/{stock_id}/report`。
3. 後端回傳分數、價格、籌碼、融資融券、新聞與 signals。
4. 前端畫摘要 K 線、法人柱狀圖、指標拆解與風控資訊。
5. 使用者可從摘要面板開啟 `/stock.html?id={stock_id}` 查看完整互動圖表。

### 個股完整圖表流程

1. 使用者從首頁點擊 `完整圖表`。
2. `stock.html` 讀取 query string 中的股票代號。
3. `stock.js` 呼叫 `/api/stocks/{stock_id}/report`。
4. 前端用 canvas 繪製 K 線、收盤線、成交量、MA、RSI、MACD、法人買賣超。
5. 使用者可用十字游標檢視資料、點選固定資料點，或用趨勢線工具做簡單技術分析。

### 持股流程

1. 使用者在 `/portfolio.html` 新增持股。
2. `PortfolioService` 寫入 `positions` table。
3. 系統用正式掃描資料中的最新價格估算市值與損益。
4. 若沒有正式價格，現價與市值會暫時為 0。

### AI 分析流程

1. AI 頁讀取 `/api/ai/status` 確認 Ollama 是否可用。
2. 單檔分析會讀取正式股票 report，組成 prompt。
3. 持股分析可附加保存的持股紀錄。
4. `OllamaClient` 呼叫 `POST /api/generate`。
5. 前端把 AI 文字整理成報告卡片。

## 已修正或遇過的問題

### 示範資料混入正式流程

曾經遇到測試資料或 demo 資料容易干擾正式計算的問題。現在處理方式：

- 網站 UI 已移除示範資料按鈕與勾選。
- 公開 API 會忽略 `demo=1` 或 `demo: true`。
- 持股計算不再 fallback 到 demo 分數。
- 正常啟動網站不會自動建立 `tw_stock_screener.demo.sqlite`。
- 測試 fixtures 仍保留在內部測試流程，避免測試依賴外部網路。

### Ollama timeout

`qwen3.5:9b` 第一次載入可能很慢，曾出現 timeout。

建議：

- WSL 先執行 `ollama run qwen3.5:9b "OK"` 暖機。
- PowerShell 設定 `$env:OLLAMA_TIMEOUT="600"` 後重啟網站。
- 追加問題不要一次寫太長。
- 若仍慢，可以換較小模型並設定 `OLLAMA_MODEL`。

### WSL / Windows 連線

Windows 程式預設連到：

```text
http://127.0.0.1:11434
```

如果 AI 頁顯示 Ollama 未連線，先在 WSL 檢查：

```bash
ollama list
ollama serve
```

若 `ollama serve` 顯示 port 已被使用，通常表示服務已經在跑。

### 重複 run_app 行程

開發過程中曾出現多個 `run_app.py` 同時存在。若覺得頁面沒有更新到新版，可檢查：

```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
  Where-Object { $_.CommandLine -like '*run_app.py*' } |
  Select-Object ProcessId,CommandLine
```

必要時關掉舊行程再重開。

### 瀏覽器快取

CSS 或 JS 更新後，如果畫面仍像舊版，先按：

```text
Ctrl + F5
```

### 台股紅綠顏色

全站已依台股習慣統一：

- 紅色：漲、偏多、適合買入、獲利
- 綠色：跌、偏空、避開、虧損
- 黃色：觀察、中性、等待

### 免費資料來源穩定性

TWSE / FinMind 免費資料可能有：

- 暫時連線失敗
- API 欄位變動
- 額度限制
- 盤中或盤後延遲
- 部分股票缺籌碼或新聞資料

這類失敗不代表程式壞掉。可重試更新資料，或設定 `FINMIND_TOKEN` 提高穩定度。

## 目前已知限制

- 目前是本機工具，沒有登入與權限控管。
- 沒有自動下單功能。
- 篩選模型是規則式評分，不是保證獲利模型。
- AI 分析依賴 Ollama 是否已啟動、模型是否足夠快。
- 持股現價依賴正式掃描資料；沒有被掃描過的股票可能現價為 0。
- SQLite 適合本機單人使用，不適合多人高併發。
- 盤中即時能力受免費資料源限制，目前較適合作盤後或低頻更新。
- 個股完整圖表是本機 canvas 繪圖，提供基本技術分析工具；尚未做到專業看盤軟體的縮放拖曳、區間統計與多圖層物件管理。

## 建議維護方式

更新程式後建議固定跑：

```powershell
python -m unittest discover -s tests
python -m compileall app
node --check static\app.js
node --check static\ai.js
node --check static\portfolio.js
```

正式使用前建議確認：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/ai/status
```

若資料庫異常，可先備份：

```powershell
Copy-Item data\tw_stock_screener.sqlite data\tw_stock_screener.backup.sqlite
```

再視情況重新更新資料。

## 之後可加強的方向

- 加入更明確的資料新鮮度面板。
- 將持股頁加入編輯功能，而不只是新增與刪除。
- 將 AI 分析改成背景任務，避免長時間 HTTP request。
- 強化個股圖表的拖曳縮放、更多畫線工具與指標參數設定。
- 增加自選股管理頁。
- 增加更完整的 API 錯誤提示。
- 加入定期備份 SQLite 的工具。
