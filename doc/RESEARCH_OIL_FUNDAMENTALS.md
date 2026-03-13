# Oil Market Fundamentals — ABAIC Research
**Date:** March 10, 2026
**Sources:** GPT-4o, Gemini-2.5-Flash, Grok-3-mini (parallel query)
**Purpose:** Foundation knowledge for Oil Trading Intelligence Bot

---

## TOPIC 1: Oil Price Formation Factors

### TOP 10 Factors Moving Brent Crude (Consolidated Ranking)

All 3 models agree on the top factors. Consolidated by consensus:

| # | Factor | Impact | Typical Move | Consensus |
|---|--------|--------|-------------|-----------|
| 1 | **OPEC+ Production Decisions** | Very High | 5–15% | 3/3 top-3 |
| 2 | **Geopolitical Conflicts** (wars, sanctions, Hormuz) | Very High | 5–20% | 3/3 top-4 |
| 3 | **Global Economic Conditions** (recession/growth) | High | 5–10% | 3/3 top-4 |
| 4 | **China Demand** (largest importer) | High | 5–10% | 3/3 |
| 5 | **US Shale Production** (swing producer) | High | 3–8% | 3/3 |
| 6 | **SPR Releases** (Strategic Petroleum Reserve) | Medium-High | 2–7% | 3/3 |
| 7 | **USD Strength** (inverse correlation) | Medium | 2–6% | 3/3 |
| 8 | **Inventory Levels** (EIA/API weekly data) | Medium | 2–5% | 2/3 (Grok, Gemini) |
| 9 | **Weather Events** (hurricanes, cold snaps) | Medium | 2–5% | 3/3 |
| 10 | **Regulatory/Environmental** (carbon taxes, IMO) | Low-Medium | 1–3% | 3/3 |

### Brent ↔ Gasoil London Correlation

- **Correlation coefficient:** 0.85–0.95 (all models agree: very high)
- **Gasoil typically lags Brent by 1–3 days** (refining processing time)
- **Crack spread** (Gasoil - Brent) = refining margin:
  - Normal range: $10–20/bbl (Grok), $15–40/bbl (Gemini)
  - Extreme: >$100/bbl during 2022 European diesel shortage (Gemini)
- **Gasoil can LEAD Brent** when distillate-specific shocks occur (cold snap, refinery outage)

### Factors SPECIFIC to Gasoil (vs Brent)

| Factor | Impact on Gasoil | Not Brent? |
|--------|-----------------|------------|
| Refinery outages/maintenance | Direct — reduces Gasoil supply | Indirect |
| Winter heating demand (EU) | Major seasonal driver | Minor |
| Diesel/trucking/shipping demand | Primary end-use | Not applicable |
| IMO 2020 marine fuel regs | Structural demand uplift | Indirect |
| EU distillate inventories (Euroilstock) | Gasoil-specific metric | Different |
| Jet fuel demand (seasonal travel) | Component of Gasoil | Not directly |
| Agricultural diesel (planting/harvest) | Seasonal demand | Not applicable |

### Seasonal Patterns

| Quarter | Brent | Gasoil |
|---------|-------|--------|
| **Q1 (Jan-Mar)** | Supported by winter refinery runs | **PEAK** — heating demand |
| **Q2 (Apr-Jun)** | Dip — refinery maintenance | Drops — heating ends, agricultural diesel |
| **Q3 (Jul-Sep)** | **PEAK** — summer driving season | Steady — industrial + jet fuel |
| **Q4 (Oct-Dec)** | Moderate — pre-winter buildup | **Rises** — winter heating starts |

**Key insight (Grok):** Brent historically rises ~7% average in July (US driving season, EIA 2010-2022 data).

---

## TOPIC 2: News Sources & Data Providers

### Scheduled Events Calendar (CRITICAL for bot)

