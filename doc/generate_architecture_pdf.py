#!/usr/bin/env python3
"""Generate Architecture PDF for Oil Trading Intelligence Bot."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

# Colors
DARK = HexColor("#1a1a2e")
ACCENT = HexColor("#00d4aa")
ACCENT2 = HexColor("#0099ff")
GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#f0f0f0")
TABLE_HEADER = HexColor("#1a1a2e")
TABLE_ALT = HexColor("#f8f9fa")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "ARCHITECTURE.pdf")


def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "Cover", fontSize=28, leading=34, textColor=DARK,
        alignment=TA_CENTER, spaceAfter=12, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "CoverSub", fontSize=14, leading=18, textColor=GRAY,
        alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "H1", fontSize=18, leading=22, textColor=DARK,
        spaceBefore=20, spaceAfter=10, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "H2", fontSize=14, leading=17, textColor=DARK,
        spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "H3", fontSize=11, leading=14, textColor=DARK,
        spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "Body", fontSize=10, leading=14, textColor=black,
        spaceAfter=6, fontName="Helvetica", alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        "BulletItem", fontSize=10, leading=14, textColor=black,
        spaceAfter=3, fontName="Helvetica", leftIndent=18,
        bulletIndent=6, bulletFontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "CodeBlock", fontSize=9, leading=12, textColor=HexColor("#333"),
        fontName="Courier", backColor=LIGHT_GRAY, leftIndent=12,
        rightIndent=12, spaceBefore=4, spaceAfter=4,
        borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        "Caption", fontSize=8, leading=10, textColor=GRAY,
        alignment=TA_CENTER, spaceAfter=8, fontName="Helvetica-Oblique",
    ))
    styles.add(ParagraphStyle(
        "Footer", fontSize=8, leading=10, textColor=GRAY,
        alignment=TA_CENTER, fontName="Helvetica",
    ))
    return styles


def make_table(headers, rows, col_widths=None):
    """Create a styled table."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT))
    t.setStyle(TableStyle(style))
    return t


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceBefore=6, spaceAfter=6)


