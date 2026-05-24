# config.py — 台股智慧選股系統設定檔

# ─── 分析權重（總和必須為 1.0）───────────────────────────────────────────
WEIGHTS = {
    'technical':   0.35,   # 技術面
    'chips':       0.35,   # 籌碼面
    'fundamental': 0.20,   # 基本面
    'sentiment':   0.10,   # 市場情緒
}

# ─── 篩選門檻 ───────────────────────────────────────────────────────────
MIN_SCORE_THRESHOLD = 65    # 最低推薦總分（0–100）
TOP_N_STOCKS       = 20     # 最終輸出前 N 名

# ─── 股票初步過濾條件 ────────────────────────────────────────────────────
FILTERS = {
    'min_price':       10,      # 最低股價（排除水餃股）
    'max_price':       3000,    # 最高股價
    'min_avg_volume':  300,     # 最低平均成交量（張），流動性過濾
}

# ─── 資料抓取設定 ────────────────────────────────────────────────────────
REQUEST_DELAY      = 0.8    # 每次 API 請求間隔（秒），避免被擋
REQUEST_TIMEOUT    = 15     # 請求逾時（秒）
MAX_RETRIES        = 3      # 失敗重試次數

LOOKBACK_MONTHS    = 3      # 技術分析抓幾個月歷史資料
CHIPS_LOOKBACK_DAYS = 10    # 籌碼分析回看天數

# ─── 技術面指標參數 ──────────────────────────────────────────────────────
TECH_PARAMS = {
    'ma_periods':  [5, 10, 20, 60],   # 均線週期
    'kd_period':   9,
    'macd_fast':   12,
    'macd_slow':   26,
    'macd_signal': 9,
    'bb_period':   20,
    'bb_std':      2,
}

# ─── 情緒分析關鍵字 ──────────────────────────────────────────────────────
POSITIVE_KEYWORDS = [
    '創高', '突破', '漲停', '法說', '獲利', '成長', '訂單', '旺季',
    '上調', '買進', '推薦', '新高', '題材', '利多', '受惠', '強勢',
    '增資', '配息', 'EPS 超預期', '業績亮眼',
]
NEGATIVE_KEYWORDS = [
    '虧損', '下修', '地雷', '減資', '停牌', '違約', '跌停', '庫存',
    '砍單', '衰退', '警示', '下調', '賣出', '看壞', '利空', '暴跌',
    '出貨', '財報不佳',
]

# ─── 報告輸出 ────────────────────────────────────────────────────────────
REPORT_OUTPUT_DIR  = './reports/'

# ─── TWSE API Endpoints ──────────────────────────────────────────────────
TWSE_BASE = 'https://www.twse.com.tw/rwd/zh'
ENDPOINTS = {
    # 個股月成交資訊
    'stock_day':       f'{TWSE_BASE}/afterTrading/STOCK_DAY',
    # 三大法人買賣超（全市場）
    'institutional':   f'{TWSE_BASE}/fund/T86',
    # 融資融券餘額
    'margin':          f'{TWSE_BASE}/marginTrading/MI_MARGN',
    # 本益比、殖利率、淨值比（全市場）
    'valuation':       f'{TWSE_BASE}/afterTrading/BWIBBU_d',
    # 大盤指數
    'index':           f'{TWSE_BASE}/indicesReport/MI_5MINS_HIST',
}

# 股票清單來源
STOCK_LIST_URL = 'https://isin.twse.com.tw/isin/C_public.jsp?strMode=2'

# 新聞來源（鉅亨網 RSS）
NEWS_RSS_URLS = [
    'https://www.cnyes.com/rss/cat/tw_stock',
    'https://tw.stock.yahoo.com/rss',
]
