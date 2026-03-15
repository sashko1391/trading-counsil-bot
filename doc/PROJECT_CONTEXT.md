# ABAIC — Oil Trading Intelligence Bot
## Project Context v3.1 (March 10, 2026)

Complete rewrite from crypto → oil trading. Phases 0–6 done (240 tests passing).
Phase 3A architecture upgrade shipped March 10, 2026.

---

## Architecture v3.1

### Stage 1 — Event Detection (3 parallel watchers)

| Watcher | Source | Detects |
|---|---|---|
| **OilPriceWatcher** | yfinance BZ=F + Nasdaq Data Link LGO | price_spike (>1.5%), volume_surge (>2x), spread_change (>5%) |
| **OilNewsScanner** | 10 RSS feeds with credibility weights (0.40–0.95) | news_event, opec_event, geopolitical_alert, tanker_alert, influencer_signal |
| **ScheduledEventsManager** | Internal calendar | scheduled_event (30–60 min pre-alert) |

### Stage 2 — AI Council (4 agents in parallel)

| Agent | Model | Role | Focus |
|---|---|---|---|
| **Grok** | grok-3-latest | Sentiment Hunter | X/Twitter, 17 oil influencers with weights, breaking news |
| **Perplexity** | Perplexity Pro | Fact Verifier | EIA/IEA/OPEC primary sources, data cross-check |
| **Gemini** | gemini-2.5-pro | Macro + Historian | Task A: macro/fundamentals. Task B: historical pattern matching |
| **Claude Sonnet** | claude-sonnet-4-6 | Risk CFO | Crack spreads, contango/backwardation, OPEC compliance, quant |

### Stage 3 — Aggregator v2 (deterministic)

Confidence-weighted voting (not simple majority):
- Score per action = Σ(agent_weight × confidence) for agents choosing that action
- Devil's Advocate: 5th virtual agent at 0.15 weight — always argues AGAINST consensus
- Consensus strength: UNANIMOUS (≥75%) / STRONG (≥55%) / WEAK (≥40%) / CONFLICT
- Invalidation price: MAX for LONG (most conservative), MIN for SHORT
- Dynamic weights: updatable quarterly via per-agent BrierScore tracker

### Stage 4 — Adversarial Reasoning Stage (NEW Phase 3A)

Runs only on STRONG or UNANIMOUS consensus with confidence ≥ 0.65.

```
Step 1: Claude Opus 4.6     → primary thesis (bold position, key arguments)
Step 2: Gemini 2.5 Pro      → steel-man counterargument (BLIND to Opus confidence)
Step 3: Claude Opus 4.6     → reads counter → accepts/rejects each objection → final verdict
```

Anti-sycophancy: Gemini in Step 2 does NOT see Opus's confidence level — prevents anchoring.
Meaningful debate = at least 1 accepted counterargument OR confidence_delta > 0.05.
Cost per run: ~$0.50–1.20. Estimated full pipeline: ~$0.80–1.60.

### Stage 5 — Output (PLANNED)
GPT-5 / GPT-4o → user-friendly summary → PWA push notification

---

## Data Layer

### Price Data

| Instrument | Current Provider | Planned Upgrade |
|---|---|---|
| Brent (BZ=F) | yfinance (free, 15min delay) | OilPriceAPI.com ($30/mo, 5min) → Databento ($1000/mo, real-time) |
| ICE Gasoil (LGO) | Nasdaq Data Link (Quandl) | Databento ICE G futures feed |
| EIA data | EIA API v2 (free) | Keep |

LGO is an ICE Europe futures contract — not covered by generic APIs. Databento is the most viable non-institutional real-time source.

### RSS Feeds (10 sources with weights)