def build_pdf():
    s = build_styles()
    story = []

    # ── COVER ──
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("OIL TRADING INTELLIGENCE BOT", s["Cover"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("System Architecture Document", s["CoverSub"]))
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph("Version 1.0", s["CoverSub"]))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", s["CoverSub"]))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("CONFIDENTIAL", s["CoverSub"]))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──
    story.append(Paragraph("Table of Contents", s["H1"]))
    toc = [
        "1. Executive Summary",
        "2. System Architecture Overview",
        "3. Data Sources & Event Detection",
        "4. AI Agents & Analysis",
        "5. Consensus Aggregation",
        "6. Risk Governance",
        "7. Notifications & Persistence",
        "8. Knowledge Retrieval (RAG)",
        "9. API Server & Frontend",
        "10. Deployment Architecture",
        "11. Data Models & Schemas",
        "12. External Dependencies",
        "13. Security & Compliance",
        "14. Performance Characteristics",
        "15. Operational Costs",
    ]
    for item in toc:
        story.append(Paragraph(item, s["Body"]))
    story.append(PageBreak())

    # ── 1. EXECUTIVE SUMMARY ──
    story.append(Paragraph("1. Executive Summary", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Oil Trading Intelligence Bot is a multi-agent AI system that monitors crude oil and "
        "refined products markets in real-time. It combines four specialized AI agents (Claude, Grok, "
        "Perplexity, Gemini) with automated market monitoring, consensus-based decision-making, "
        "risk governance, and instant notifications via Telegram.",
        s["Body"]
    ))
    story.append(Paragraph(
        "The system targets <b>Brent Crude (BZ=F)</b> and <b>Distillates (HO=F proxy)</b> exclusively, "
        "using a deterministic 5-stage pipeline: Event Detection, Agent Analysis, Consensus Aggregation, "
        "Risk Filtering, and Notification.",
        s["Body"]
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(make_table(
        ["Parameter", "Value"],
        [
            ["Target Instruments", "Brent Crude (BZ=F), Distillates (HO=F proxy)"],
            ["AI Agents", "4 (Claude, Grok, Perplexity, Gemini)"],
            ["Polling Interval", "15 minutes (configurable)"],
            ["Tech Stack", "Python 3.12, FastAPI, React, Docker"],
            ["Deployment", "Docker Compose + Caddy (auto-SSL)"],
            ["Tests", "466 passing"],
            ["Status", "Production (all 7 phases complete)"],
        ],
        col_widths=[50 * mm, 120 * mm],
    ))
    story.append(PageBreak())

    # ── 2. SYSTEM ARCHITECTURE ──
    story.append(Paragraph("2. System Architecture Overview", s["H1"]))
    story.append(hr())
    story.append(Paragraph("5-Stage Pipeline", s["H2"]))

    pipeline_data = [
        ["Stage", "Component", "Description"],
        ["1. Detection", "OilPriceWatcher\nOilNewsScanner\nScheduledEvents\n+6 enrichment watchers",
         "Detects price spikes, volume surges, news events, scheduled catalysts. "
         "Enriches with OVX volatility, DXY/currencies, COT positioning, weather, refinery margins, seasonal patterns."],
        ["2. Analysis", "4 AI Agents\n(parallel execution)",
         "Each agent independently analyzes the event and returns a structured Signal "
         "(action, confidence, thesis, risks, drivers)."],
        ["3. Aggregation", "Aggregator\n(deterministic Python)",
         "Confidence-weighted voting produces CouncilResponse with consensus "
         "(LONG/SHORT/WAIT/CONFLICT) and strength (UNANIMOUS/STRONG/WEAK/NONE)."],
        ["4. Risk", "RiskGovernor\n(6-category scoring)",
         "Evaluates geopolitical, supply, demand, financial, seasonal, and technical risks. "
         "Applies daily limits, cooldowns, and confidence thresholds."],
        ["5. Output", "TelegramNotifier\nTradeJournal\nForecastTracker\nFrontend Dashboard",
         "Sends alerts to Telegram, logs decisions, tracks forecast accuracy (Brier Score), "
         "and pushes updates to the War Room dashboard."],
    ]
    story.append(make_table(
        pipeline_data[0], pipeline_data[1:],
        col_widths=[28 * mm, 42 * mm, 100 * mm],
    ))
    story.append(PageBreak())

    # ── 3. DATA SOURCES ──
    story.append(Paragraph("3. Data Sources & Event Detection", s["H1"]))
    story.append(hr())

    story.append(Paragraph("3.1 Core Watchers", s["H2"]))
    story.append(make_table(
        ["Watcher", "Source", "Detects"],
        [
            ["OilPriceWatcher", "yfinance (BZ=F, HO=F)", "Price spikes (>2%), volume surges (>2x avg), crack spread changes (>5%)"],
            ["OilNewsScanner", "10 RSS feeds (EIA, Reuters, Bloomberg, OilPrice, OPEC...)", "Relevant oil news events with severity scoring"],
            ["ScheduledEvents", "Built-in calendar", "OPEC meetings, EIA reports, FOMC decisions"],
        ],
        col_widths=[35 * mm, 45 * mm, 90 * mm],
    ))

    story.append(Paragraph("3.2 Enrichment Sources", s["H2"]))
    story.append(make_table(
        ["Source", "Data", "API"],
        [
            ["OVX (^OVX)", "Oil volatility index, regime classification", "yfinance (free)"],
            ["DXY + Currencies", "Dollar index, EUR/USD, USD/CNY trends", "yfinance (free)"],
            ["CFTC COT", "Money Manager net positions, 52-week percentile", "CFTC SODA API (free)"],
            ["Weather/Hurricane", "Gulf Coast storm tracking, NOAA alerts", "NOAA NHC API (free)"],
            ["Refinery Margins", "3-2-1 crack spread, gasoline/heating oil cracks", "yfinance (free)"],
            ["Seasonal Patterns", "12-month demand database", "Built-in"],
            ["EIA Data", "Weekly petroleum status reports", "EIA API (free)"],
        ],
        col_widths=[35 * mm, 55 * mm, 80 * mm],
    ))

    story.append(Paragraph("3.3 Brent Price: Active Contract Resolution", s["H2"]))
    story.append(Paragraph(
        "Yahoo Finance's generic BZ=F ticker can roll to the next contract month before the actual "
        "front month expires. The system auto-detects this roll by checking the underlyingSymbol and "
        "falls back to the specific near-month contract (e.g., BZK26.NYM for May 2026), ensuring "
        "prices match TradingView and Investing.com.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 4. AI AGENTS ──
    story.append(Paragraph("4. AI Agents & Analysis", s["H1"]))
    story.append(hr())

    story.append(make_table(
        ["Agent", "Model", "Provider", "Role", "Focus"],
        [
            ["Claude", "claude-sonnet-4", "Anthropic", "Risk CFO",
             "Contango, crack spreads, OPEC compliance, geopolitical premium"],
            ["Grok", "grok-3", "xAI", "Sentiment Hunter",
             "X/Twitter sentiment, breaking news, rumours, tanker chatter"],
            ["Perplexity", "sonar", "Perplexity", "Fact Verifier",
             "EIA/IEA/OPEC data verification, inventory cross-reference"],
            ["Gemini", "gemini-2.5-flash", "Google", "Macro Analyst",
             "Seasonal demand, China trends, USD correlation, contango/backwardation"],
        ],
        col_widths=[22 * mm, 28 * mm, 22 * mm, 28 * mm, 70 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Agent Output: Signal Schema", s["H2"]))
    story.append(make_table(
        ["Field", "Type", "Description"],
        [
            ["action", "LONG / SHORT / WAIT", "Trading direction recommendation"],
            ["confidence", "0.0 - 1.0", "Agent's conviction level"],
            ["thesis", "string (max 500 chars)", "Reasoning in Ukrainian"],
            ["risk_notes", "string (max 500 chars)", "Key risks in Ukrainian"],
            ["invalidation_price", "float (optional)", "Price that invalidates the thesis"],
            ["drivers", "list (1-3)", "Key market drivers from taxonomy"],
            ["sources", "list of URLs", "Information sources"],
        ],
        col_widths=[35 * mm, 40 * mm, 95 * mm],
    ))

    story.append(Paragraph("Adversarial Stage (Devil's Advocate)", s["H2"]))
    story.append(Paragraph(
        "A virtual 5th agent argues against the consensus via a 3-step debate: "
        "primary thesis, counterargument, and final verdict. Includes sycophancy detection "
        "that penalizes confidence when the debate produces no substantive objections. "
        "This stage can shift combined confidence by up to +/-10%.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 5. AGGREGATION ──
    story.append(Paragraph("5. Consensus Aggregation", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Aggregator uses <b>deterministic Python code</b> (no AI) to combine 4 agent signals "
        "into a single CouncilResponse via confidence-weighted voting.",
        s["Body"]
    ))

    story.append(make_table(
        ["Strength", "Criteria"],
        [
            ["UNANIMOUS", "All 4 agents agree + combined confidence > 80%"],
            ["STRONG", "3+ agents agree + combined confidence > 70%"],
            ["WEAK", "Mixed votes + combined confidence 50-70%"],
            ["NONE", "No clear consensus or all agents say WAIT"],
        ],
        col_widths=[35 * mm, 135 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Agent weights are dynamically calibrated based on historical hit rates tracked via "
        "Brier Score. Overconfident agents are dampened; underconfident agents are boosted.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 6. RISK GOVERNANCE ──
    story.append(Paragraph("6. Risk Governance", s["H1"]))
    story.append(hr())

    story.append(Paragraph("6-Category OilRiskScore", s["H2"]))
    story.append(make_table(
        ["Category", "Weight", "Examples"],
        [
            ["Geopolitical", "25%", "Conflict, sanctions, chokepoint (Hormuz, Suez)"],
            ["Supply", "25%", "OPEC cuts, production disruptions, refinery outages"],
            ["Demand", "20%", "Recession risk, China slowdown, EV transition"],
            ["Financial", "10%", "Currency volatility, rate decisions, credit stress"],
            ["Seasonal", "10%", "Q1 heating demand, Q3 driving season"],
            ["Technical", "10%", "Volatility spikes, chart breakouts, OVX regime"],
        ],
        col_widths=[30 * mm, 20 * mm, 120 * mm],
    ))

    story.append(Paragraph("Gating Rules", s["H2"]))
    story.append(make_table(
        ["Rule", "Threshold", "Action"],
        [
            ["Low Confidence", "< 60%", "BLOCK alert"],
            ["Weak Consensus", "< STRONG", "BLOCK alert"],
            ["Daily Limit", "> 10 alerts/day", "BLOCK remaining"],
            ["Cooldown", "< 30 min since last", "BLOCK (prevent churn)"],
            ["High Risk", "Composite > 85%", "BLOCK alert"],
            ["OPEC Proximity", "Meeting within 24h", "Raise risk score"],
        ],
        col_widths=[35 * mm, 40 * mm, 95 * mm],
    ))
    story.append(PageBreak())

    # ── 7. NOTIFICATIONS ──
    story.append(Paragraph("7. Notifications & Persistence", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Component", "Purpose", "Storage"],
        [
            ["Telegram Notifier", "Real-time alerts to multiple chat IDs", "Telegram Bot API"],
            ["Digest Summarizer", "Periodic summary via Gemini Flash", "In-memory + Telegram"],
            ["Trade Journal", "Full audit trail of all decisions", "data/trades.json"],
            ["Daily Summary", "End-of-day trend + stats", "data/daily_summary.json"],
            ["Digest History", "Hourly/6-hourly alert archive", "data/digest_history.json"],
            ["Agent Memory", "Per-agent decision history for context injection", "data/agent_memory.json"],
            ["Forecast Tracker", "Brier Score + hit rate tracking", "data/forecast_tracker.json"],
        ],
        col_widths=[35 * mm, 55 * mm, 80 * mm],
    ))
    story.append(PageBreak())

    # ── 8. RAG ──
    story.append(Paragraph("8. Knowledge Retrieval (RAG)", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "Vector-backed knowledge retrieval enriches agent context with domain expertise.",
        s["Body"]
    ))
    story.append(make_table(
        ["Component", "Technology"],
        [
            ["Vector Database", "Pinecone (serverless)"],
            ["Embedding Model", "text-embedding-3-small (OpenAI, 1536 dims)"],
            ["Knowledge Base", "4 documents: fundamentals, OPEC history, seasonal patterns, EIA guide"],
            ["Query Flow", "Format query -> Embed -> Search top-5 similar chunks -> Inject into prompt"],
            ["Fallback", "If Pinecone/OpenAI unavailable, agents continue without RAG context"],
        ],
        col_widths=[35 * mm, 135 * mm],
    ))
    story.append(PageBreak())

    # ── 9. API & FRONTEND ──
    story.append(Paragraph("9. API Server & Frontend", s["H1"]))
    story.append(hr())

    story.append(Paragraph("9.1 REST API Endpoints", s["H2"]))
    story.append(make_table(
        ["Method", "Path", "Description"],
        [
            ["GET", "/api/status", "System status, uptime, connected clients"],
            ["GET", "/api/forecast", "Latest OilForecast"],
            ["GET", "/api/council", "Latest CouncilResponse (all agent votes)"],
            ["GET", "/api/prices", "Current BZ=F & LGO prices"],
            ["GET", "/api/agents", "Agent statuses"],
            ["GET", "/api/risk", "Risk check + 6-category score"],
            ["GET", "/api/signals", "Signal history (last 20)"],
            ["GET", "/api/history/daily", "Daily summaries"],
            ["GET", "/api/history/digests", "Digest history"],
            ["GET", "/api/history/agents/all", "All agents' memory"],
            ["WS", "/ws", "Real-time WebSocket (auto-broadcast)"],
        ],
        col_widths=[18 * mm, 50 * mm, 102 * mm],
    ))

    story.append(Paragraph("9.2 Frontend: War Room Dashboard", s["H2"]))
    story.append(Paragraph(
        "React SPA with matrix-style theme. Features: live price charts (SVG), "
        "agent consensus panel, risk score gauge, signal history table, "
        "history panel (daily/digest/agent tabs with trend charts). "
        "Three selectable themes: Matrix (green), Amber (orange), Cyber (cyan). "
        "WebSocket auto-reconnect with fallback to REST polling.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 10. DEPLOYMENT ──
    story.append(Paragraph("10. Deployment Architecture", s["H1"]))
    story.append(hr())

    story.append(make_table(
        ["Service", "Container", "Port", "Role"],
        [
            ["bot", "oil-bot (Python 3.12-slim)", "8000 (internal)", "Backend: FastAPI + WebSocket + Bot pipeline"],
            ["frontend", "oil-frontend (Node → serve)", "3000 (internal)", "React SPA static server"],
            ["caddy", "caddy:2-alpine", "80, 443 (external)", "Reverse proxy, auto-SSL (Let's Encrypt)"],
        ],
        col_widths=[25 * mm, 50 * mm, 35 * mm, 60 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Routing (Caddyfile)", s["H2"]))
    story.append(make_table(
        ["Path", "Destination"],
        [
            ["/api/*", "bot:8000 (FastAPI backend)"],
            ["/ws", "bot:8000 (WebSocket)"],
            ["/*", "frontend:3000 (React SPA)"],
        ],
        col_widths=[40 * mm, 130 * mm],
    ))

    story.append(Paragraph("Data Persistence", s["H2"]))
    story.append(Paragraph(
        "Bot data (trades, journals, metrics) is stored in a Docker named volume "
        "<b>bot-data:/app/data</b>, ensuring persistence across container restarts. "
        "Caddy SSL certificates are stored in <b>caddy-data</b> volume.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 11. DATA MODELS ──
    story.append(Paragraph("11. Data Models & Schemas", s["H1"]))
    story.append(hr())
    story.append(Paragraph("All models use <b>Pydantic v2</b> with strict validation.", s["Body"]))
    story.append(make_table(
        ["Model", "Purpose", "Key Fields"],
        [
            ["Signal", "Single agent recommendation", "action, confidence, thesis, risk_notes, drivers"],
            ["MarketEvent", "Detected anomaly/news", "event_type, instrument, severity, headline, data"],
            ["CouncilResponse", "Aggregated result", "4x Signal + consensus + strength + confidence"],
            ["OilForecast", "Actionable forecast", "direction, target_price, current_price, timeframe, drivers"],
            ["OilRiskScore", "6-category risk", "geopolitical, supply, demand, financial, seasonal, technical"],
            ["RiskCheck", "Gate decision", "allowed (bool), reason, daily_alerts_count"],
        ],
        col_widths=[30 * mm, 40 * mm, 100 * mm],
    ))
    story.append(PageBreak())

    # ── 12. DEPENDENCIES ──
    story.append(Paragraph("12. External Dependencies", s["H1"]))
    story.append(hr())

    story.append(Paragraph("12.1 Third-Party APIs", s["H2"]))
    story.append(make_table(
        ["Service", "Usage", "Auth", "Cost"],
        [
            ["Anthropic (Claude)", "Risk analysis", "API key", "~$45-75/mo"],
            ["xAI (Grok)", "Sentiment analysis", "API key", "~$30-45/mo"],
            ["Perplexity", "Fact verification", "API key", "~$7-15/mo"],
            ["Google (Gemini)", "Macro + digests", "API key", "~$1-4/mo"],
            ["OpenAI", "Embeddings (RAG)", "API key", "< $1/mo"],
            ["Pinecone", "Vector DB", "API key", "Free tier"],
            ["Yahoo Finance", "Price data", "None (public)", "Free"],
            ["CFTC SODA", "COT positioning", "None (public)", "Free"],
            ["NOAA", "Weather/hurricanes", "None (public)", "Free"],
            ["EIA", "Energy statistics", "API key (free)", "Free"],
            ["Telegram", "Notifications", "Bot token", "Free"],
        ],
        col_widths=[35 * mm, 40 * mm, 35 * mm, 60 * mm],
    ))

    story.append(Paragraph("12.2 Key Python Packages", s["H2"]))
    story.append(make_table(
        ["Package", "Version", "Purpose"],
        [
            ["pydantic", ">= 2.5", "Data validation & schemas"],
            ["anthropic", ">= 0.18", "Claude API client"],
            ["openai", ">= 1.12", "OpenAI + xAI/Perplexity (compatible endpoint)"],
            ["google-genai", ">= 0.3", "Gemini API client"],
            ["yfinance", ">= 0.2.30", "Market data (prices, OVX, DXY)"],
            ["httpx", ">= 0.27", "Async HTTP client"],
            ["fastapi", ">= 0.110", "REST API framework"],
            ["feedparser", ">= 6.0", "RSS news parsing"],
            ["pinecone", ">= 5.0", "Vector database client"],
            ["loguru", ">= 0.7", "Structured logging"],
        ],
        col_widths=[35 * mm, 25 * mm, 110 * mm],
    ))
    story.append(PageBreak())

    # ── 13. SECURITY ──
    story.append(Paragraph("13. Security & Compliance", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Area", "Implementation"],
        [
            ["Secret Management", "All API keys in .env (never committed to git)"],
            ["Input Validation", "Pydantic schemas enforce structure on all external data"],
            ["HTTPS", "Caddy auto-provisions Let's Encrypt certificates"],
            ["Security Headers", "X-Content-Type-Options, X-Frame-Options, Referrer-Policy"],
            ["Non-root Container", "Bot runs as appuser inside Docker"],
            ["Rate Limiting", "Cooldown + daily alert limits prevent spam"],
            ["Audit Trail", "Every decision logged with prompt hash (SHA256)"],
            ["Data Isolation", "Dry-run trades in separate file from production"],
        ],
        col_widths=[35 * mm, 135 * mm],
    ))
    story.append(PageBreak())

    # ── 14. PERFORMANCE ──
    story.append(Paragraph("14. Performance Characteristics", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Operation", "Duration"],
        [
            ["Price fetch (yfinance)", "200-500 ms"],
            ["News poll (10 RSS feeds)", "500-1000 ms"],
            ["Single agent API call", "2-5 seconds"],
            ["4 agents in parallel", "2-5 seconds (concurrent)"],
            ["Aggregation (deterministic)", "< 100 ms"],
            ["Risk check", "< 50 ms"],
            ["Telegram notification", "500-1000 ms"],
            ["Full polling cycle", "~7-10 seconds"],
        ],
        col_widths=[50 * mm, 120 * mm],
    ))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Resource Usage", s["H2"]))
    story.append(make_table(
        ["Component", "Memory", "CPU"],
        [
            ["Bot (Python)", "300-500 MB", "Low (mostly I/O wait)"],
            ["Frontend (React)", "50-100 MB", "Minimal"],
            ["Caddy (proxy)", "20-30 MB", "Minimal"],
            ["Total", "~500-700 MB", "1-2 vCPU sufficient"],
        ],
        col_widths=[40 * mm, 60 * mm, 70 * mm],
    ))
    story.append(PageBreak())

    # ── 15. COSTS ──
    story.append(Paragraph("15. Operational Costs", s["H1"]))
    story.append(hr())
    story.append(Paragraph("Estimated monthly costs (50 polling cycles/day, ~10 events/day):", s["Body"]))
    story.append(make_table(
        ["Category", "Service", "Est. Monthly Cost"],
        [
            ["AI Agents", "Claude + Grok + Perplexity + Gemini", "$80-140"],
            ["Embeddings", "OpenAI text-embedding-3-small", "< $1"],
            ["Vector DB", "Pinecone (free tier)", "$0"],
            ["Market Data", "yfinance + CFTC + NOAA + EIA", "$0"],
            ["Infrastructure", "Hetzner CPX22 (4 vCPU, 8GB RAM)", "~$12"],
            ["Domain + SSL", "Caddy + Let's Encrypt", "$0 (auto)"],
            ["Notifications", "Telegram Bot API", "$0"],
            ["", "", ""],
            ["TOTAL", "", "$92-153/month"],
        ],
        col_widths=[35 * mm, 70 * mm, 65 * mm],
    ))

    story.append(Spacer(1, 10 * mm))
    story.append(hr())
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y')} | "
        "Oil Trading Intelligence Bot v1.0 | "
        "All rights reserved.",
        s["Footer"]
    ))

    # Build PDF
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="Oil Trading Intelligence Bot — Architecture",
        author="Trading Council",
    )
    doc.build(story)
    print(f"PDF generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
