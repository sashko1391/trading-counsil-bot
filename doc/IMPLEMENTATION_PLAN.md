# Oil Trading Bot — Implementation Plan

## Context

Трансформація crypto trading council bot → oil trading intelligence bot.
Поточний код побудований для крипто (CCXT/Binance), але архітектура модульна — більшість компонентів generic.

**Ціль:** News → trends → oil price forecast → Telegram alert
**Інструменти:** Brent Crude (BZ=F) + Gasoil London (LGO)

---

## Що НЕ змінюється (generic):
- `src/models/schemas.py` — Pydantic моделі (розширюємо, не ламаємо)
- `src/council/aggregator.py` — voting logic
- `src/council/base_agent.py` — ABC
- `src/journal/trade_journal.py` — JSON journal
- `src/watchers/market_watcher.py` — зберігаємо як deprecated

---

## Phase 0: Foundation (Settings + Schemas)

**Ціль:** Оновити конфіги та моделі даних — фундамент для всіх наступних фаз.

**Modify:**
| File | Що робимо |
|------|-----------|
| `config/settings.py` | Прибрати Binance keys. Додати XAI_API_KEY, PERPLEXITY_API_KEY, PINECONE_API_KEY, EIA_API_KEY. Змінити WATCH_PAIRS на ["BZ=F", "LGO"]. Додати DATA_PROVIDER="yfinance" |
| `src/models/schemas.py` | Розширити MarketEvent.event_type (news_event, eia_report, opec_event, geopolitical_alert, spread_change). Додати OilRiskScore (6 categories) + OilForecast моделі |
| `.env.example` | Оновити під oil keys |

**Create:**
| File | Що робимо |
|------|-----------|
| `tests/test_oil_schemas.py` | Тести для OilRiskScore, OilForecast |

**Verify:** `pytest tests/test_oil_schemas.py -v` + Settings loads without Binance

---

## Phase 1: Oil Price Watcher (MVP Data Layer)

**Ціль:** Заміна crypto MarketWatcher → OilPriceWatcher з adapter pattern.

**Dep:** Phase 0

**Create:**
| File | Що робимо |
|------|-----------|
| `src/watchers/base_watcher.py` | ABC: poll_once(), get_latest_snapshot(), get_history() |
| `src/watchers/data_providers/__init__.py` | DataProviderProtocol |
| `src/watchers/data_providers/yfinance_provider.py` | YFinanceProvider: fetch Brent (BZ=F) + Gasoil (Quandl ICE/L1) |
| `src/watchers/oil_price_watcher.py` | OilPriceWatcher: rolling window, detect price_spike, volume_surge, spread_change (Brent-Gasoil). Без funding_extreme |
| `tests/test_oil_price_watcher.py` | Mock yfinance, test all detectors |

**Verify:** `pytest tests/test_oil_price_watcher.py -v`

**New deps:** `yfinance>=0.2.30`, `nasdaqdatalink>=1.0.0`

---

## Phase 2: Oil Prompts + Agent Rewiring

**Ціль:** Переписати всі 4 промпти під нафту. Виправити API keys агентів.

**Dep:** Phase 0

**Modify:**
| File | Що робимо |
|------|-----------|
| `config/prompts.py` | **ПОВНИЙ ПЕРЕПИС.** Grok→oil journalists on X. Perplexity→EIA/IEA/OPEC verification. Gemini→macro+seasonal+inventory. Claude CFO→contango, crack spreads, OPEC compliance |
| `src/council/grok_agent.py` | API key → XAI_API_KEY, model → grok-3, temperature=0.2 |
| `src/council/claude_agent.py` | temperature=0.2 |
| `src/council/gemini_agent.py` | model update, temperature=0.2 |
| `src/council/perplexity_agent.py` | model update, temperature=0.2 |

**Create:**
| File | Що робимо |
|------|-----------|
| `tests/test_oil_prompts.py` | Verify prompts contain oil keywords, JSON output format |

**Key prompt design:**
- Brent і Gasoil аналізувати ОКРЕМО
- JSON structured output (Signal schema)
- Chain-of-thought: facts → impact → price estimate
- Negative constraints: "Do not speculate"

**Verify:** `pytest tests/test_oil_prompts.py -v` + `python -m main --dry-run --once`

---

## Phase 3: Oil News Scanner

**Ціль:** RSS/API моніторинг нафтових новин + scheduled events calendar.

**Dep:** Phase 0

**Create:**
| File | Що робимо |
|------|-----------|
| `src/watchers/oil_news_scanner.py` | OilNewsScanner: RSS feeds (OPEC, OilPrice.com, Reuters). Keyword relevance scoring. Deduplication. Cooldown per source |
| `src/watchers/eia_client.py` | EIAClient: wraps EIA API v2. Crude inventories, production, refinery utilization |
| `src/watchers/scheduled_events.py` | ScheduledEventsManager: EIA Wed 10:30 ET, API Tue 16:30, Baker Hughes Fri 13:00, OPEC meetings. Pre/post event triggers |
| `tests/test_oil_news_scanner.py` | Mock RSS, test relevance scoring, dedup |
| `tests/test_eia_client.py` | Mock EIA API |
| `tests/test_scheduled_events.py` | Test event timing (freezegun) |