| Event | Day | Time (ET) | Impact | Source |
|-------|-----|-----------|--------|--------|
| **API Weekly Inventory** | Tuesday | 4:30 PM | Pre-EIA signal, 2-3% moves | api.org |
| **EIA Weekly Petroleum Status** | Wednesday | 10:30 AM | **Major mover**, 2-5% | eia.gov |
| **Baker Hughes Rig Count** | Friday | 1:00 PM | US drilling activity proxy | bakerhughes.com |
| **OPEC+ Meetings** | Varies (Jun/Dec + extraordinary) | 9:00 AM CET | 5-15% moves | opec.org |
| **IEA Monthly Oil Market Report** | Mid-month (~12-15th) | Varies | Global supply/demand forecast | iea.org |
| **OPEC MOMR** | Mid-month (~10-13th) | Varies | OPEC's own forecast | opec.org |
| **US Fed Rate Decision** | 8x/year | 2:00 PM ET | USD impact → oil inverse | fed.gov |
| **US Non-Farm Payrolls** | 1st Friday/month | 8:30 AM ET | Economic health signal | bls.gov |
| **China Manufacturing PMI** | End of month | Varies | Demand signal | stats.gov.cn |

### Real-Time News Sources

**Paid (professional-grade):**
- **Reuters Eikon / Refinitiv** — industry standard, robust API
- **Bloomberg Terminal** — unparalleled depth, $20k+/year
- **S&P Global Platts** — commodity-specific, crack spread assessments
- **Argus Media** — strong on regional/product pricing
- **Dow Jones Newswires** — real-time financial + energy

**Free/Freemium:**
- **Reuters.com / Bloomberg.com** — key headlines break free
- **OilPrice.com** — aggregated news + analysis
- **EIA.gov** — official US energy data, free API
- **Financial Times / WSJ** — in-depth analysis (paywalled)

### Price Data APIs

| Provider | Brent | Gasoil | Latency | Cost |
|----------|-------|--------|---------|------|
| **ICE Data Services** | ✅ | ✅ | Real-time (1s) | $1000+/mo |
| **Refinitiv/Bloomberg** | ✅ | ✅ | Real-time | $10-20k/yr |
| **Interactive Brokers API** | ✅ | ✅ | Real-time | Account required |
| **yfinance** | ✅ BZ=F | ⚠️ LGO=F (unreliable) | 15-20min delay | Free |
| **EIA API** | ✅ (weekly) | ❌ | 1-2 day delay | Free |
| **Nasdaq Data Link (Quandl)** | ✅ | ✅ | End-of-day | Freemium |
| **Alpha Vantage** | ✅ | ⚠️ varies | Delayed | Freemium |

**Key problem confirmed by all 3 models:** Gasoil London (LGO) is hard to get free/cheap. yfinance `LGO=F` is unreliable.

### X/Twitter Accounts to Monitor

**Official:**
- @OPECSecretariat, @IEA, @EIAgov, @BakerHughesCo

**Journalists (market-moving):**
- **@JavierBlas** — Bloomberg energy columnist (all 3 models mention him)
- **@Amena_Bakr** — Chief OPEC correspondent, Energy Intelligence
- **@Rania_El_Gamal** — Reuters ME energy correspondent

**Analysts:**
- @OilShepard (David Sheppard, FT)
- @DanYergin (S&P Global vice chair)

---

## TOPIC 3: News Classification & Impact Taxonomy

### News Categories with Impact Profiles

