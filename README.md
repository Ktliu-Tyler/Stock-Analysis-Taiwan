# 台股投資分析系統

這是一個本機 Web 儀表板，用來輔助分析台股標的，支援短線、波段與中長線觀察。系統會整合技術面、籌碼面、情緒面、風控分數、本地規則模型與持股紀錄，並可透過本機 Ollama 模型產生單檔股票或個人持股策略分析。

本系統只做研究輔助，不會自動下單，也不構成投資建議。

## 目前狀態

- 使用 Python 標準函式庫實作後端與靜態檔案服務。
- 使用 SQLite 儲存正式掃描資料、價格、籌碼、新聞、評分與持股紀錄。
- 網站操作只使用正式資料，不提供示範資料模式。
- 台股顏色習慣已統一：漲、偏多、獲利用紅色；跌、偏空、虧損用綠色。
- 前端已加入暗色系介面、載入動畫、skeleton loading 與 AI 報告式排版。
- 篩選、個股、AI 與持股流程支援短線、波段、長線三種分析模式。

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

### 手機或平板用同一個 Wi-Fi 開啟

如果要從手機開啟，伺服器不能只綁定 `127.0.0.1`，因為那只允許目前這台電腦自己連線。請改用區網模式啟動：

```powershell
cd D:\stock
.\start_lan.ps1
```

或手動執行：

```powershell
python run_app.py --host 0.0.0.0 --port 8000
```

啟動後終端機會印出類似下面的區網網址，手機請開這個網址：

```text
http://192.168.1.23:8000/
```

注意事項：

- 手機和電腦要在同一個 Wi-Fi 或同一個區網，不能用手機行動網路。
- Windows 防火牆若跳出提示，請允許 Python 在私人網路通訊。
- 若終端機沒有列出區網網址，可用 `ipconfig` 找 `IPv4 Address`，再用 `http://你的IPv4:8000/` 開啟。
- 本系統沒有登入驗證，區網模式只建議在你信任的私人網路使用。

主要頁面：

- `http://127.0.0.1:8000/`：候選股票篩選儀表板
- `http://127.0.0.1:8000/stock.html?id=2330`：個股完整分析與互動價量圖
- `http://127.0.0.1:8000/portfolio.html`：持股紀錄與損益計算
- `http://127.0.0.1:8000/ai.html`：Ollama AI 股票與持股分析

## 第一次使用

1. 啟動網站。
2. 打開首頁。
3. 點擊 `更新資料`，讓系統抓取正式市場資料並重新評分；若今天已更新過，會直接使用本機快取加速。
4. 在首頁切換 `短線`、`波段`、`長線` 模式，查看不同週期的候選名單。
5. 在候選清單中點選股票查看摘要分析。
6. 點擊 `完整圖表` 開啟獨立個股分析頁，也可在該頁快速加入持股觀察。
7. 到持股頁加入自己的股票、股數與成本，並依短期、中期、長期分類查看。
8. 到 AI 頁選股票或帶入持股，讓 Ollama 產生分析。

若資料來源暫時抓不到資料，系統不會自動載入示範資料；畫面會保留目前正式資料或顯示更新失敗訊息。

首頁資料更新按鈕：

- `更新資料`：智慧更新。今天已更新過正式資料時直接使用本機快取重新評分，沒有今日快取才抓 API。
- `重新評分`：只使用本機資料重新計算分數，不抓取任何外部 API。
- `強制更新`：忽略今日快取，重新抓取市場資料；適合你確認資料源已更新後手動刷新。

## 功能概覽

### 篩選儀表板

首頁直接顯示候選股票清單，包含：

- 短線、波段、長線三種選股模式
- 股票代號、名稱、產業
- 多空方向
- 投資建議
- 總分、技術分、籌碼分、情緒分、風控分
- 觀察價、停損價、資料時間
- K 線與成交量摘要
- 法人買賣超
- 指標影響拆解，包含 MA、RSI、MACD、布林通道、KDJ、量能與區間突破
- 本地規則模型偏多、中性、偏空機率
- 近期新聞與公告摘要
- 依模式切換的策略回測
- 同日快取、快速重新評分與強制更新

三種模式重點：

- `短線`：1-5 日，重視短均線、量價突破、法人短期買盤與停損效率。
- `波段`：2-8 週，重視 MA20/MA60、法人延續性、整理突破與較寬的風控空間。
- `長線`：3-12 個月，重視 MA60 趨勢、風險邊際、題材持續性與較長目標區間。

### 個股完整分析頁

從首頁選取股票後，可點擊 `完整圖表` 進入獨立頁面。該頁提供：

