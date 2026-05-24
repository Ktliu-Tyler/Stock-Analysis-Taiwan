# 專案工作流程

最後更新：2026-05-24

## 開發前檢查

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

## 上傳 GitHub 前檢查

硬性規則：不要上傳 `.env`、API key、LINE token、Email 密碼、`reports/` 產物或個人資料。

上傳前執行：

```powershell
venv\Scripts\python.exe scripts\integrity_check.py
venv\Scripts\python.exe scripts\secret_scan.py
git status --short
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

目前本機尚未初始化 git repo，也沒有 GitHub CLI `gh`，所以先完成本地檔案與流程。等你準備上傳時：

```powershell
git init
git add .gitignore .env.example README.md config.py main.py report_generator.py scorer.py daily_agent.py analysis fetchers scripts docs .github reports/.gitkeep requirements.txt
git commit -m "Add daily stock report agent workflow"
git branch -M main
git remote add origin <你的 GitHub repo URL>
git push -u origin main
```

如果安裝 `gh`，也可以：

```powershell
gh auth login
gh repo create taiwan_stock_scanner --private --source . --remote origin --push
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
