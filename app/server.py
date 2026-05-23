from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo

from .config import ENABLE_SCHEDULER, ROOT_DIR
from .ollama_ai import AIAnalysisService
from .portfolio import PortfolioService
from .screener import ScreenerService

STATIC_DIR = ROOT_DIR / "static"
service = ScreenerService()
portfolio_service = PortfolioService(service.storage)
ai_service = AIAnalysisService(service, portfolio=portfolio_service)


class StockScreenerHandler(BaseHTTPRequestHandler):
    server_version = "TaiwanStockScreener/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        if path == "/api/health":
            self._json({"status": "ok", "scheduler": ENABLE_SCHEDULER})
            return
        if path == "/api/ai/status":
            self._json(ai_service.status())
            return
        if path == "/api/portfolio":
            self._json(portfolio_service.list_positions())
            return
        if path == "/api/screener/today":
            query.pop("demo", None)
            self._json(service.today_scores(query))
            return
        if path.startswith("/api/stocks/") and path.endswith("/report"):
            stock_id = unquote(path.split("/")[3])
            self._json(service.stock_report(stock_id, include_demo=False, analysis_mode=query.get("mode") or query.get("analysis_mode") or "short"))
            return
        if path.startswith("/api/stocks/") and path.endswith("/signals"):
            stock_id = unquote(path.split("/")[3])
            self._json(service.stock_signals(stock_id, include_demo=False, analysis_mode=query.get("mode") or query.get("analysis_mode") or "short"))
            return
        if path == "/api/backtest":
            self._json(service.backtest(include_demo=False, analysis_mode=query.get("mode") or query.get("analysis_mode") or "short"))
            return
        if path.startswith("/api/"):
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/screener/run":
            body = self._read_json()
            mode = str(body.get("mode", "after_hours"))
            self._json(service.run(use_demo=False, mode=mode, analysis_mode=str(body.get("analysis_mode") or "short")))
            return
        if parsed.path == "/api/ai/analyze-stock":
            body = self._read_json()
            body.pop("demo", None)
            self._json(ai_service.analyze_stock(body))
            return
        if parsed.path == "/api/ai/analyze-stock-stream":
            body = self._read_json()
            body.pop("demo", None)
            self._ai_stream(ai_service.prepare_stock_analysis(body))
            return
        if parsed.path == "/api/ai/analyze-position":
            body = self._read_json()
            body.pop("demo", None)
            self._json(ai_service.analyze_position(body))
            return
        if parsed.path == "/api/ai/analyze-position-stream":
            body = self._read_json()
            body.pop("demo", None)
            self._ai_stream(ai_service.prepare_position_analysis(body))
            return
        if parsed.path == "/api/portfolio":
            try:
                self._json(portfolio_service.add_position(self._read_json()))
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path.startswith("/api/portfolio/") and parsed.path.endswith("/delete"):
            try:
                position_id = int(parsed.path.split("/")[3])
            except (ValueError, IndexError):
                self._json({"error": "invalid_position_id"}, HTTPStatus.BAD_REQUEST)
                return
            self._json(portfolio_service.delete_position(position_id))
            return
        if parsed.path.startswith("/api/portfolio/") and parsed.path.endswith("/sell"):
            try:
                position_id = int(parsed.path.split("/")[3])
                self._json(portfolio_service.sell_position(position_id, self._read_json()))
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except IndexError:
                self._json({"error": "invalid_position_id"}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path.startswith("/api/portfolio/"):
            try:
                position_id = int(parsed.path.split("/")[3])
                self._json(portfolio_service.update_position(position_id, self._read_json()))
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except IndexError:
                self._json({"error": "invalid_position_id"}, HTTPStatus.BAD_REQUEST)
            return
        else:
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _ai_stream(self, request: object) -> None:
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            if isinstance(request, dict):
                self._write_sse("error", request)
                return
            for event in ai_service.stream_response(request):
                self._write_sse(str(event.get("event") or "message"), event.get("data") or {})
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _write_sse(self, event_name: str, payload: dict) -> None:
        body = f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _static(self, path: str) -> None:
        requested = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (STATIC_DIR / requested).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists() or file_path.is_dir():
            file_path = STATIC_DIR / "index.html"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        body = file_path.read_bytes()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


def scheduler_loop() -> None:
    last_after_hours_run = ""
    while True:
        now = datetime.now(ZoneInfo("Asia/Taipei"))
        if now.weekday() < 5 and now.hour >= 14 and now.minute >= 15 and last_after_hours_run != now.date().isoformat():
            service.run(use_demo=False, mode="after_hours")
            last_after_hours_run = now.date().isoformat()
        time.sleep(15 * 60)


def _discover_lan_urls(port: int) -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass

    return [f"http://{ip}:{port}/" for ip in sorted(addresses)]


def _print_startup_urls(host: str, port: int) -> None:
    if host in {"0.0.0.0", "::", ""}:
        print(f"Local URL: http://127.0.0.1:{port}/")
        lan_urls = _discover_lan_urls(port)
        if lan_urls:
            print("LAN URLs for phones/tablets on the same Wi-Fi:")
            for url in lan_urls:
                print(f"  {url}")
        else:
            print("LAN access is enabled. Use ipconfig to find this PC's IPv4 address.")
    else:
        print(f"Serving on http://{host}:{port}/")
        print("LAN access is disabled because the server is bound to a single local address.")
        print(f"For phone access on the same Wi-Fi, restart with: python run_app.py --host 0.0.0.0 --port {port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Taiwan stock investment analysis system")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    if ENABLE_SCHEDULER:
        threading.Thread(target=scheduler_loop, daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), StockScreenerHandler)
    _print_startup_urls(args.host, args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
