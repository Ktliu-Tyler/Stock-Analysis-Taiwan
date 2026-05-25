# 執行紀錄

## 2026-05-25

- 釐清本機主專案路徑為 `D:\taiwan_stock_scanner`，`D:\stock` 是舊工作目錄。
- 更新 README 與工作流程文件，將執行說明改為 `D:\taiwan_stock_scanner` 與 `venv\Scripts\python.exe`。
- 新增桌面捷徑建立腳本，產生 `Stock Scanner Start` 與 `Stock Scanner Stop`。
- 新增 `scripts/start_stock_scanner.ps1` 與 `scripts/stop_stock_scanner.ps1`，讓桌面啟動與停止流程固定指向正確專案。
- 更新 `start_lan.ps1`，優先使用專案虛擬環境的 Python。
- 新增 `technical-scan.html` 直接 API 技術掃描分頁，不使用本機快取結果，逐檔抓日線資料尋找 MACD 利空減弱與 KDJ 將金叉未金叉。
- 新增 `/api/technical-scanner/run` 與 `/api/technical-scanner/jobs/{job_id}`，以背景工作回報直接 API 掃描進度。
- 直接 API 技術掃描回傳 `data_policy=direct_api_only`，並以測試確保不讀寫本機市場資料。
- 新增日線自訂篩選模式：「MACD空頭減弱 + KDJ將金叉」。
- 新增 MACD series 與 KDJ series 計算，讓系統可以判斷最近多根日線的變化，而不是只看最新一根。
- 在評分模型加入 `daily_pattern` 與 `filter_flags`，完整成立時標示 `daily_macd_kdj_reversal_setup`。
- 首頁仍會顯示「日線轉折」標籤，精準型態掃描移到獨立直接 API 分頁。
- API 支援 `setup_pattern=daily_macd_kdj_reversal`，也支援 `macd_bearish_weakening=1` 與 `kdj_pre_golden_cross=1` 單獨篩選。
- 更新測試，覆蓋指標 series、一組日線轉折樣本、評分輸出與後端篩選。
- 已執行 `venv\Scripts\python.exe -m unittest discover -s tests`：19 tests 通過。
- 已執行 `venv\Scripts\python.exe -m compileall app`：通過。
- 已執行 `node --check static\app.js static\technical-scan.js static\stock.js static\ai.js static\portfolio.js`：通過。
- 已執行 `scripts\secret_scan.py` 與 `scripts\integrity_check.py`：通過。
- 以本機服務測試 `/api/screener/today?mode=short&setup_pattern=daily_macd_kdj_reversal`：API 正常回傳，目前本機資料符合數量為 0。

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

- 尚未設定 `.env`、GitHub Secrets、Email 或 LINE token。
- 尚未執行真實資料晨報，需等通知設定完成後再測。

### GitHub 發布

- 已連接遠端 repo：`Ktliu-Tyler/Stock-Analysis-Taiwan`。
- 已以遠端 `main` 為基底合併，不覆蓋既有 Web app 檔案。
- 已推送 commit：`92d6596 Add daily stock report agent workflow`。
- 推送前確認 `.env`、`reports/*.json`、`reports/*.svg`、`venv/`、`__pycache__/` 皆未 staged。
- 本機仍缺少 GitHub CLI `gh`，但已使用 `git push origin main` 完成發布。
