import argparse
import base64
import html
import json
import logging
import mimetypes
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import requests

import config as app_config
import main as screener
import report_generator


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = BASE_DIR / "reports"
LOGGER = logging.getLogger("daily_agent")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def split_values(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(",", " ")
    return [item.strip() for item in normalized.split() if item.strip()]


@dataclass
class AgentConfig:
    quick_mode: bool
    stocks: list[str]
    threshold: int
    dry_run: bool
    output_dir: Path
    send_email: bool
    email_provider: str
    email_from: str
    email_to: list[str]
    resend_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool
    send_line: bool
    line_channel_access_token: str
    line_to: str
    line_report_url: str
    line_poster_image_url: str

    @classmethod
    def from_env(cls, args: argparse.Namespace) -> "AgentConfig":
        output_dir = Path(os.getenv("AGENT_OUTPUT_DIR", str(DEFAULT_REPORT_DIR)))
        if not output_dir.is_absolute():
            output_dir = BASE_DIR / output_dir

        threshold = args.threshold
        if threshold is None:
            threshold = int(os.getenv("AGENT_THRESHOLD", app_config.MIN_SCORE_THRESHOLD))

        stocks = args.stocks or split_values(os.getenv("AGENT_STOCKS"))

        return cls(
            quick_mode=args.quick or env_bool("AGENT_QUICK_MODE", False),
            stocks=stocks,
            threshold=threshold,
            dry_run=args.dry_run or env_bool("AGENT_DRY_RUN", False),
            output_dir=output_dir,
            send_email=args.send_email or env_bool("AGENT_SEND_EMAIL", False),
            email_provider=os.getenv("EMAIL_PROVIDER", "resend").strip().lower(),
            email_from=os.getenv("EMAIL_FROM", ""),
            email_to=split_values(os.getenv("EMAIL_TO")),
            resend_api_key=os.getenv("RESEND_API_KEY", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=env_bool("SMTP_USE_TLS", True),
            send_line=args.send_line or env_bool("AGENT_SEND_LINE", False),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""),
            line_to=os.getenv("LINE_TO", ""),
            line_report_url=os.getenv("LINE_REPORT_URL", ""),
            line_poster_image_url=os.getenv("LINE_POSTER_IMAGE_URL", ""),
        )


def configure_threshold(threshold: int) -> None:
    app_config.MIN_SCORE_THRESHOLD = threshold
    screener.MIN_SCORE_THRESHOLD = threshold
    report_generator.MIN_SCORE_THRESHOLD = threshold


def build_sample_metadata() -> dict:
    now = datetime.now()
    sample_results = [
        {
            "stock_id": "2330",
            "name": "台積電",
            "price": 999.0,
            "total_score": 86.5,
            "grade": {"label": "A+ 強力買進", "color": "#00a651", "emoji": "🚀"},
            "dimension_scores": {
                "technical": 88,
                "chips": 84,
                "fundamental": 91,
                "sentiment": 78,
            },
            "all_signals": {
                "technical": "均線多頭排列，量能同步放大",
                "chips": "外資與投信同步偏多",
                "risk": "留意短線漲幅後的拉回風險",
            },
        },
        {
            "stock_id": "2317",
            "name": "鴻海",
            "price": 188.5,
            "total_score": 75.2,
            "grade": {"label": "A 建議買進", "color": "#4caf50", "emoji": "✅"},
            "dimension_scores": {
                "technical": 76,
                "chips": 79,
                "fundamental": 70,
                "sentiment": 74,
            },
            "all_signals": {
                "technical": "價格站上月線，KD 轉強",
                "chips": "法人近幾日買超延續",
            },
        },
    ]
    return {
        "run_id": now.strftime("%Y%m%d_%H%M%S"),
        "created_at": now.isoformat(timespec="seconds"),
        "results": sample_results,
        "scanned_count": 100,
        "candidate_count": 18,
        "qualified_count": 2,
        "report_path": None,
        "market_info": {
            "sentiment": "neutral",
            "description": "測試資料：盤勢中性偏多",
            "score_multiplier": 1.0,
        },
        "elapsed_seconds": 0,
        "threshold": 65,
        "sample": True,
    }


def normalize_metadata(raw_metadata: dict) -> dict:
    now = datetime.now()
    metadata = dict(raw_metadata)
    metadata.setdefault("run_id", now.strftime("%Y%m%d_%H%M%S"))
    metadata.setdefault("created_at", now.isoformat(timespec="seconds"))
    metadata.setdefault("results", [])
    metadata.setdefault("market_info", {})
    return metadata


def collect_signals(stock: dict, limit: int = 3) -> list[str]:
    signals = stock.get("all_signals") or {}
    if not signals:
        for key in ["tech_signals", "chips_signals", "fund_signals", "sent_signals"]:
            signals.update(stock.get(key, {}) or {})
    return [str(value) for value in signals.values() if value][:limit]


def score_color(score: float) -> str:
    if score >= 80:
        return "#00a651"
    if score >= 70:
        return "#2e7d32"
    if score >= 65:
        return "#7cb342"
    if score >= 55:
        return "#f9a825"
    return "#e53935"


def generate_poster_svg(metadata: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = metadata["run_id"]
    poster_path = output_dir / f"poster_{run_id}.svg"
    stocks = metadata.get("results", [])[:5]
    market = metadata.get("market_info", {})
    created_at = metadata.get("created_at", "")

    rows = []
    y = 310
    for index, stock in enumerate(stocks, 1):
        score = float(stock.get("total_score", 0))
        color = score_color(score)
        name = html.escape(str(stock.get("name") or stock.get("stock_id", "")))
        stock_id = html.escape(str(stock.get("stock_id", "")))
        price = stock.get("price")
        price_text = f"NT$ {price:.2f}" if isinstance(price, (int, float)) else "N/A"
        dims = stock.get("dimension_scores", {})
        dim_text = (
            f"T {float(dims.get('technical', 0)):.0f} / "
            f"C {float(dims.get('chips', 0)):.0f} / "
            f"F {float(dims.get('fundamental', 0)):.0f} / "
            f"S {float(dims.get('sentiment', 0)):.0f}"
        )
        signal = html.escape(collect_signals(stock, 1)[0] if collect_signals(stock, 1) else "觀察量價與籌碼延續性")
        bar_width = max(0, min(620, score / 100 * 620))

        rows.append(
            f"""
  <g>
    <rect x="70" y="{y}" width="940" height="130" rx="22" fill="#ffffff" opacity="0.96"/>
    <text x="105" y="{y + 46}" font-size="32" font-weight="800" fill="#102033">{index}. {stock_id} {name}</text>
    <text x="105" y="{y + 84}" font-size="22" fill="#50606f">{price_text} · {dim_text}</text>
    <text x="105" y="{y + 116}" font-size="20" fill="#687887">{signal}</text>
    <text x="880" y="{y + 55}" font-size="42" font-weight="900" text-anchor="middle" fill="{color}">{score:.1f}</text>
    <rect x="610" y="{y + 90}" width="320" height="12" rx="6" fill="#dfe6ee"/>
    <rect x="610" y="{y + 90}" width="{bar_width / 620 * 320:.1f}" height="12" rx="6" fill="{color}"/>
  </g>"""
        )
        y += 152

    if not rows:
        rows.append(
            """
  <rect x="70" y="330" width="940" height="180" rx="24" fill="#ffffff" opacity="0.96"/>
  <text x="540" y="420" font-size="34" font-weight="800" text-anchor="middle" fill="#102033">今日沒有符合門檻的標的</text>
  <text x="540" y="466" font-size="23" text-anchor="middle" fill="#687887">維持觀察，等待更好的風險報酬條件</text>"""
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f4f8fb"/>
      <stop offset="0.45" stop-color="#dcefe9"/>
      <stop offset="1" stop-color="#f7e7d7"/>
    </linearGradient>
  </defs>
  <rect width="1080" height="1350" fill="url(#bg)"/>
  <rect x="0" y="0" width="1080" height="250" fill="#102033"/>
  <text x="70" y="96" font-size="50" font-weight="900" fill="#ffffff">台股晨間選股報告</text>
  <text x="70" y="150" font-size="25" fill="#d8e6f0">{html.escape(created_at)}</text>
  <text x="70" y="198" font-size="25" fill="#9ed8c4">{html.escape(str(market.get("description", "市場狀態待確認")))}</text>
  <g>
    <rect x="70" y="230" width="290" height="58" rx="18" fill="#ffffff" opacity="0.96"/>
    <text x="95" y="267" font-size="24" fill="#102033">掃描 {metadata.get("scanned_count", 0)} 檔</text>
    <rect x="395" y="230" width="290" height="58" rx="18" fill="#ffffff" opacity="0.96"/>
    <text x="420" y="267" font-size="24" fill="#102033">候選 {metadata.get("candidate_count", 0)} 檔</text>
    <rect x="720" y="230" width="290" height="58" rx="18" fill="#ffffff" opacity="0.96"/>
    <text x="745" y="267" font-size="24" fill="#102033">門檻 {metadata.get("threshold", 0)} 分</text>
  </g>
  {''.join(rows)}
  <text x="70" y="1274" font-size="21" fill="#50606f">分數：T 技術 / C 籌碼 / F 基本 / S 情緒。此報告為自動化分析，僅供研究與紀錄。</text>
  <text x="70" y="1310" font-size="19" fill="#798895">Taiwan Stock Scanner · daily_agent.py · {html.escape(str(metadata.get("run_id", "")))}</text>
</svg>
"""
    poster_path.write_text(svg, encoding="utf-8")
    return poster_path


def build_text_summary(metadata: dict) -> str:
    market = metadata.get("market_info", {})
    lines = [
        "台股晨間選股報告",
        f"時間：{metadata.get('created_at', '')}",
        f"市場：{market.get('description', 'N/A')}",
        f"掃描：{metadata.get('scanned_count', 0)} 檔，候選 {metadata.get('candidate_count', 0)} 檔，符合門檻 {metadata.get('qualified_count', 0)} 檔",
        "",
        "Top picks:",
    ]

    for index, stock in enumerate(metadata.get("results", [])[:5], 1):
        lines.append(
            f"{index}. {stock.get('stock_id')} {stock.get('name')} "
            f"{float(stock.get('total_score', 0)):.1f} 分"
        )
        for signal in collect_signals(stock, 2):
            lines.append(f"   - {signal}")

    if not metadata.get("results"):
        lines.append("今日沒有符合門檻的標的。")

    if metadata.get("report_path"):
        lines.append("")
        lines.append(f"HTML report: {metadata['report_path']}")

    lines.append("")
    lines.append("僅供研究與紀錄，不構成投資建議。")
    return "\n".join(lines)


def build_email_html(metadata: dict, poster_path: Path | None) -> str:
    stocks_html = []
    for index, stock in enumerate(metadata.get("results", [])[:10], 1):
        score = float(stock.get("total_score", 0))
        dims = stock.get("dimension_scores", {})
        signals = "".join(f"<li>{html.escape(signal)}</li>" for signal in collect_signals(stock, 4))
        stocks_html.append(
            f"""
            <tr>
              <td>{index}</td>
              <td><strong>{html.escape(str(stock.get('stock_id', '')))}</strong></td>
              <td>{html.escape(str(stock.get('name', '')))}</td>
              <td style="font-weight:700;color:{score_color(score)}">{score:.1f}</td>
              <td>{float(dims.get('technical', 0)):.0f}</td>
              <td>{float(dims.get('chips', 0)):.0f}</td>
              <td>{float(dims.get('fundamental', 0)):.0f}</td>
              <td>{float(dims.get('sentiment', 0)):.0f}</td>
              <td><ul>{signals}</ul></td>
            </tr>"""
        )

    if not stocks_html:
        stocks_html.append('<tr><td colspan="9">今日沒有符合門檻的標的。</td></tr>')

    market = metadata.get("market_info", {})
    poster_note = f"<p>已附上海報檔：{html.escape(poster_path.name)}</p>" if poster_path else ""
    report_note = (
        f"<p>完整 HTML 報告：{html.escape(str(metadata['report_path']))}</p>"
        if metadata.get("report_path")
        else ""
    )
    return f"""
<!doctype html>
<html lang="zh-Hant">
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#17202a">
  <h1>台股晨間選股報告</h1>
  <p><strong>時間：</strong>{html.escape(str(metadata.get('created_at', '')))}</p>
  <p><strong>市場：</strong>{html.escape(str(market.get('description', 'N/A')))}</p>
  <p><strong>掃描：</strong>{metadata.get('scanned_count', 0)} 檔，
     <strong>候選：</strong>{metadata.get('candidate_count', 0)} 檔，
     <strong>符合門檻：</strong>{metadata.get('qualified_count', 0)} 檔。</p>
  {poster_note}
  {report_note}
  <table cellspacing="0" cellpadding="8" border="1" style="border-collapse:collapse;border-color:#d6dde5;font-size:14px">
    <thead style="background:#eef4f8">
      <tr>
        <th>#</th><th>代號</th><th>名稱</th><th>總分</th>
        <th>技術</th><th>籌碼</th><th>基本</th><th>情緒</th><th>重點訊號</th>
      </tr>
    </thead>
    <tbody>{''.join(stocks_html)}</tbody>
  </table>
  <p style="color:#8a5b00;background:#fff8df;padding:12px;border:1px solid #f2d36b">
    免責聲明：本報告為系統自動分析，僅供研究與紀錄，不構成任何投資建議。
  </p>
</body>
</html>
"""


def attachment_payload(paths: Iterable[Path]) -> list[dict]:
    attachments = []
    for path in paths:
        if not path or not path.exists() or not path.is_file():
            continue
        attachments.append(
            {
                "filename": path.name,
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return attachments


def send_email(config: AgentConfig, subject: str, html_body: str, attachments: list[Path]) -> str:
    if not config.email_from or not config.email_to:
        return "skipped: EMAIL_FROM or EMAIL_TO is missing"

    if config.email_provider == "smtp":
        return send_email_smtp(config, subject, html_body, attachments)
    return send_email_resend(config, subject, html_body, attachments)


def send_email_resend(config: AgentConfig, subject: str, html_body: str, attachments: list[Path]) -> str:
    if not config.resend_api_key:
        return "skipped: RESEND_API_KEY is missing"

    payload = {
        "from": config.email_from,
        "to": config.email_to,
        "subject": subject,
        "html": html_body,
    }
    resend_attachments = attachment_payload(attachments)
    if resend_attachments:
        payload["attachments"] = resend_attachments

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {config.resend_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return f"sent: resend {response.json().get('id', '')}"


def send_email_smtp(config: AgentConfig, subject: str, html_body: str, attachments: list[Path]) -> str:
    if not config.smtp_host:
        return "skipped: SMTP_HOST is missing"

    message = EmailMessage()
    message["From"] = config.email_from
    message["To"] = ", ".join(config.email_to)
    message["Subject"] = subject
    message.set_content("請使用支援 HTML 的信箱閱讀本報告。")
    message.add_alternative(html_body, subtype="html")

    for path in attachments:
        if not path.exists() or not path.is_file():
            continue
        content_type, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.smtp_use_tls:
            smtp.starttls()
        if config.smtp_user:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)
    return "sent: smtp"


def send_line(config: AgentConfig, text: str) -> str:
    if not config.line_channel_access_token or not config.line_to:
        return "skipped: LINE_CHANNEL_ACCESS_TOKEN or LINE_TO is missing"

    messages = [{"type": "text", "text": text[:4900]}]
    if config.line_report_url:
        messages.append({"type": "text", "text": f"完整報告：{config.line_report_url}"})
    if config.line_poster_image_url:
        messages.append(
            {
                "type": "image",
                "originalContentUrl": config.line_poster_image_url,
                "previewImageUrl": config.line_poster_image_url,
            }
        )

    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {config.line_channel_access_token}",
            "Content-Type": "application/json",
        },
        json={"to": config.line_to, "messages": messages[:5]},
        timeout=30,
    )
    response.raise_for_status()
    return "sent: line push"


def write_manifest(metadata: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"daily_run_{metadata['run_id']}.json"
    manifest_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def run(config: AgentConfig, sample: bool = False) -> dict:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    configure_threshold(config.threshold)

    if sample:
        metadata = build_sample_metadata()
        metadata["threshold"] = config.threshold
    else:
        metadata = screener.run_screener(
            quick_mode=config.quick_mode,
            custom_list=config.stocks or None,
            return_metadata=True,
        )
    metadata = normalize_metadata(metadata)

    poster_path = generate_poster_svg(metadata, config.output_dir)
    metadata["poster_path"] = str(poster_path)

    subject = f"台股晨間選股報告 {datetime.now().strftime('%Y-%m-%d')}"
    html_body = build_email_html(metadata, poster_path)
    text_summary = build_text_summary(metadata)

    notification_results = {}
    attachments = [poster_path]
    if metadata.get("report_path"):
        attachments.append(Path(metadata["report_path"]))

    if config.dry_run:
        notification_results["email"] = "dry-run"
        notification_results["line"] = "dry-run"
    else:
        if config.send_email:
            notification_results["email"] = send_email(config, subject, html_body, attachments)
        else:
            notification_results["email"] = "disabled"
        if config.send_line:
            notification_results["line"] = send_line(config, text_summary)
        else:
            notification_results["line"] = "disabled"

    metadata["notifications"] = notification_results
    manifest_path = config.output_dir / f"daily_run_{metadata['run_id']}.json"
    metadata["manifest_path"] = str(manifest_path)
    write_manifest(metadata, config.output_dir)
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily Taiwan stock report agent.")
    parser.add_argument("--env-file", default=".env", help="Path to an env file. Defaults to .env.")
    parser.add_argument("--quick", action="store_true", help="Run scanner quick mode.")
    parser.add_argument("--stocks", nargs="+", help="Scan only specific stock IDs.")
    parser.add_argument("--threshold", type=int, help="Override minimum score threshold.")
    parser.add_argument("--send-email", action="store_true", help="Send email after report generation.")
    parser.add_argument("--send-line", action="store_true", help="Send LINE push message after report generation.")
    parser.add_argument("--dry-run", action="store_true", help="Generate outputs without sending notifications.")
    parser.add_argument("--sample", action="store_true", help="Use sample data without network calls.")
    parser.add_argument("--output-json", help="Write final metadata to this JSON path.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()
    load_env_file((BASE_DIR / args.env_file).resolve() if not Path(args.env_file).is_absolute() else Path(args.env_file))
    agent_config = AgentConfig.from_env(args)
    metadata = run(agent_config, sample=args.sample)

    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = BASE_DIR / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    LOGGER.info("Daily agent finished: %s", metadata.get("manifest_path"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
