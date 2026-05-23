# 台股投資分析系統

這是一個本機 Web 儀表板，用來輔助分析台股標的，支援短線、波段與中長線觀察。系統會整合技術面、籌碼面、情緒面、風控分數、本地規則模型與持股紀錄，並可透過本機 Ollama 模型產生單檔股票或個人持股策略分析。

本系統只做研究輔助，不會自動下單，也不構成投資建議。

## 目前狀態

- 使用 Python 標準函式庫實作後端與靜態檔案服務。
- 使用 SQLite 儲存正式掃描資料、價格、籌碼、新聞、評分與持股紀錄。
- 網站操作只使用正式資料，不提供示範資料模式。
- 台股顏色習慣已統一：漲、偏多、獲利用紅色；跌、偏空、虧損用綠色。
- 前端已加入暗色系介面、載入動畫、skeleton loading 與 AI 報告式排版。

## 快速啟動

在 Windows PowerShell 執行：

```powershell
cd D:\stock
python run_app.py --host 127.0.0.1 --port 8000
```

開啟首頁：

```text
http://127.0.0.1:8000/
```

主要頁面：

- `http://127.0.0.1:8000/`：候選股票篩選儀表板
- `http://127.0.0.1:8000/stock.html?id=2330`：個股完整分析與互動價量圖
- `http://127.0.0.1:8000/portfolio.html`：持股紀錄與損益計算
- `http://127.0.0.1:8000/ai.html`：Ollama AI 股票與持股分析

## 第一次使用

1. 啟動網站。
2. 打開首頁。
3. 點擊 `更新資料`，讓系統抓取正式市場資料並重新評分。
4. 在候選清單中點選股票查看摘要分析。
5. 點擊 `完整圖表` 開啟獨立個股分析頁。
6. 到持股頁加入自己的股票、股數與成本。
7. 到 AI 頁選股票或帶入持股，讓 Ollama 產生分析。

若資料來源暫時抓不到資料，系統不會自動載入示範資料；畫面會保留目前正式資料或顯示更新失敗訊息。

## 功能概覽

### 篩選儀表板

首頁直接顯示候選股票清單，包含：

- 股票代號、名稱、產業
- 多空方向
- 投資建議
- 總分、技術分、籌碼分、情緒分、風控分
- 觀察價、停損價、資料時間
- K 線與成交量摘要
- 法人買賣超
- 指標影響拆解
- 本地規則模型偏多、中性、偏空機率
- 近期新聞與公告摘要
- 1、3、5 日策略回測

### 個股完整分析頁

從首頁選取股票後，可點擊 `完整圖表` 進入獨立頁面。該頁提供：

- 互動 K 線與收盤線切換
- 1M、3M、6M、全部資料範圍
- MA5、MA10、MA20 顯示切換
- 成交量顯示切換
- RSI、MACD、法人買賣超副圖
- 十字游標與點選固定資料點
- 趨勢線繪製與清除
- 分數、價位規劃、系統理由、新聞公告與指標拆解

可用篩選條件：

- 產業
- 最低總分
- 多空方向
- 投資建議
- 最低成交量
- 技術分、籌碼分、情緒分、風控分
- 本地模型信心
- 法人偏多
- 排除高風險
- 均線偏多
- MACD 偏多
- 量能突破
- 20 日突破
- 情緒正向
- 本地模型偏多

### 持股紀錄

持股頁是獨立功能，不依賴 AI 分析。

支援：

- 快速加入股票代號、名稱、股數、平均買入價、買入日期
- 設定持股狀態、投資週期、風險承受度與備註
- 刪除持股
- 自動估算總成本、目前市值、未實現損益與損益率
- 每筆持股可點擊 `AI`，帶入 AI 頁作為分析參考

注意：若某檔股票尚未出現在正式掃描資料中，持股頁現價可能暫時為 `0`。更新資料或將該股票加入掃描清單後，損益會依最新資料重新計算。

### Ollama AI 分析

AI 頁和原本篩選儀表板分開，不會阻塞你查看原本介面。

支援：

- 單檔股票 AI 分析
- 個人持股策略分析
- 從持股頁帶入保存的持股資料
- 追加問題
- 選擇本機 Ollama 模型
- AI 回覆自動整理成報告卡片

預設 Ollama 設定：

- `OLLAMA_HOST`：`http://127.0.0.1:11434`
- `OLLAMA_MODEL`：`qwen3.5:9b`
- `OLLAMA_TIMEOUT`：`360`

## WSL / Ollama 啟動方式

你不一定每次都要進 WSL 重新開模型。只要 Ollama 服務已經在 WSL 裡持續執行，Windows 這邊直接執行本系統即可。