| Source | Weight | Category |
|---|---|---|
| OPEC Press Room | 0.95 | official |
| EIA Today in Energy | 0.85 | official |
| IEA Reports | 0.85 | official |
| Energy Intelligence | 0.80 | pro |
| Argus Media | 0.80 | pro |
| Reuters Commodities | 0.80 | wire |
| S&P Global Platts | 0.75 | pro |
| Rigzone | 0.60 | news |
| OGJ Upstream | 0.60 | trade |
| OilPrice.com | 0.40 | news |

### Scheduled Events Calendar (11 events — expanded Phase 3A)

**Original 6:** EIA Weekly, API Private, Baker Hughes, NFP, OPEC Monthly, IEA Monthly

**New in Phase 3A (+5):**
- Chinese Manufacturing PMI (1st of month, 01:30 UTC) — China = largest importer
- Fujairah Petroleum Storage (weekly Monday, 08:00 UTC) — Middle East gasoil proxy
- EU Gas Storage Report GIE (weekly Thursday, 09:00 UTC) — LGO demand correlation
- Russian Oil Production (monthly ~20th) — sanctions impact visibility
- Indian Oil Import Data PPAC (monthly ~25th) — 3rd largest importer

### Influencer Tracking (17 accounts)

Tier 1 Leading (tweet before price moves): @JavierBlas, @Amena_Bakr, @DavidSheppard_, @AlexLongley1, @summer_said
Tier 2 Data (tanker/flow, leading): @TankerTrackers, @Kpler, @Vortexa
Tier 3 Analysts (lagging/mixed): @EnergyAspects, @AnasAlhajji, @staunovo, @ArjunNMurti, @HFI_Research
Official (high weight, lagging): @OPECnews (0.95), @EIAgov (0.90), @IEA (0.88)

---

## RAG Knowledge Base

**Vector DB:** Pinecone + OpenAI text-embedding-3-small
**Top-K:** 6 chunks per query | **Chunk:** 800 tokens, 160 overlap

**Confidence Decay (Phase 3A):**
- News chunks: score × e^(−0.05 × hours) → half-life ≈ 14h
- Fundamental facts: score × e^(−0.005 × hours) → half-life ≈ 140h

**Knowledge files (4 existing + 6 planned):**
- ✅ oil_fundamentals.md, opec_history.md, seasonal_patterns.md, eia_guide.md
- 📋 geopolitical_risks.md, refining_margins.md, shale_economics.md, china_demand_guide.md, market_microstructure.md, influencer_profiles.md

---

## Data Models (v3.1)

**Core:** Signal, MarketEvent (11 event types), OilRiskScore, OilForecast, CouncilResponse, RiskCheck, TradeJournalEntry

**New in Phase 3A:**
- `HistoricalAnalogue` — event_name, year, similarity_score, price_impact_pct, duration_days, key_difference
- `AdversarialResult` — full 3-step debate transcript, confidence_delta, was_meaningful property
- `DebateStep` — per-step: model, role, accepted/rejected counterarguments, cost_usd
- `ProbabilityDensity` — bull/bear/neutral (sum=1.0 validated)
- `MarketRegime` — trending_up/down/ranging/breakout/crisis
- `AgentPerformanceRecord` — per-agent BrierScore for dynamic weight calibration

**Extended OilForecast fields:** probability_density, regime, model_uncertainty, market_uncertainty, historical_analogues (max 3), narrative_divergence, debate_summary, agent_votes, council_cost_usd

---

## Signal Output Schema (v3.1)

```json
{
  "signal_id": "uuid",
  "instrument": "BZ=F",
  "action": "LONG|SHORT|WAIT",
  "confidence": 0.72,
  "probability_density": {"bull": 0.65, "bear": 0.20, "neutral": 0.15},
  "model_uncertainty": 0.12,
  "market_uncertainty": 0.28,
  "regime": "trending_up",
  "thesis": "...",
  "narrative_divergence": "Opus bullish on supply. Gemini flagged China PMI risk.",
  "invalidation_price": 70.50,
  "invalidation_triggers": ["Price crosses $70.50", "OPEC denial statement"],
  "historical_analogues": [
    {"event_name": "Abqaiq attack 2019", "similarity_score": 0.75, "price_impact_pct": 15.0, "duration_days": 7}
  ],
  "agent_votes": {"grok": "LONG:0.80", "perplexity": "LONG:0.65", "claude": "LONG:0.75", "gemini": "WAIT:0.50"},
  "debate_summary": "Opus → LONG. Gemini countered China PMI. Opus accepted, reduced confidence 0.78 → 0.72.",
  "council_cost_usd": 0.95
}
```

