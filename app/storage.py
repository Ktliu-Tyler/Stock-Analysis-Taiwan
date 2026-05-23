from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator

from .config import DATA_DIR, DB_PATH
from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, ScoreResult, Stock


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS stocks (
                    stock_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    market TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS prices (
                    stock_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL NOT NULL,
                    PRIMARY KEY (stock_id, date)
                );

                CREATE TABLE IF NOT EXISTS institutional_flows (
                    stock_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    foreign_net REAL NOT NULL,
                    trust_net REAL NOT NULL,
                    dealer_net REAL NOT NULL,
                    total_net REAL NOT NULL,
                    PRIMARY KEY (stock_id, date)
                );

                CREATE TABLE IF NOT EXISTS margin_balances (
                    stock_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    margin_balance REAL NOT NULL,
                    short_balance REAL NOT NULL,
                    margin_change REAL NOT NULL,
                    short_change REAL NOT NULL,
                    PRIMARY KEY (stock_id, date)
                );

                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sentiment REAL NOT NULL,
                    UNIQUE (stock_id, title, published_at)
                );

                CREATE TABLE IF NOT EXISTS scores (
                    stock_id TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    name TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    market TEXT NOT NULL,
                    buy_score REAL NOT NULL,
                    technical_score REAL NOT NULL,
                    chip_score REAL NOT NULL,
                    sentiment_score REAL NOT NULL,
                    risk_score REAL NOT NULL,
                    entry_watch_price REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,
                    target_zone TEXT NOT NULL,
                    buy_reason TEXT NOT NULL,
                    avoid_reason TEXT NOT NULL,
                    data_freshness TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (stock_id, run_date)
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    shares REAL NOT NULL,
                    average_cost REAL NOT NULL,
                    buy_date TEXT NOT NULL,
                    position_status TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    risk_profile TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    sell_price REAL DEFAULT 0,
                    sell_date TEXT DEFAULT '',
                    sell_shares REAL DEFAULT 0,
                    closed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_prices_stock_date ON prices(stock_id, date);
                CREATE INDEX IF NOT EXISTS idx_scores_run_score ON scores(run_date, buy_score DESC);
                CREATE INDEX IF NOT EXISTS idx_positions_stock_id ON positions(stock_id);
                """
            )
            self._ensure_column(connection, "positions", "sell_price", "REAL DEFAULT 0")
            self._ensure_column(connection, "positions", "sell_date", "TEXT DEFAULT ''")
            self._ensure_column(connection, "positions", "sell_shares", "REAL DEFAULT 0")
            self._ensure_column(connection, "positions", "closed", "INTEGER DEFAULT 0")

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert_stocks(self, stocks: list[Stock]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO stocks (stock_id, name, industry, market)
                VALUES (:stock_id, :name, :industry, :market)
                ON CONFLICT(stock_id) DO UPDATE SET
                    name = excluded.name,
                    industry = excluded.industry,
                    market = excluded.market,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [asdict(stock) for stock in stocks],
            )

    def upsert_prices(self, prices: list[PriceBar]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO prices (stock_id, date, open, high, low, close, volume, amount)
                VALUES (:stock_id, :date, :open, :high, :low, :close, :volume, :amount)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    amount = excluded.amount
                """,
                [asdict(item) for item in prices],
            )

    def upsert_institutional_flows(self, flows: list[InstitutionalFlow]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO institutional_flows
                    (stock_id, date, foreign_net, trust_net, dealer_net, total_net)
                VALUES (:stock_id, :date, :foreign_net, :trust_net, :dealer_net, :total_net)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    foreign_net = excluded.foreign_net,
                    trust_net = excluded.trust_net,
                    dealer_net = excluded.dealer_net,
                    total_net = excluded.total_net
                """,
                [asdict(item) for item in flows],
            )

    def upsert_margin_balances(self, margins: list[MarginBalance]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO margin_balances
                    (stock_id, date, margin_balance, short_balance, margin_change, short_change)
                VALUES (:stock_id, :date, :margin_balance, :short_balance, :margin_change, :short_change)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    margin_balance = excluded.margin_balance,
                    short_balance = excluded.short_balance,
                    margin_change = excluded.margin_change,
                    short_change = excluded.short_change
                """,
                [asdict(item) for item in margins],
            )

    def upsert_news(self, news: list[NewsItem]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO news (stock_id, title, summary, source, published_at, url, sentiment)
                VALUES (:stock_id, :title, :summary, :source, :published_at, :url, :sentiment)
                ON CONFLICT(stock_id, title, published_at) DO UPDATE SET
                    summary = excluded.summary,
                    source = excluded.source,
                    url = excluded.url,
                    sentiment = excluded.sentiment
                """,
                [asdict(item) for item in news],
            )

    def upsert_scores(self, scores: list[ScoreResult]) -> None:
        rows: list[dict[str, Any]] = []
        for score in scores:
            row = score.to_dict()
            row["details_json"] = json.dumps(score.details, ensure_ascii=False)
            row.pop("details", None)
            rows.append(row)
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO scores (
                    stock_id, run_date, name, industry, market, buy_score,
                    technical_score, chip_score, sentiment_score, risk_score,
                    entry_watch_price, stop_loss_price, target_zone, buy_reason,
                    avoid_reason, data_freshness, decision, details_json
                )
                VALUES (
                    :stock_id, :run_date, :name, :industry, :market, :buy_score,
                    :technical_score, :chip_score, :sentiment_score, :risk_score,
                    :entry_watch_price, :stop_loss_price, :target_zone, :buy_reason,
                    :avoid_reason, :data_freshness, :decision, :details_json
                )
                ON CONFLICT(stock_id, run_date) DO UPDATE SET
                    name = excluded.name,
                    industry = excluded.industry,
                    market = excluded.market,
                    buy_score = excluded.buy_score,
                    technical_score = excluded.technical_score,
                    chip_score = excluded.chip_score,
                    sentiment_score = excluded.sentiment_score,
                    risk_score = excluded.risk_score,
                    entry_watch_price = excluded.entry_watch_price,
                    stop_loss_price = excluded.stop_loss_price,
                    target_zone = excluded.target_zone,
                    buy_reason = excluded.buy_reason,
                    avoid_reason = excluded.avoid_reason,
                    data_freshness = excluded.data_freshness,
                    decision = excluded.decision,
                    details_json = excluded.details_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def delete_scores_for_run(self, run_date: str, include_demo: bool = True) -> None:
        if not run_date:
            return
        with self.connect() as connection:
            if include_demo:
                connection.execute("DELETE FROM scores WHERE run_date = ?", (run_date,))
            else:
                connection.execute(
                    """
                    DELETE FROM scores
                    WHERE run_date = ?
                      AND data_freshness NOT LIKE 'demo/%'
                      AND data_freshness NOT LIKE 'demo_fallback/%'
                    """,
                    (run_date,),
                )

    def clear_stock_market_data(self, stock_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM prices WHERE stock_id = ?", (stock_id,))
            connection.execute("DELETE FROM institutional_flows WHERE stock_id = ?", (stock_id,))
            connection.execute("DELETE FROM margin_balances WHERE stock_id = ?", (stock_id,))
            connection.execute("DELETE FROM news WHERE stock_id = ?", (stock_id,))

    def purge_demo_artifacts(self, stock_ids: list[str] | None = None) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM scores
                WHERE data_freshness LIKE 'demo/%'
                   OR data_freshness LIKE 'demo_fallback/%'
                   OR run_date LIKE 'demo-%'
                """
            )
            deleted = cursor.rowcount if cursor.rowcount is not None else 0
            connection.execute("DELETE FROM news WHERE source = 'demo'")
            for stock_id in stock_ids or []:
                connection.execute("DELETE FROM scores WHERE stock_id = ?", (stock_id,))
                connection.execute("DELETE FROM prices WHERE stock_id = ?", (stock_id,))
                connection.execute("DELETE FROM institutional_flows WHERE stock_id = ?", (stock_id,))
                connection.execute("DELETE FROM margin_balances WHERE stock_id = ?", (stock_id,))
        return deleted

    def latest_run_date(self, include_demo: bool = False) -> str:
        with self.connect() as connection:
            if include_demo:
                row = connection.execute("SELECT MAX(run_date) AS run_date FROM scores").fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT MAX(run_date) AS run_date
                    FROM scores
                    WHERE data_freshness NOT LIKE 'demo/%'
                      AND data_freshness NOT LIKE 'demo_fallback/%'
                      AND run_date NOT LIKE 'demo-%'
                    """
                ).fetchone()
            return row["run_date"] if row and row["run_date"] else ""

    def get_scores(self, run_date: str = "", include_demo: bool = False) -> list[ScoreResult]:
        with self.connect() as connection:
            selected_date = run_date or self.latest_run_date(include_demo=include_demo)
            if not selected_date:
                return []
            if include_demo:
                rows = connection.execute(
                    "SELECT * FROM scores WHERE run_date = ? ORDER BY buy_score DESC",
                    (selected_date,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM scores
                    WHERE run_date = ?
                      AND data_freshness NOT LIKE 'demo/%'
                      AND data_freshness NOT LIKE 'demo_fallback/%'
                      AND run_date NOT LIKE 'demo-%'
                    ORDER BY buy_score DESC
                    """,
                    (selected_date,),
                ).fetchall()
        return [self._score_from_row(row) for row in rows]

    def get_score(self, stock_id: str, run_date: str = "", include_demo: bool = False) -> ScoreResult | None:
        with self.connect() as connection:
            selected_date = run_date or self.latest_run_date(include_demo=include_demo)
            if not selected_date:
                return None
            if include_demo:
                row = connection.execute(
                    "SELECT * FROM scores WHERE stock_id = ? AND run_date = ?",
                    (stock_id, selected_date),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM scores
                    WHERE stock_id = ?
                      AND run_date = ?
                      AND data_freshness NOT LIKE 'demo/%'
                      AND data_freshness NOT LIKE 'demo_fallback/%'
                      AND run_date NOT LIKE 'demo-%'
                    """,
                    (stock_id, selected_date),
                ).fetchone()
        return self._score_from_row(row) if row else None

    def get_stock(self, stock_id: str) -> Stock | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM stocks WHERE stock_id = ?", (stock_id,)).fetchone()
        if not row:
            return None
        return Stock(row["stock_id"], row["name"], row["industry"], row["market"])

    def get_stocks(self) -> list[Stock]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM stocks ORDER BY stock_id").fetchall()
        return [Stock(row["stock_id"], row["name"], row["industry"], row["market"]) for row in rows]

    def get_prices(self, stock_id: str) -> list[PriceBar]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM prices WHERE stock_id = ? ORDER BY date",
                (stock_id,),
            ).fetchall()
        return [PriceBar(**dict(row)) for row in rows]

    def get_institutional_flows(self, stock_id: str) -> list[InstitutionalFlow]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM institutional_flows WHERE stock_id = ? ORDER BY date",
                (stock_id,),
            ).fetchall()
        return [InstitutionalFlow(**dict(row)) for row in rows]

    def get_margin_balances(self, stock_id: str) -> list[MarginBalance]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM margin_balances WHERE stock_id = ? ORDER BY date",
                (stock_id,),
            ).fetchall()
        return [MarginBalance(**dict(row)) for row in rows]

    def get_news(self, stock_id: str, limit: int = 12) -> list[NewsItem]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT stock_id, title, summary, source, published_at, url, sentiment FROM news WHERE stock_id = ? "
                "ORDER BY published_at DESC, id DESC LIMIT ?",
                (stock_id, limit),
            ).fetchall()
        return [NewsItem(**dict(row)) for row in rows]

    def add_position(self, position: dict[str, Any]) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO positions (
                    stock_id, name, shares, average_cost, buy_date,
                    position_status, horizon, risk_profile, notes,
                    sell_price, sell_date, sell_shares, closed
                )
                VALUES (
                    :stock_id, :name, :shares, :average_cost, :buy_date,
                    :position_status, :horizon, :risk_profile, :notes,
                    :sell_price, :sell_date, :sell_shares, :closed
                )
                """,
                position,
            )
            return int(cursor.lastrowid)

    def update_position(self, position_id: int, position: dict[str, Any]) -> None:
        payload = dict(position)
        payload["id"] = position_id
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE positions
                SET stock_id = :stock_id,
                    name = :name,
                    shares = :shares,
                    average_cost = :average_cost,
                    buy_date = :buy_date,
                    position_status = :position_status,
                    horizon = :horizon,
                    risk_profile = :risk_profile,
                    notes = :notes,
                    sell_price = :sell_price,
                    sell_date = :sell_date,
                    sell_shares = :sell_shares,
                    closed = :closed,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                payload,
            )

    def delete_position(self, position_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM positions WHERE id = ?", (position_id,))

    def get_position(self, position_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
        return dict(row) if row else None

    def get_positions(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM positions ORDER BY updated_at DESC, id DESC").fetchall()
        return [dict(row) for row in rows]

    def _score_from_row(self, row: sqlite3.Row) -> ScoreResult:
        payload = dict(row)
        details_json = payload.pop("details_json", "{}")
        payload.pop("updated_at", None)
        payload["details"] = json.loads(details_json or "{}")
        return ScoreResult(**payload)