| Category | Direction | Magnitude | Time Horizon | Example |
|----------|-----------|-----------|-------------|---------|
| **Geopolitical** (wars, sanctions, Hormuz) | BULLISH (supply risk) | 5–20% | Minutes → months | Russia-Ukraine 2022: +22% in 1 week |
| **Supply — OPEC+** (cuts/increases) | BULL/BEAR | 5–15% | Hours → weeks | Oct 2022 OPEC cut: +6.6% in 3 days |
| **Supply — Inventory** (EIA/API draws/builds) | BULL (draw) / BEAR (build) | 1–5% | Minutes → hours | Jul 2023 EIA -7.9M bbl draw: +1.5% in 1hr |
| **Supply — Disruption** (outages, hurricanes) | BULLISH | 2–10% | Days → weeks | Saudi Aramco attack Sep 2019: +14.6% gap |
| **Demand — Macro** (GDP, PMI, recession) | BULL/BEAR | 3–10% | Days → months | COVID Mar 2020: -60% over weeks |
| **Demand — China** (lockdowns, recovery) | BULL/BEAR | 5–10% | Weeks → months | China reopening Q1 2023: +7% |
| **Financial** (USD, rates, speculation) | Inverse to USD | 1–5% | Hours → days | Fed hikes 2022: USD up → Brent -4% |
| **Weather** (hurricanes, cold snaps) | BULLISH | 2–7% | Days → weeks | Hurricane Ida Aug 2021: +5% |
| **Regulatory** (carbon tax, emissions) | Usually BEARISH | 1–3% | Weeks → months | EU carbon tax 2023: -3% |

### Historical Examples (Consensus Across Models)

| # | Event | Date | Impact | Timeframe |
|---|-------|------|--------|-----------|
| 1 | **Russia invades Ukraine** | Feb 24, 2022 | Brent +22% ($97→$118) | 1 week |
| 2 | **Saudi Aramco drone attack** | Sep 14, 2019 | Brent +14.6% gap open | 1 day (then partial reversal) |
| 3 | **OPEC+ cuts 2M bpd** | Oct 5, 2022 | Brent +6.6% | 3 days |
| 4 | **COVID demand collapse** | Mar-Apr 2020 | Brent -60% ($50→$20) | 6 weeks |
| 5 | **Hurricane Katrina** | Aug 2005 | Brent +10% | 3 days |

### Signal vs Noise — Filtering Criteria for Bot

**Signal (actionable):**
- Source: verified (EIA, OPEC, Reuters, Bloomberg)
- Impacts core supply/demand directly
- Historical precedent of >2% price move
- Consensus across multiple sources
- Clear time horizon (not speculative)

**Noise (ignore):**
- Unverified social media rumors
- Low engagement (<1000 retweets unless from key accounts)
- Speculative commentary without data
- "Oil will go to $200" type predictions
- News older than 2 hours without market reaction

### What Makes News "Actionable" for Our Bot

1. **High probability of >2% price impact** (based on category + magnitude table above)
2. **Verifiable source** (official agency, top-tier journalist)
3. **Short time horizon** (hours to days, not months)
4. **Historical pattern match** (similar events moved prices predictably before)
5. **Corroborated by data** (e.g., OPEC announcement + actual inventory change)

---

## Key Takeaways for Bot Architecture

### What the bot MUST monitor:
1. **EIA Wednesday 10:30 AM ET** — biggest weekly mover
2. **OPEC+ meetings & statements** — biggest structural mover
3. **Geopolitical news from Middle East/Russia** — biggest shock mover
4. **China economic data (PMI, imports)** — biggest demand signal
5. **USD/DXY movements** — constant inverse pressure
6. **European weather forecasts** — Gasoil-specific driver

### Data source strategy:
- **Price data:** yfinance (Brent BZ=F) for MVP, upgrade to IBKR/ICE for production
- **Gasoil problem:** Need paid source (ICE Data, IBKR, or Commodities-API)
- **News:** Start with free RSS (Reuters, EIA, OPEC) + X/Twitter monitoring via Grok
- **Scheduled events:** Hardcode calendar, trigger pre/post analysis

### Agent prompt adaptation:
- Replace crypto terminology with oil-specific context
- Train agents on oil taxonomy (above)
- Grok → monitor oil journalists on X (not crypto influencers)
- Claude CFO → oil-specific risk factors (contango, crack spreads, OPEC compliance)

---

*Generated by ABAIC multi-LLM research council*
*Raw responses saved in: doc/abaic_oil_research.json*