建議流程：

```bash
ollama list
```

如果 Ollama 沒有在跑：

```bash
ollama serve
```

如果看到 port 已被使用，通常代表 Ollama 已經在跑，不用再開第二個。

第一次分析前，建議先暖機模型：

```bash
ollama run qwen3.5:9b "請用一句話回答 OK"
```

Windows PowerShell 啟動網站時可設定：

```powershell
$env:OLLAMA_MODEL="qwen3.5:9b"
$env:OLLAMA_TIMEOUT="360"
python run_app.py --host 127.0.0.1 --port 8000
```

若 AI 分析仍 timeout，可以改成：

```powershell
$env:OLLAMA_TIMEOUT="600"
```

再重新啟動網站。

## 資料來源

目前使用免費或低成本資料來源為主：

- TWSE OpenAPI
- FinMind API
- 本機 SQLite 快照

資料會寫入：

```text
data/tw_stock_screener.sqlite
```

網站正式流程不會載入示範資料，也不會自動 fallback 到示範資料。

## 環境變數

| 變數 | 預設值 | 說明 |
| --- | --- | --- |
| `FINMIND_TOKEN` | 空字串 | FinMind token，可提高額度與穩定性 |
| `REQUEST_TIMEOUT` | `10` | 抓取外部資料的 timeout 秒數 |
| `STOCK_SCAN_LIMIT` | `18` | 每次掃描股票數 |
| `TW_STOCK_WATCHLIST` | 空字串 | 自訂掃描清單，例如 `2330,2317,2454` |
| `ENABLE_SCHEDULER` | `0` | 設為 `1` 時啟用台北時間盤後自動更新 |
| `STOCK_DB_PATH` | `data/tw_stock_screener.sqlite` | 自訂 SQLite 資料庫路徑 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API 位址 |
| `OLLAMA_MODEL` | `qwen3.5:9b` | 預設 AI 模型 |
| `OLLAMA_TIMEOUT` | `360` | AI 生成 timeout 秒數 |

自訂掃描清單範例：

```powershell
$env:TW_STOCK_WATCHLIST="2330,2317,2454,2382"
python run_app.py --host 127.0.0.1 --port 8000
```

## API

### 系統狀態

```text
GET /api/health
```

### 篩選

```text
GET /api/screener/today
POST /api/screener/run
GET /api/backtest
```

篩選參數範例：

```text
/api/screener/today?direction=看多&macd_bullish=1&local_model_bullish=1&min_technical=70
```

手動更新資料：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/screener/run `
  -ContentType application/json `
  -Body '{"mode":"manual"}'
```

### 單檔股票

```text
GET /api/stocks/{stock_id}/report
GET /api/stocks/{stock_id}/signals
```

### 持股

```text
GET /api/portfolio
POST /api/portfolio
POST /api/portfolio/{position_id}
POST /api/portfolio/{position_id}/delete
```

新增持股範例：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/portfolio `
  -ContentType application/json `
  -Body '{"stock_id":"2330","shares":1000,"average_cost":650}'
```

### AI

```text
GET /api/ai/status
POST /api/ai/analyze-stock
POST /api/ai/analyze-position
```

## 測試與檢查

執行單元測試：

```powershell
python -m unittest discover -s tests
```

檢查 Python 語法：

```powershell
python -m compileall app
```

檢查前端 JS 語法：

```powershell
node --check static\app.js
node --check static\ai.js
node --check static\portfolio.js
```

檢查服務是否正常：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## 目錄結構

```text
app/
  config.py          設定與環境變數
  data_sources.py    TWSE / FinMind 資料抓取
  indicators.py      技術指標
  scoring.py         評分模型
  screener.py        掃描、報告、回測流程
  portfolio.py       持股紀錄與損益計算
  ollama_ai.py       Ollama AI 分析
  server.py          HTTP server 與 API route
  storage.py         SQLite 存取
static/
  index.html         篩選儀表板
  portfolio.html     持股頁
  ai.html            AI 分析頁
  styles.css         全站暗色 UI
tests/
  單元測試
data/
  tw_stock_screener.sqlite
```

## 安全與限制

- 本系統沒有登入驗證，建議只綁定 `127.0.0.1` 本機使用。
- 不會自動下單。
- 評分與 AI 回覆都只是研究輔助。
- 免費資料來源可能延遲、缺欄位或暫時失敗。
- Ollama 生成速度取決於模型大小、GPU/VRAM、RAM 與第一次載入狀態。
- 台股投資訊號會受週期、資料延遲與市場波動影響，實際交易前仍需自行確認風險。
