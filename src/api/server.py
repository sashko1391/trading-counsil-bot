"""
FastAPI server — War Room backend for Oil Trading Intelligence Bot.

Exposes REST endpoints + WebSocket for the React frontend.
Runs alongside the main bot loop.

USAGE:
    uvicorn api.server:app --reload --port 8000
    # or from project root:
    cd src && uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from models.schemas import (
    CouncilResponse,
    MarketEvent,
    OilForecast,
    OilRiskScore,
    RiskCheck,
    Signal,
)

app = FastAPI(
    title="Oil Trading Intelligence — War Room API",
    version="1.0.0",
    description="Backend for the War Room dashboard",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory state (populated by the bot loop or mocks) ─────────────────────

class BotState:
    """Shared mutable state between the bot loop and the API."""

    def __init__(self):
        self.latest_forecast: Optional[dict] = None
        self.latest_council: Optional[dict] = None
        self.latest_risk_check: Optional[dict] = None
        self.latest_risk_score: Optional[dict] = None
        self.agent_statuses: dict = {}
        self.signal_history: list[dict] = []
        self.prices: dict = {}
        self.context: dict = {}
        self.upcoming_events: list[dict] = []
        self.bot_started_at: Optional[datetime] = None
        self.last_cycle_at: Optional[datetime] = None
        self.total_cycles: int = 0
        self.system_status: str = "idle"

    def push_result(self, result: dict) -> None:
        """Called after each analyze_event cycle to update state."""
        council: CouncilResponse = result["council_response"]
        risk_check: RiskCheck = result["risk_check"]
        signals: dict[str, Signal] = result["signals"]
        forecast: Optional[OilForecast] = result.get("forecast")
        context: dict = result.get("context", {})

        self.latest_council = council.model_dump(mode="json")
        self.latest_risk_check = risk_check.model_dump(mode="json")
        self.latest_risk_score = (
            risk_check.oil_risk_score.model_dump(mode="json")
            if risk_check.oil_risk_score else None
        )

        if forecast:
            self.latest_forecast = forecast.model_dump(mode="json")

        # Agent statuses
        action_to_status = {"LONG": "BULLISH", "SHORT": "BEARISH", "WAIT": "NEUTRAL"}
        for name, sig in signals.items():
            self.agent_statuses[name] = {
                "name": name,
                "action": sig.action,
                "status": action_to_status.get(sig.action, "NEUTRAL"),
                "confidence": sig.confidence,
                "thesis": sig.thesis,
                "risk_notes": sig.risk_notes,
                "sources": sig.sources,
            }

        # Signal history (prepend, keep last 50)
        self.signal_history.insert(0, {
            "time": datetime.now().strftime("%H:%M"),
            "instrument": council.instrument,
            "consensus": council.consensus,
            "consensus_strength": council.consensus_strength,
            "confidence": council.combined_confidence,
            "action": council.consensus,
            "reason": forecast.drivers[0] if forecast and forecast.drivers else council.recommendation.get("reason", ""),
            "price": context.get("prices", {}).get(council.instrument, {}).get("price", 0),
            "allowed": risk_check.allowed,
        })
        self.signal_history = self.signal_history[:50]

        # Context
        self.prices = context.get("prices", self.prices)
        self.upcoming_events = context.get("upcoming_events", self.upcoming_events)
        self.context = context

        self.last_cycle_at = datetime.now()
        self.total_cycles += 1
        self.system_status = "active"

        # Notify WebSocket subscribers (may be called from bot thread)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_broadcast_update())
            else:
                loop.run_until_complete(_broadcast_update())
        except RuntimeError:
            pass  # no event loop in this thread — WS clients will get data on next poll


state = BotState()


# ── WebSocket management ─────────────────────────────────────────────────────

_ws_clients: set[WebSocket] = set()


async def _broadcast_update():
    """Push latest state to all connected WebSocket clients."""
    global _ws_clients
    if not _ws_clients:
        return
    payload = json.dumps({
        "type": "update",
        "prices": state.prices,
        "forecast": state.latest_forecast,
        "risk_score": state.latest_risk_score,
        "agents": state.agent_statuses,
        "latest_signal": state.signal_history[0] if state.signal_history else None,
        "timestamp": datetime.now().isoformat(),
    })
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """System status overview."""
    return {
        "status": state.system_status,
        "bot_started_at": state.bot_started_at.isoformat() if state.bot_started_at else None,
        "last_cycle_at": state.last_cycle_at.isoformat() if state.last_cycle_at else None,
        "total_cycles": state.total_cycles,
        "connected_clients": len(_ws_clients),
    }


@app.get("/api/forecast")
async def get_forecast():
    """Latest OilForecast."""
    return state.latest_forecast or {"message": "No forecast yet"}


@app.get("/api/council")
async def get_council():
    """Latest CouncilResponse (all agent votes + consensus)."""
    return state.latest_council or {"message": "No council response yet"}


@app.get("/api/agents")
async def get_agents():
    """Current agent statuses."""
    return state.agent_statuses or {"message": "No agent data yet"}


@app.get("/api/risk")
async def get_risk():
    """Latest risk check + score."""
    return {
        "risk_check": state.latest_risk_check,
        "risk_score": state.latest_risk_score,
    }


@app.get("/api/prices")
async def get_prices():
    """Current instrument prices."""
    return state.prices or {"message": "No price data yet"}


@app.get("/api/signals")
async def get_signals(limit: int = 20):
    """Signal history (most recent first)."""
    return state.signal_history[:limit]


@app.get("/api/events")
async def get_events():
    """Upcoming scheduled events."""
    return state.upcoming_events or []


@app.get("/api/context")
async def get_context():
    """Full market context snapshot."""
    return state.context or {"message": "No context yet"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time updates via WebSocket."""
    await ws.accept()
    _ws_clients.add(ws)
    logger.info(f"WS client connected ({len(_ws_clients)} total)")

    # Send initial state
    await ws.send_text(json.dumps({
        "type": "init",
        "prices": state.prices,
        "forecast": state.latest_forecast,
        "risk_score": state.latest_risk_score,
        "agents": state.agent_statuses,
        "signals": state.signal_history[:10],
        "events": state.upcoming_events,
        "status": state.system_status,
    }))

    try:
        while True:
            # Keep connection alive, receive client messages if needed
            data = await ws.receive_text()
            # Could handle client commands here in the future
    except WebSocketDisconnect:
        _ws_clients.discard(ws)
        logger.info(f"WS client disconnected ({len(_ws_clients)} total)")


