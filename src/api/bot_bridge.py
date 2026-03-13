"""
Bridge: connect TradingCouncil pipeline to the FastAPI state.

Monkey-patches TradingCouncil.analyze_event to push results
into api.server.state after each cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from main import TradingCouncil


def wire_bot_to_api(council: "TradingCouncil") -> None:
    """
    Wrap council.analyze_event so each result is pushed to the API state.
    Also wraps run_once to capture forecasts.
    Call this BEFORE council.run() / council.run_once().
    """
    from api.server import state

    state.bot_started_at = datetime.now()
    state.system_status = "active"

    original_analyze = council.analyze_event

    def patched_analyze(event, context):
        result = original_analyze(event, context)
        try:
            state.push_result({**result, "context": context})
        except Exception as exc:
            logger.warning(f"API state push failed: {exc}")
        return result

    council.analyze_event = patched_analyze

    # Also patch run_once to capture forecasts after they're built
    original_run_once = council.run_once

    async def patched_run_once():
        results = await original_run_once()
        for r in results:
            forecast = r.get("forecast")
            if forecast:
                try:
                    state.latest_forecast = forecast.model_dump(mode="json")
                    logger.info(f"Forecast pushed to API: {forecast.direction} {forecast.confidence:.0%}")
                    # Broadcast to WS clients
                    try:
                        from api.server import _broadcast_update
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(_broadcast_update())
                    except Exception:
                        pass
                except Exception as exc:
                    logger.warning(f"Forecast push failed: {exc}")
        return results

    council.run_once = patched_run_once
    logger.info("Bot → API bridge wired")