- 互動 K 線與收盤線切換
- 1M、3M、6M、全部資料範圍
- MA5、MA10、MA20 顯示切換
- 布林通道顯示切換
- 成交量顯示切換
- RSI、MACD、KDJ、法人買賣超副圖
- 十字游標與點選固定資料點
- 趨勢線繪製與清除
- 分數、價位規劃、系統理由、新聞公告與指標拆解
- 短線、波段、長線模式切換
- 直接輸入買入/觀察價與股數，快速加入持股觀察

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
- 布林偏多
- KDJ 偏多
- 量能突破
- 20 日突破
- 情緒正向
- 本地模型偏多

### 持股紀錄

持股頁是獨立功能，不依賴 AI 分析。

支援：

- 快速加入股票代號、名稱、股數、平均買入價、買入日期
- 設定持股狀態、投資週期、風險承受度與備註
- 依短期、中期、長期分類檢視持股
- 可將持股標記為賣出，保存賣出價、賣出股數、賣出日期與已實現損益
- 刪除持股
- 自動估算總成本、目前市值、未實現損益與損益率
- 每筆持股可點擊 `AI`，帶入 AI 頁作為分析參考

注意：若某檔股票尚未出現在正式掃描資料中，持股頁現價可能暫時為 `0`。更新資料或將該股票加入掃描清單後，損益會依最新資料重新計算。

### Ollama AI 分析

AI 頁和原本篩選儀表板分開，不會阻塞你查看原本介面。

支援：

- 單檔股票 AI 分析
- 個人持股策略分析
- 短線、波段、長線模式選擇
- 從持股頁帶入保存的持股資料
- 追加問題
- 選擇本機 Ollama 模型
- thinking 模式即時顯示模型思考內容，完成後自動摺疊
- AI 回覆自動整理成報告卡片

預設 Ollama 設定：

- `OLLAMA_HOST`：`http://127.0.0.1:11434`
- `OLLAMA_MODEL`：`qwen3:4b`
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
ollama run qwen3:4b "請用一句話回答 OK"
```

目前這台 WSL 已安裝的模型：

```text
qwen3:1.7b    快速中文分析，支援 thinking
qwen3:4b      推薦日常分析，支援 thinking，速度與品質平衡
gemma3:1b     超輕量備用，速度快但細節較少
gemma4:e2b    Gemma 4 edge 版，約 7.2GB，推理能力較好但載入較久
qwen3.5:9b    較完整但比較慢
```

`gemma4:e2b` 是 Gemma 4 的較小 edge 版本，但仍約 7.2GB；若日後重新安裝或下載中斷，可在 WSL 內重新執行：

```bash
ollama pull gemma4:e2b
```

Windows PowerShell 啟動網站時可設定：

```powershell
$env:OLLAMA_MODEL="qwen3:4b"
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
| `OLLAMA_MODEL` | `qwen3:4b` | 預設 AI 模型 |
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
/api/screener/today?mode=swing&direction=看多&macd_bullish=1&local_model_bullish=1&min_technical=70
```

手動更新資料：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/screener/run `
  -ContentType application/json `
  -Body '{"mode":"manual","analysis_mode":"swing"}'
```

只用本機資料重新評分：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/screener/run `
  -ContentType application/json `
  -Body '{"mode":"rescore","analysis_mode":"swing","rescore_only":true}'
```

忽略今日快取並強制重抓：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/screener/run `
  -ContentType application/json `
  -Body '{"mode":"manual","analysis_mode":"swing","force_refresh":true}'
```

### 單檔股票

```text
GET /api/stocks/{stock_id}/report
GET /api/stocks/{stock_id}/signals
```

可加上 `?mode=short`、`?mode=swing`、`?mode=long` 切換分析週期。

### 持股

```text
GET /api/portfolio
POST /api/portfolio
POST /api/portfolio/{position_id}
POST /api/portfolio/{position_id}/sell
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
POST /api/ai/analyze-stock-stream
POST /api/ai/analyze-position-stream
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
node --check static\stock.js
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
  stock.html         個股完整分析頁
  portfolio.html     持股頁
  ai.html            AI 分析頁
  styles.css         全站暗色 UI
tests/
  單元測試
data/
  tw_stock_screener.sqlite
```

## 安全與限制

- 本系統沒有登入驗證，平常建議只綁定 `127.0.0.1` 本機使用；需要手機查看時再用 `--host 0.0.0.0` 開區網模式。
- 不會自動下單。
- 評分與 AI 回覆都只是研究輔助。
- 免費資料來源可能延遲、缺欄位或暫時失敗。
- Ollama 生成速度取決於模型大小、GPU/VRAM、RAM 與第一次載入狀態。
- 台股投資訊號會受週期、資料延遲與市場波動影響，實際交易前仍需自行確認風險。
