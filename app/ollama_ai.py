from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any

from .config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT
from .portfolio import PortfolioService
from .screener import ScreenerService


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size: int = 0
    parameter_size: str = ""
    quantization_level: str = ""


@dataclass(frozen=True)
class AIAnalysisRequest:
    stock_id: str
    model: str
    prompt: str
    analysis_type: str
    think: bool = False


class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, default_model: str = OLLAMA_MODEL):
        self.host = host.rstrip("/")
        self.default_model = default_model

    def models(self) -> list[OllamaModel]:
        payload = self._json_request("/api/tags", method="GET")
        models = []
        for item in payload.get("models", []):
            details = item.get("details") or {}
            models.append(
                OllamaModel(
                    name=item.get("name") or item.get("model") or "",
                    size=int(item.get("size") or 0),
                    parameter_size=str(details.get("parameter_size") or ""),
                    quantization_level=str(details.get("quantization_level") or ""),
                )
            )
        return [item for item in models if item.name]

    def available(self) -> bool:
        try:
            return bool(self.models())
        except Exception:
            return False

    def generate(self, prompt: str, model: str = "", temperature: float = 0.2, think: bool = False) -> dict[str, str]:
        selected_model = model or self.default_model
        payload = self._json_request(
            "/api/generate",
            method="POST",
            body={
                "model": selected_model,
                "prompt": prompt,
                "stream": False,
                "think": think,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 8192,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response = str(payload.get("response") or "").strip()
        thinking = str(payload.get("thinking") or "").strip()
        if not response:
            raise OllamaError("Ollama returned an empty response.")
        return {"content": response, "thinking": thinking}

    def generate_stream(
        self,
        prompt: str,
        model: str = "",
        temperature: float = 0.2,
        think: bool = False,
    ) -> Iterator[dict[str, str]]:
        selected_model = model or self.default_model
        body = {
            "model": selected_model,
            "prompt": prompt,
            "stream": True,
            "think": think,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,
            },
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("error"):
                        raise OllamaError(str(payload.get("error")))
                    message = payload.get("message") or {}
                    thinking = str(payload.get("thinking") or message.get("thinking") or "")
                    content = str(payload.get("response") or message.get("content") or "")
                    if thinking:
                        yield {"type": "thinking", "content": thinking}
                    if content:
                        yield {"type": "content", "content": content}
                    if payload.get("done"):
                        yield {"type": "done", "content": ""}
        except Exception as exc:
            raise OllamaError(str(exc)) from exc

    def _json_request(
        self,
        path: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        timeout: float = 10,
    ) -> dict[str, Any]:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{self.host}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise OllamaError(str(exc)) from exc


class AIAnalysisService:
    def __init__(
        self,
        screener: ScreenerService,
        ollama: OllamaClient | None = None,
        portfolio: PortfolioService | None = None,
    ):
        self.screener = screener
        self.ollama = ollama or OllamaClient()
        self.portfolio = portfolio

    def status(self) -> dict[str, Any]:
        try:
            models = self.ollama.models()
            return {
                "available": bool(models),
                "host": self.ollama.host,
                "default_model": self.ollama.default_model,
                "models": [model.__dict__ for model in models],
            }
        except OllamaError as exc:
            return {
                "available": False,
                "host": self.ollama.host,
                "default_model": self.ollama.default_model,
                "models": [],
                "error": str(exc),
            }

    def analyze_stock(self, body: dict[str, Any]) -> dict[str, Any]:
        request = self.prepare_stock_analysis(body)
        if isinstance(request, dict):
            return request
        return self._generate_response(request)

    def prepare_stock_analysis(self, body: dict[str, Any]) -> AIAnalysisRequest | dict[str, Any]:
        stock_id = str(body.get("stock_id") or "").strip()
        if not stock_id:
            return {"error": "missing_stock_id"}
        include_demo = bool(body.get("demo", False))
        analysis_mode = str(body.get("analysis_mode") or body.get("mode") or "short")
        report = self.screener.stock_report(stock_id, include_demo=include_demo, analysis_mode=analysis_mode)
        if report.get("error"):
            return report
        model = str(body.get("model") or self.ollama.default_model)
        question = str(body.get("question") or "").strip()
        prompt = self._stock_prompt(report, question)
        return AIAnalysisRequest(stock_id, model, prompt, "stock_analysis", _bool(body.get("think")))

    def analyze_position(self, body: dict[str, Any]) -> dict[str, Any]:
        request = self.prepare_position_analysis(body)
        if isinstance(request, dict):
            return request
        return self._generate_response(request)

    def prepare_position_analysis(self, body: dict[str, Any]) -> AIAnalysisRequest | dict[str, Any]:
        saved_position = None
        position_id = body.get("position_id")
        if self.portfolio and position_id not in (None, ""):
            try:
                saved_position = self.portfolio.get_position_context(int(position_id))
            except (TypeError, ValueError):
                saved_position = None
        stock_id = str(body.get("stock_id") or (saved_position or {}).get("stock_id") or "").strip()
        if not stock_id:
            return {"error": "missing_stock_id"}
        include_demo = bool(body.get("demo", False))
        analysis_mode = str(body.get("analysis_mode") or body.get("mode") or "short")
        report = self.screener.stock_report(stock_id, include_demo=include_demo, analysis_mode=analysis_mode)
        if report.get("error"):
            return report
        model = str(body.get("model") or self.ollama.default_model)
        position = self._position_context(body, saved_position)
        prompt = self._position_prompt(report, position)
        return AIAnalysisRequest(stock_id, model, prompt, "position_analysis", _bool(body.get("think")))

    def _position_context(self, body: dict[str, Any], saved_position: dict[str, Any] | None) -> dict[str, Any]:
        saved_position = saved_position or {}
        return {
            "持股紀錄ID": saved_position.get("id") or body.get("position_id") or "未提供",
            "持股股數": body.get("shares") or saved_position.get("shares") or "未提供",
            "平均買入價": body.get("average_cost") or saved_position.get("average_cost") or "未提供",
            "目前市價": saved_position.get("latest_price") or "未提供",
            "成本總額": saved_position.get("cost_basis") or "未提供",
            "目前市值": saved_position.get("market_value") or "未提供",
            "未實現損益": saved_position.get("unrealized_pnl") or "未提供",
            "未實現損益百分比": saved_position.get("unrealized_pnl_pct") or "未提供",
            "買入日期": saved_position.get("buy_date") or "未提供",
            "目前持股狀態": body.get("position_status") or saved_position.get("position_status") or "未提供",
            "投資週期": body.get("horizon") or saved_position.get("horizon") or "短線1-5日",
            "風險承受度": body.get("risk_profile") or saved_position.get("risk_profile") or "中等",
            "補充說明": body.get("notes") or saved_position.get("notes") or "",
        }

    def stream_response(self, request: AIAnalysisRequest) -> Iterator[dict[str, Any]]:
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        yield {
            "event": "meta",
            "data": {
                "stock_id": request.stock_id,
                "model": request.model,
                "analysis_type": request.analysis_type,
                "think": request.think,
            },
        }
        try:
            for chunk in self.ollama.generate_stream(request.prompt, model=request.model, think=request.think):
                chunk_type = chunk.get("type")
                content = chunk.get("content") or ""
                if chunk_type == "thinking" and content:
                    thinking_parts.append(content)
                    yield {"event": "thinking", "data": {"content": content}}
                elif chunk_type == "content" and content:
                    content_parts.append(content)
                    yield {"event": "content", "data": {"content": content}}
            yield {
                "event": "done",
                "data": {
                    "stock_id": request.stock_id,
                    "model": request.model,
                    "analysis_type": request.analysis_type,
                    "think": request.think,
                    "content": "".join(content_parts).strip(),
                    "thinking": "".join(thinking_parts).strip(),
                },
            }
        except OllamaError as exc:
            yield {
                "event": "error",
                "data": {
                    "stock_id": request.stock_id,
                    "model": request.model,
                    "analysis_type": request.analysis_type,
                    "error": "ollama_error",
                    "message": str(exc),
                },
            }

    def _generate_response(self, request: AIAnalysisRequest) -> dict[str, Any]:
        try:
            result = self.ollama.generate(request.prompt, model=request.model, think=request.think)
            thinking = ""
            if isinstance(result, dict):
                text = str(result.get("content") or "")
                thinking = str(result.get("thinking") or "")
            else:
                text = str(result)
            return {
                "stock_id": request.stock_id,
                "model": request.model,
                "analysis_type": request.analysis_type,
                "content": text,
                "thinking": thinking,
                "think": request.think,
            }
        except OllamaError as exc:
            return {
                "stock_id": request.stock_id,
                "model": request.model,
                "analysis_type": request.analysis_type,
                "error": "ollama_error",
                "message": str(exc),
            }

    def _stock_prompt(self, report: dict[str, Any], question: str = "") -> str:
        context = _compact_report(report)
        extra_question = question or "請針對這檔股票給出短線、波段與中長線都可參考的買賣建議。"
        return f"""你是台股投資分析助理。請使用繁體中文，根據下列系統化資料分析該股票，並同時考量短線、波段與中長線觀察角度。

重要規則：
1. 不要宣稱保證獲利。
2. 請把建議寫成研究輔助，不構成投資建議。
3. 請明確區分：可以買、觀察、等待拉回、避開。
4. 必須使用資料中的技術面、籌碼面、情緒面、風控面。
5. 若資料不足，請明確說資料不足，不要臆測。

請用 Markdown 小標題與條列輸出，讓前端可以整理成報告卡片。每段保持精簡，避免大段文字。
請固定輸出以下段落：
## 一句話結論
## 多空判斷
## 買入條件
## 不買/避開條件
## 停損與停利規劃
## 需要補充觀察的資料
## 最後提醒

使用者問題：
{extra_question}

股票資料：
{json.dumps(context, ensure_ascii=False, indent=2)}
"""

    def _position_prompt(self, report: dict[str, Any], position: dict[str, Any]) -> str:
        context = _compact_report(report)
        return f"""你是台股持股風控助理。請使用繁體中文，根據股票資料與使用者持股狀態，分析應該續抱、加碼、減碼、停損或等待。

重要規則：
1. 不要宣稱保證獲利。
2. 請把建議寫成研究輔助，不構成投資建議。
3. 必須把使用者買入價與目前觀察價/停損價比較。
4. 如果缺少股數或成本，請仍可分析，但要標示缺少哪些資訊。
5. 請給出清楚的條件式策略，不要只給籠統結論。

請用 Markdown 小標題與條列輸出，讓前端可以整理成報告卡片。每段保持精簡，避免大段文字。
請固定輸出以下段落：
## 一句話結論
## 目前部位狀態
## 若要續抱的條件
## 若要加碼的條件
## 若要減碼或停損的條件
## 風險與注意事項
## 行動清單

使用者持股狀態：
{json.dumps(position, ensure_ascii=False, indent=2)}

股票資料：
{json.dumps(context, ensure_ascii=False, indent=2)}
"""


def _compact_report(report: dict[str, Any]) -> dict[str, Any]:
    score = report.get("score") or {}
    details = score.get("details") or {}
    breakdown = details.get("indicator_breakdown") or {}
    compact_breakdown = {}
    for key, group in breakdown.items():
        compact_breakdown[key] = {
            "label": group.get("label"),
            "score": group.get("score"),
            "direction": group.get("direction"),
            "summary": group.get("summary"),
            "indicators": [
                {
                    "label": item.get("label"),
                    "value": item.get("value"),
                    "unit": item.get("unit"),
                    "impact": item.get("impact"),
                    "state": item.get("state"),
                    "explanation": item.get("explanation"),
                }
                for item in (group.get("indicators") or [])[:8]
            ],
        }
    return {
        "stock": report.get("stock"),
        "score": {
            "buy_score": score.get("buy_score"),
            "technical_score": score.get("technical_score"),
            "chip_score": score.get("chip_score"),
            "sentiment_score": score.get("sentiment_score"),
            "risk_score": score.get("risk_score"),
            "decision": score.get("decision"),
            "entry_watch_price": score.get("entry_watch_price"),
            "stop_loss_price": score.get("stop_loss_price"),
            "target_zone": score.get("target_zone"),
            "buy_reason": score.get("buy_reason"),
            "avoid_reason": score.get("avoid_reason"),
            "data_freshness": score.get("data_freshness"),
        },
        "analysis_mode": details.get("analysis_mode"),
        "analysis_mode_label": details.get("analysis_mode_label"),
        "analysis_mode_description": details.get("analysis_mode_description"),
        "portfolio_horizon": details.get("portfolio_horizon"),
        "direction": details.get("direction"),
        "investment_advice": details.get("investment_advice"),
        "local_rule_model": details.get("local_model"),
        "latest_price": details.get("latest_price"),
        "latest_volume": details.get("latest_volume"),
        "ma": {"ma5": details.get("ma5"), "ma10": details.get("ma10"), "ma20": details.get("ma20")},
        "technical": {
            "volume_ratio": details.get("volume_ratio"),
            "rsi14": details.get("rsi14"),
            "macd": details.get("macd"),
            "kd": details.get("kd"),
            "atr_ratio": details.get("atr_ratio"),
            "change_5d": details.get("change_5d"),
            "change_20d": details.get("change_20d"),
        },
        "latest_flow": details.get("latest_flow"),
        "latest_margin": details.get("latest_margin"),
        "indicator_breakdown": compact_breakdown,
        "news": [
            {
                "title": item.get("title"),
                "source": item.get("source"),
                "published_at": item.get("published_at"),
                "sentiment": item.get("sentiment"),
            }
            for item in (report.get("news") or [])[:6]
        ],
    }


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}
