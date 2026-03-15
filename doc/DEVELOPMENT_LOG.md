# ABAIC — Development Log

---

## Mar 10, 2026 — Phases 0–6: Full Oil Bot Implementation

### Phase 0: Foundation
- Rewrote config/settings.py: removed Binance, added XAI/Perplexity/Pinecone/EIA keys, WATCH_INSTRUMENTS=["BZ=F","LGO"]
- Extended schemas.py: OilRiskScore (6 categories + composite), OilForecast, 9 oil event types
- Updated .env.example
- 27 new tests

### Phase 1: Oil Price Watcher
- Created base_watcher.py (ABC), DataProviderProtocol, YFinanceProvider
- OilPriceWatcher: rolling window, 3 detectors (price_spike, volume_surge, spread_change)
- Adapter pattern for swapping data providers
- 13 tests

### Phase 2: Oil Prompts + Agent Rewiring
- Complete rewrite of config/prompts.py for oil (4 specialized prompts)
- Fixed all 4 agents: correct API keys, models, temperature=0.2, instrument field
- All prompts require JSON structured output, separate Brent/Gasoil analysis
- 46 tests

### Phase 3: Oil News Scanner
- OilNewsScanner: RSS feeds, keyword relevance scoring, dedup, cooldown
- EIAClient: wraps EIA API v2 (inventories, production, utilization)
- ScheduledEventsManager: 6 recurring events with timezone handling
- 48 tests

### Phase 4: Pipeline Integration
- Rewrote src/main.py: async orchestrator, 3 event sources, rich context building
- Updated telegram_notifier.py: oil alert format with emoji
- Updated aggregator.py: pair → instrument
- E2E integration tests, ~30 tests