**New deps:** `feedparser>=6.0.0`, `freezegun>=1.2.0`

**Verify:** `pytest tests/test_oil_news_scanner.py tests/test_eia_client.py tests/test_scheduled_events.py -v`

---

## Phase 4: Pipeline Integration + Telegram

**Ціль:** З'єднати все разом. Оновити Telegram формат.

**Dep:** Phases 1, 2, 3

**Modify:**
| File | Що робимо |
|------|-----------|
| `src/main.py` | TradingCouncil приймає 3 sources: OilPriceWatcher + OilNewsScanner + ScheduledEventsManager. Context enrichment перед агентами (price + news + EIA + event proximity) |
| `src/notifications/telegram_notifier.py` | Oil alert format: Direction + Confidence + Target + Drivers + Risks + Council consensus + Disclaimer |
| `tests/test_full_pipeline.py` | Оновити fixtures під oil events |

**Create:**
| File | Що робимо |
|------|-----------|
| `tests/test_oil_integration.py` | E2E: all 3 sources → agents → aggregator → telegram |

**Telegram format:**
```
🛢️ OIL ALERT — Brent Crude
📈 Direction: BULLISH
💪 Confidence: 75%
⏰ Timeframe: 48h
🎯 Target: $82.50 (+2.3%)
📊 Drivers: EIA draw -7.2M, OPEC compliance 98%
⚠️ Risks: USD rally, China PMI miss
🤖 Council: 3/4 Bullish (Strong)
📝 NOT financial advice.
```

**Verify:** `pytest tests/ -v` (all tests) + `python -m main --dry-run --once`

---

## Phase 5: RAG Knowledge Base

**Ціль:** Pinecone vector DB з нафтовими знаннями для контексту агентів.

**Dep:** Phase 4

**Create:**
| File | Що робимо |
|------|-----------|
| `src/knowledge/__init__.py` | Package init |
| `src/knowledge/rag_engine.py` | OilRAGEngine: Pinecone + OpenAI embeddings. query() + ingest() |
| `src/knowledge/oil_knowledge_loader.py` | Load knowledge from data/knowledge/*.md |
| `data/knowledge/fundamentals.md` | Contango, backwardation, crack spreads |
| `data/knowledge/opec_history.md` | OPEC decisions → market reactions |
| `data/knowledge/seasonal_patterns.md` | Q1-Q4 Brent + Gasoil patterns |
| `data/knowledge/eia_guide.md` | How to interpret EIA reports |
| `tests/test_rag_engine.py` | Mock Pinecone |

**New deps:** `pinecone-client>=3.0.0`

---

## Phase 6: Production Hardening

**Dep:** Phase 5

**Create:**
| File | Що робимо |
|------|-----------|
| `src/watchers/data_providers/ibkr_provider.py` | IBKRProvider: real-time Brent + Gasoil від ICE |
| `src/metrics/__init__.py` | Package init |
| `src/metrics/forecast_tracker.py` | Hit rate, Brier score, Sharpe ratio. Weekly Telegram summary |

**Modify:**
| File | Що робимо |
|------|-----------|
| `src/risk/risk_governor.py` | OilRiskScore calculation. Contango factor. OPEC meeting proximity |
| `requirements.txt` | ib_insync |

---

## Dependency Graph

```
Phase 0 (Foundation)
  ├──→ Phase 1 (Price Watcher)  ──┐
  ├──→ Phase 2 (Prompts)  ────────┼──→ Phase 4 (Integration) ──→ Phase 5 (RAG) ──→ Phase 6 (Production)
  └──→ Phase 3 (News Scanner) ────┘
```

**Phases 1, 2, 3 — паралельні** після Phase 0.

---

## Summary

| Phase | Files modify | Files create | Tests | Complexity |
|-------|-------------|-------------|-------|------------|
| 0 | 3 | 1 | 1 | Low |
| 1 | 0 | 5 | 1 | Medium |
| 2 | 5 | 1 | 1 | Medium |
| 3 | 0 | 3 | 3 | Medium-High |
| 4 | 3 | 1 | 2 | Medium |
| 5 | 0 | 7 | 1 | High |
| 6 | 2 | 3 | 0 | High |
| **Total** | **13** | **21** | **9** | — |

**MVP (Phases 0-4):** Працюючий oil bot з price watcher + news scanner + scheduled events + 4 AI agents + Telegram alerts. Можна запустити `--dry-run` і побачити oil forecasts.
