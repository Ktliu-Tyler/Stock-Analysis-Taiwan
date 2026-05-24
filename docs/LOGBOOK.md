# 執行紀錄

## 2026-05-24

- 建立 `docs/DAILY_AGENT_PLAN.md`，定義每日晨報 agent、通知策略、排程策略與隱私原則。
- 新增 `daily_agent.py`，提供每日分析入口、sample mode、Email/LINE 通知、SVG 海報與 JSON manifest。
- 新增 `scripts/integrity_check.py`，檢查 Python 編譯、模組匯入、範例 agent 產物與環境範本。
- 新增 `scripts/secret_scan.py`，上傳前掃描疑似 API key、token、password。
- 新增 `.env.example`，僅保留 placeholder，不含任何真實金鑰。
- 新增 `.gitignore`，排除 `.env*`、`reports/`、`venv/`、快取與金鑰檔。
- 新增 `.github/workflows/daily-stock-agent.yml`，設定週一到週五 Asia/Taipei 07:30 執行。
- 移除 GitHub Actions artifact 上傳，避免把每日報告資料傳到 GitHub。
- 更新 `main.py`：加入 `return_metadata=True` 模式，讓 agent 可取得掃描統計、報告路徑與市場資訊；修正 CLI threshold 覆寫。
- 已執行 `scripts/integrity_check.py`：通過。
- 已執行 `scripts/secret_scan.py`：通過。
- 已執行 `daily_agent.py --sample --dry-run`：成功產生本機 sample manifest 與 SVG 海報，沒有發送通知。

### 尚待處理

- 本機不是 git repo，尚未 commit 或 push。
- 本機缺少 GitHub CLI `gh`，尚未建立 GitHub repo。
- 尚未設定 `.env`、GitHub Secrets、Email 或 LINE token。
- 尚未執行真實資料晨報，需等通知設定完成後再測。
