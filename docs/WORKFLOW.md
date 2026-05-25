# 專案工作流程

最後更新：2026-05-25

## 開發前檢查

主專案路徑：

```powershell
cd D:\taiwan_stock_scanner
```

`D:\stock` 是舊的本機工作目錄，後續開發、測試與上傳 GitHub 都以 `D:\taiwan_stock_scanner` 為準。

1. 確認目前沒有要上傳的私密檔：

```powershell
venv\Scripts\python.exe scripts\secret_scan.py
```

2. 執行完整性檢查：

```powershell
venv\Scripts\python.exe scripts\integrity_check.py
```

3. 產生範例晨報，不發送通知：

```powershell
venv\Scripts\python.exe daily_agent.py --sample --dry-run
```

## 本機執行每日 Agent

1. 複製設定檔：

```powershell
Copy-Item .env.example .env
```

2. 編輯 `.env`，填入自己的通知設定。

3. 先 dry run：

```powershell
venv\Scripts\python.exe daily_agent.py --sample --dry-run
```

4. 測試 Email：

```powershell
venv\Scripts\python.exe daily_agent.py --sample --send-email
```

5. 測試 LINE：

```powershell
venv\Scripts\python.exe daily_agent.py --sample --send-line
```

6. 測試少量真實股票：

```powershell
venv\Scripts\python.exe daily_agent.py --stocks 2330 2317 2454 --dry-run
```

## 桌面啟動與停止

建立或更新桌面捷徑：

```powershell
cd D:\taiwan_stock_scanner
powershell -ExecutionPolicy Bypass -File .\scripts\create_desktop_shortcuts.ps1
```

桌面會有：

- `Stock Scanner Start`：切到 `D:\taiwan_stock_scanner`，使用 `venv\Scripts\python.exe` 啟動 `run_app.py`，並開啟 `http://127.0.0.1:8000/`。
- `Stock Scanner Stop`：停止本機 `8000` port 上的 Python 服務。

手動停止方式：

- 在啟動視窗按 `Ctrl+C`。
- 或直接關閉啟動用的 PowerShell 視窗。
- 或雙擊桌面的 `Stock Scanner Stop`。

## 使用日線自訂篩選

Web 介面：

1. 啟動服務。
2. 在首頁篩選列找到「日線型態」。
3. 選擇「MACD空頭減弱 + KDJ將金叉」。

API：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/screener/today?mode=short&setup_pattern=daily_macd_kdj_reversal"
```

可拆開單獨查詢：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/screener/today?macd_bearish_weakening=1"
Invoke-RestMethod "http://127.0.0.1:8000/api/screener/today?kdj_pre_golden_cross=1"
```

## 上傳 GitHub 前檢查

硬性規則：不要上傳 `.env`、API key、LINE token、Email 密碼、`reports/` 產物或個人資料。

上傳前執行：

```powershell
venv\Scripts\python.exe scripts\integrity_check.py
venv\Scripts\python.exe scripts\secret_scan.py
git status --short
```

前端或篩選邏輯變更時，另外執行：

```powershell
venv\Scripts\python.exe -m unittest discover -s tests
venv\Scripts\python.exe -m compileall app
node --check static\app.js
node --check static\ai.js
node --check static\portfolio.js
node --check static\stock.js
```

只允許提交：

- 程式碼：`.py`
- 文件：`docs/`、`README.md`
- 設定範本：`.env.example`
- GitHub Actions workflow：`.github/workflows/`
- `.gitignore`
- `reports/.gitkeep`

不允許提交：

- `.env` 或任何 `.env.*` 私密檔
- `reports/*.html`、`reports/*.svg`、`reports/*.json`
- `venv/`
- `__pycache__/`
- 任何金鑰、token、私密信箱設定

## GitHub 發布流程

目前已連接遠端 repo：`Ktliu-Tyler/Stock-Analysis-Taiwan`。

因為本機尚未安裝 GitHub CLI `gh`，目前採用一般 git push 流程：

```powershell
venv\Scripts\python.exe scripts\secret_scan.py
git status --short
git add <本次要提交的檔案>
git commit -m "<本次變更摘要>"
git push -u origin main
```

若未來安裝 `gh`，可改用 GitHub CLI 建立 PR 或管理 repo：

```powershell
gh auth login
gh pr create --draft --fill
```

## GitHub Secrets / Variables

在 GitHub repository 的 Settings 設定，不要寫進檔案。

Secrets：

- `EMAIL_FROM`
- `EMAIL_TO`
- `RESEND_API_KEY`
- `SMTP_HOST`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO`

Variables：

- `AGENT_THRESHOLD`
- `AGENT_QUICK_MODE`
- `AGENT_STOCKS`
- `AGENT_SEND_EMAIL`
- `AGENT_SEND_LINE`
- `EMAIL_PROVIDER`
- `SMTP_PORT`
- `SMTP_USE_TLS`
- `LINE_REPORT_URL`
- `LINE_POSTER_IMAGE_URL`

## 紀錄規則

- 架構與計畫變更記錄在 `docs/LOGBOOK.md`。
- 每次 agent 執行會在 `reports/daily_run_*.json` 產生本機紀錄，但這些不進 GitHub。
- 若未來要保存歷史績效，建議另建私有資料庫或加密儲存，不放公開 repo。