### Phase 5: RAG Knowledge Base
- OilRAGEngine: Pinecone REST API + OpenAI embeddings, chunk splitting
- OilKnowledgeLoader: bulk ingest from data/knowledge/*.md, dedup tracking
- 4 knowledge files: fundamentals, opec_history, seasonal_patterns, eia_guide
- 14 tests

### Phase 6: Production Hardening
- Rewrote RiskGovernor: OilRiskScore calculation, daily limits, cooldown, composite ceiling
- ForecastTracker: hit rate, Brier score, weekly reports, JSON persistence
- ~30 tests

**Subtotal: 240 tests, all passing**

---

## Mar 10, 2026 — Architecture Research Sessions (3A Pre-work)

### AI Consultation — Data API Decision
Sent questionnaire to 3 AI models. Synthesised into ABAIC_AI_Consultation_Synthesis.docx.

**Data API decision (hybrid):**
- Brent (BZ=F): OilPriceAPI.com (~$30/mo, 5-min updates) — MVP
- Gasoil (LGO): Nasdaq Data Link (Quandl) — only reliable LGO source at MVP stage
- EIA API: free, keep for inventory/production data
- Phase 2 upgrade: Databento (~$1,000/mo) — covers ICE Brent + ICE G futures natively

**RSS feeds decided:** 10 feeds with credibility weights (OPEC=0.95, EIA=0.85, Argus=0.80, Reuters=0.80, OilPrice.com=0.40)

**Scheduled events expanded:** +5 new events (Chinese PMI, Fujairah Storage, EU GIE, Russian Production, Indian Imports)

**Influencer list finalised:** 17 accounts with tier classification (leading/lagging/mixed) and per-account weights

**Gemini role upgraded:** Few-Shot Chain-of-Thought historical pattern matching added as Task B alongside macro analysis (Task A)

**Aggregator v2 design:** Replace simple majority vote with confidence-weighted aggregation. Add Devil's Advocate (5th virtual agent at weight=0.15). CONFLICT threshold: top two scores within 10% of each other.

**Adversarial Reasoning Stage design:**
- Claude Opus 4.6 → primary thesis
- Gemini 2.5 Pro → steel-man counterargument (BLIND to Opus confidence — anti-anchoring)
- Claude Opus 4.6 → reads counter, accepts/rejects each objection, final verdict
- confidence_delta field tracks how much debate shifted the position
- Only runs on STRONG/UNANIMOUS consensus ≥ 0.65 confidence
- Cost: ~$0.50–1.20 per adversarial run

**Output channel:** PWA web app (Next.js 15 + FastAPI + WebSockets) replaces Telegram

**Signal schema v3.1:** Added probability_density, model_uncertainty, market_uncertainty, regime, narrative_divergence, historical_analogues, agent_votes, debate_summary, council_cost_usd

**RAG confidence decay formula:** relevance_score = base × e^(−λ×hours)
- News chunks: λ=0.05 (half-life ~14h)
- Fundamental facts: λ=0.005 (half-life ~140h)

**Dynamic agent weights:** BrierScore tracker → weights updated quarterly per-agent

---

## Mar 10, 2026 — Phase 3A: Core Architecture Upgrade

### Deliverable: abaic_phase3a.zip

**Files created/updated:**

#### src/models/schemas.py → v3.1
New classes:
- `HistoricalAnalogue` — structured historical episode record (event, year, similarity_score, price_impact_pct, duration_days, resolution, key_difference)
- `DebateStep` — single step in adversarial debate (model, role, accepted/rejected counterarguments, tokens_used, cost_usd)
- `AdversarialResult` — full 3-step debate transcript with `was_meaningful` property (True if accepted_counterarguments > 0 OR |confidence_delta| > 0.05)
- `ProbabilityDensity` — bull/bear/neutral distribution with model_validator enforcing sum=1.0
- `MarketRegime` — Literal type: trending_up/trending_down/ranging/breakout/crisis
- `AgentPerformanceRecord` — per-prediction record for BrierScore calculation and quarterly weight recalibration
Extended existing:
- `MarketEvent` — added source_weight, rag_context_ids, new event types: influencer_signal, tanker_alert
- `OilForecast` — added probability_density, regime, model_uncertainty, market_uncertainty, historical_analogues (max 3), narrative_divergence, debate_summary, agent_votes, council_cost_usd, invalidation_triggers
- `CouncilResponse` — added devil_advocate (Optional[Signal]), adversarial_result (Optional[AdversarialResult]), total_cost_usd

#### src/config/settings.py → v3.1
- New API key fields: OILPRICEAPI_KEY, DATABENTO_API_KEY, NASDAQ_DATA_LINK_KEY
- New model fields: CLAUDE_OPUS_MODEL, CLAUDE_SONNET_MODEL, GEMINI_ADVERSARIAL_MODEL, OPENAI_SUMMARY_MODEL
- ADVERSARIAL_ENABLED flag + ADVERSARIAL_MIN_CONFIDENCE_DELTA
- RAG_NEWS_DECAY_LAMBDA=0.05, RAG_FACT_DECAY_LAMBDA=0.005
- MAX_PIPELINE_RUNS_PER_HOUR=5 (cost control)
- RSS_FEEDS: 10 feeds as dict with url/weight/category
- OIL_INFLUENCERS: 17 accounts with weight/type/signals/org
- SCHEDULED_EVENTS: expanded to 11 events (+5 new)
- OIL_KEYWORDS_HIGH/MED/LOW lists for news scoring

#### src/config/prompts.py → v3.1
- GEMINI_SYSTEM_PROMPT: added Task A (macro) + Task B (historical pattern matching with structured JSON output including historical_analogues field)
- DEVIL_ADVOCATE_PROMPT: new — 5th virtual agent that argues against consensus
- ADVERSARIAL_PRIMARY_PROMPT: Opus Step 1
- ADVERSARIAL_COUNTER_PROMPT: Gemini Step 2 (explicitly blind to Opus confidence)
- ADVERSARIAL_VERDICT_PROMPT: Opus Step 3 (accept/reject each objection by ID)

#### src/council/adversarial_stage.py → NEW
- `AdversarialStage` class with `should_run()` gate and `run()` method
- `_call_opus()`: Anthropic API, temperature=0.3, cost tracking (Opus 4.6: $15/M in, $75/M out)
- `_call_gemini()`: Google GenAI API, temperature=0.4
- `_parse()`: JSON extraction with markdown fence stripping
- `_summarize_council()`: builds text context from CouncilResponse for prompt injection
- `MockAdversarialStage`: drop-in mock for testing (deterministic, no API calls)

#### src/council/aggregator.py → v2
- Confidence-weighted voting replaces simple majority
- `_vote()`: scores per action = Σ(weight × confidence), DEVIL_WEIGHT=0.15 for devil's advocate
- `_confidence()`: weighted avg of agreeing agents minus disagreement penalty (×0.30) minus devil penalty (×0.20)
- `_risks()`: collects [DEVIL] tagged risk alongside agent risks
- `update_weights()`: accepts new weights dict, validates sum=1.0, logs change
- CONFLICT: triggers when top two scores within 10% of each other

#### tests/test_phase3a.py → NEW (38 tests in 4 blocks)
- Block A: Schema tests (HistoricalAnalogue, ProbabilityDensity, DebateStep, AdversarialResult, OilForecast v3.1, AgentPerformanceRecord)
- Block B: Aggregator v2 tests (voting, confidence, devil advocate, position sizing, invalidation, weights)
- Block C: MockAdversarialStage tests (run, was_meaningful, should_run gates)
- Block D: Settings v3.1 tests (new keys, RSS, influencers, events, decay lambdas)

**Validation results (no pydantic in sandbox):**
- Settings: RSS=10, influencers=17, events=11, decay lambdas OK ✅
- Prompts: Gemini Task A+B, adversarial 3 prompts, devil's advocate ✅
- Aggregator logic: UNANIMOUS, devil's advocate penalty, STRONG 3v1, invalidation MAX/MIN ✅
- All 8 pure-Python aggregator tests passed ✅
- Full 38-test pytest suite requires pydantic — run locally with `pytest tests/test_phase3a.py -v`

**Total new tests: 38 | Cumulative: 278**

---

## Pending — Phase 3B (Next Session)

- [ ] OilNewsScanner: update RSS_FEEDS from settings (no hardcoding), credibility weight scoring
- [ ] OilNewsScanner: add influencer_signal and tanker_alert event types
- [ ] RAG Engine: implement confidence decay (e^(−λt)) in retrieval scoring
- [ ] RAG Engine: add 6 new knowledge files (geopolitical_risks, refining_margins, shale_economics, china_demand_guide, market_microstructure, influencer_profiles)
- [ ] Data providers: OilPriceAPIProvider class (adapter pattern, drops in as yfinance replacement)
- [ ] ScheduledEventsManager: add 5 new events from settings (Chinese PMI, Fujairah, EU GIE, Russian, Indian)

## Pending — Phase 3C (FastAPI Backend)

- [ ] FastAPI app with WebSocket support
- [ ] /api/signals endpoint (latest N forecasts)
- [ ] /api/pipeline/run endpoint (manual trigger)
- [ ] /ws/signals WebSocket for live push
- [ ] CORS config for Next.js frontend

## Pending — Phase 3D (PWA Frontend)

- [ ] Next.js 15 app (App Router)
- [ ] TradingView Lightweight Charts — Brent + Gasoil price
- [ ] Signal card component: headline, action badge, confidence bar, agent votes grid
- [ ] Debate timeline: 3-step adversarial transcript viewer
- [ ] PWA manifest + service worker + Web Push API
- [ ] Mobile: headline + confidence bar + action icon only
- [ ] Desktop: full charts + agent votes + historical analogues

## Pending — Cross-cutting

- [ ] Devil's Advocate integration in main.py pipeline (generate after council, pass to aggregator)
- [ ] BrierScore → dynamic weight recalibration (quarterly cron)
- [ ] CRISIS MODE: if >5% price move in 15min with no scheduled event → escalate all agents, disable cooldowns
- [ ] Per-agent cost tracker → daily cost dashboard
- [ ] Disclaimer on every signal: "AI-generated intelligence, not financial advice"

---

## Mar 14, 2026 — War Room History Tab + Digest Summarizer

### History Tab in War Room
- Integrated HistoryPanel into WarRoom.jsx with ДАШБОРД/ІСТОРІЯ tab switching
- HistoryPanel shows 3 sub-tabs: daily summaries, 3h digests, and per-agent memory with trend chart

### Digest Summarizer
- Created DigestSummarizer (src/notifications/digest_summarizer.py) using Gemini Flash to compress agent theses/risks into concise, complete Ukrainian sentences instead of hard-truncating at 120/100 chars
- Integrated into TelegramNotifier and main.py pipeline

### Removed Hard Truncation
- Thesis [:120] and risk_notes [:100] truncation removed from telegram_notifier.py and main.py _save_digest_record
- Now collects full text and passes to summarizer

### New API Endpoints
- Added 4 history endpoints to server.py:
  - /api/history/digests
  - /api/history/daily
  - /api/history/agents
  - /api/history/agents/all

### Frontend Hooks
- Added useFetch and useHistoryData hooks to useApi.js