---

## Key Settings (v3.1)

```
WATCH_INSTRUMENTS: ["BZ=F", "LGO"]
DATA_PROVIDER: yfinance (MVP) → oilpriceapi → databento (production)

Models:
  CLAUDE_OPUS_MODEL:    claude-opus-4-6    # adversarial stage only (expensive)
  CLAUDE_SONNET_MODEL:  claude-sonnet-4-6  # council agent
  GEMINI_MODEL:         gemini-2.5-pro     # council + adversarial
  GROK_MODEL:           grok-3-latest
  OPENAI_SUMMARY_MODEL: gpt-4o

Thresholds:
  MIN_CONFIDENCE: 0.60
  COOLDOWN_MINUTES: 10
  MAX_DAILY_ALERTS: 30
  MAX_PIPELINE_RUNS_PER_HOUR: 5
  PRICE_SPIKE_THRESHOLD_PCT: 1.5

Adversarial:
  ADVERSARIAL_ENABLED: true
  ADVERSARIAL_MIN_CONFIDENCE_DELTA: 0.05  # gate for "meaningful" debate

RAG:
  RAG_TOP_K: 6
  RAG_NEWS_DECAY_LAMBDA: 0.05   # half-life ~14h
  RAG_FACT_DECAY_LAMBDA: 0.005  # half-life ~140h
```

---

## What It Is NOT

- Not an automated trading bot (no order execution)
- Not financial advice
- Not real-time HFT (5-min polling, not tick data)
- Not a black box (all final decisions are deterministic aggregator logic, not AI)

---

## Tech Stack

**Backend:** Python 3.12, asyncio, Pydantic v2, FastAPI (planned)
**Data:** yfinance, CCXT (legacy), Pinecone, OpenAI embeddings
**AI:** Anthropic, xAI, Google AI, Perplexity, OpenAI APIs
**Output:** PWA (planned) — Next.js + FastAPI + WebSockets (replaces Telegram)
**Testing:** pytest, 240+ tests

---

## Digest Summarizer (Mar 14, 2026)

**DigestSummarizer** (`src/notifications/digest_summarizer.py`) uses Gemini Flash for cheap, fast summarization of agent theses and risk notes. Instead of hard-truncating thesis at 120 chars and risk_notes at 100 chars, the summarizer compresses full text into concise, complete Ukrainian sentences. Integrated into TelegramNotifier and the main.py pipeline.

## War Room History Tab (Mar 14, 2026)

**HistoryPanel** (`frontend/src/HistoryPanel.jsx`) adds a full history view to the War Room dashboard. WarRoom.jsx now has tab navigation: ДАШБОРД | ІСТОРІЯ.

HistoryPanel contains 3 sub-tabs:
- **Daily summaries** — aggregated daily performance with DailyRow components
- **3h digests** — recent digest records with DigestRow components
- **Per-agent memory** — individual agent signal history with AgentMemoryRow and TrendChart visualization

## New History API Endpoints (Mar 14, 2026)

Added to `src/api/server.py`:
- `GET /api/history/digests` — list of 3h digest records
- `GET /api/history/daily` — daily summary records
- `GET /api/history/agents` — per-agent memory for a specific agent
- `GET /api/history/agents/all` — all agents' memory combined

## Frontend Hooks (Mar 14, 2026)

Added to `frontend/src/useApi.js`:
- `useFetch` — generic data fetching hook with loading/error state
- `useHistoryData` — specialized hook for history tab data (digests, daily, agents)