# ── Journal endpoints ─────────────────────────────────────────────────────────

# ── History endpoints ─────────────────────────────────────────────────────────

@app.get("/api/history/digests")
async def get_digest_history(instrument: str = "BZ=F", limit: int = 24):
    """Digest history for an instrument."""
    try:
        from journal.digest_history import DigestHistory
        dh = DigestHistory()
        records = dh.get_recent(instrument, n=limit)
        return [r.to_dict() for r in records]
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/history/daily")
async def get_daily_history(instrument: str = "BZ=F", limit: int = 30):
    """Daily summaries for an instrument."""
    try:
        from journal.daily_summary import DailySummaryHistory
        ds = DailySummaryHistory()
        records = ds.get_recent(instrument, n=limit)
        return [r.to_dict() for r in records]
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/history/agents")
async def get_agent_history(agent: str = "grok", instrument: str = "BZ=F", limit: int = 20):
    """Agent memory for a specific agent + instrument."""
    try:
        from journal.agent_memory import AgentMemory
        am = AgentMemory()
        entries = am.get_history(agent, instrument, n=limit)
        return [e.to_dict() for e in entries]
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/history/agents/all")
async def get_all_agents_history(instrument: str = "BZ=F", limit: int = 10):
    """Latest memory entries for all agents."""
    try:
        from journal.agent_memory import AgentMemory
        am = AgentMemory()
        result = {}
        for agent in ["grok", "perplexity", "claude", "gemini"]:
            entries = am.get_history(agent, instrument, n=limit)
            result[agent] = [e.to_dict() for e in entries]
        return result
    except Exception as exc:
        return {"error": str(exc)}


# ── Journal endpoints ─────────────────────────────────────────────────────────

@app.get("/api/journal")
async def get_journal(limit: int = 20):
    """Recent trade journal entries."""
    try:
        journal_path = Path("data/trades_dryrun.json")
        if not journal_path.exists():
            journal_path = Path("data/trades.json")
        if not journal_path.exists():
            return []
        entries = json.loads(journal_path.read_text())
        return entries[-limit:]
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/journal/stats")
async def get_journal_stats():
    """Journal statistics."""
    try:
        from journal.trade_journal import TradeJournal
        journal = TradeJournal()
        return journal.get_stats()
    except Exception as exc:
        return {"error": str(exc)}
