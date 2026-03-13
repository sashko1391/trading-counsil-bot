"""
Combined launcher: FastAPI server + Bot loop running together.

USAGE:
    cd src && python -m api.run                    # real agents + API
    cd src && python -m api.run --dry-run           # mock agents + API
    cd src && python -m api.run --dry-run --once    # single cycle + API stays alive
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import threading
from pathlib import Path

import uvicorn
from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="Oil Trading Bot + War Room API")
    parser.add_argument("--dry-run", action="store_true", help="Mock agents")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval (s)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="API port")
    parser.add_argument("--api-only", action="store_true", help="Only run API server (no bot loop)")
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        level="INFO",
    )

    if args.api_only:
        logger.info(f"Starting API-only on port {args.port}")
        uvicorn.run("api.server:app", host="0.0.0.0", port=args.port, reload=False, log_level="warning")
        return

    # Import bot components
    from main import (
        TradingCouncil, create_mock_agents, create_real_agents,
        Aggregator, RiskGovernor, TradeJournal, TelegramNotifier,
        OilPriceWatcher, OilNewsScanner, ScheduledEventsManager, EIAClient,
    )
    from config.settings import get_settings
    from api.bot_bridge import wire_bot_to_api

    # Build council
    if args.dry_run:
        logger.info("DRY-RUN MODE")
        agents = create_mock_agents()
        journal_path = Path("data/trades_dryrun.json")
        telegram_token = None
        telegram_chat = None
        telegram_chat_ids = None
        min_confidence = 0.6
        eia_key = ""
    else:
        settings = get_settings()
        agents = create_real_agents(settings)
        journal_path = settings.JOURNAL_PATH
        telegram_token = settings.TELEGRAM_BOT_TOKEN
        telegram_chat = settings.TELEGRAM_CHAT_ID
        telegram_chat_ids = settings.TELEGRAM_CHAT_IDS
        min_confidence = settings.MIN_CONFIDENCE
        eia_key = settings.EIA_API_KEY

    council = TradingCouncil(
        agents=agents,
        aggregator=Aggregator(),
        risk_governor=RiskGovernor(),
        journal=TradeJournal(journal_path=journal_path),
        notifier=TelegramNotifier(bot_token=telegram_token, chat_id=telegram_chat, chat_ids=telegram_chat_ids),
        price_watcher=OilPriceWatcher(),
        news_scanner=OilNewsScanner(),
        events_manager=ScheduledEventsManager(),
        eia_client=EIAClient(api_key=eia_key),
        dry_run=args.dry_run,
        min_confidence=min_confidence,
    )

    wire_bot_to_api(council)

    # Start API server in a background thread
    api_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": "api.server:app", "host": "0.0.0.0", "port": args.port, "log_level": "warning"},
        daemon=True,
    )
    api_thread.start()
    logger.info(f"War Room API started on http://localhost:{args.port}")

    # Graceful shutdown
    loop = asyncio.new_event_loop()

    def signal_handler(sig, frame):
        council.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot
    if args.once:
        logger.info("Running ONE cycle...")
        results = loop.run_until_complete(council.run_once())
        logger.info(f"Results: {len(results)} events analysed")
        # Keep API alive after --once so you can inspect results
        logger.info("Bot cycle done. API still running. Ctrl+C to exit.")
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
    else:
        loop.run_until_complete(council.run(poll_interval=args.interval))


if __name__ == "__main__":
    main()
