# Oil Market Microstructure

---

## ICE Brent Futures

ICE Brent (ticker: BZ on CME, B on ICE) is the global benchmark for ~80% of internationally traded crude.

Key contract specs:
- Exchange: ICE Futures Europe (London)
- Contract size: 1,000 barrels
- Currency: USD/barrel
- Settlement: Cash-settled against ICE Brent Index
- Trading hours: 01:00-23:00 London time (nearly 24h)
- Tick size: $0.01/bbl ($10 per tick per contract)

Monthly contracts available for 96 consecutive months. Front month has highest liquidity.

---

## Contract Expiry and Roll

- Brent front-month expires on the last business day of the second month preceding delivery
- Example: April contract expires end of February
- **Roll period:** Most position rolling occurs 5-10 days before expiry
- Roll yield: positive in backwardation (roll down = profit), negative in contango (roll up = cost)
- ETFs and passive funds must roll — creates predictable flow patterns

---

## ICE Gasoil (LGO)

ICE Gasoil is the European benchmark for middle distillates (diesel, heating oil, jet fuel).

- Contract size: 100 metric tonnes
- Currency: USD/tonne
- Settlement: Physical delivery at ARA (Amsterdam-Rotterdam-Antwerp)
- Less liquid than Brent — wider bid/ask spreads
- Key spread: Gasoil crack = LGO - Brent (converted to same units)

---

## Contango vs Backwardation

**Contango:** Forward > Spot. Signals oversupply or low near-term demand.
- Incentivizes storage (buy spot, sell forward, pocket the difference minus storage costs)
- Typical in oversupplied markets
- Negative roll yield for long positions

**Backwardation:** Spot > Forward. Signals tight supply or strong near-term demand.
- Penalizes storage (spot premium erodes)
- Typical in supply-constrained markets
- Positive roll yield for long positions

**Time spreads** (e.g., M1-M2, M1-M6) quantify the curve shape. Widening backwardation = tightening market.

---

## Open Interest Interpretation

- **Rising OI + rising prices:** New longs entering = bullish continuation
- **Rising OI + falling prices:** New shorts entering = bearish continuation
- **Falling OI + rising prices:** Short covering = potentially weak rally
- **Falling OI + falling prices:** Long liquidation = potentially weak decline

CFTC Commitments of Traders (CoT) report (Friday, 3 days delayed):
- Managed Money net long/short position is the key metric
- Extreme net long → crowded trade, vulnerable to squeeze
- Extreme net short → potential short-covering rally

---

## WTI-Brent Spread

Historically Brent traded at a premium to WTI:
- Normal: Brent $2-5 premium
- Wide: Brent $5-10+ premium (2011-2015, US export ban era)
- Narrow/inverted: signals strong US domestic demand or weak international demand

The spread reflects:
- US crude export capacity and logistics
- Atlantic Basin supply-demand balance
- Quality differential (Brent is lighter/sweeter)

---

## Key Liquidity Windows

- **London open (08:00 GMT):** European physical traders, benchmark setting
- **US open (14:00 GMT):** Highest volume period, US data releases
- **NYMEX close (19:30 GMT):** Settlement prices fixed
- **Asian session (01:00-08:00 GMT):** Lower volume, China/India demand signals
- **EIA release (15:30 GMT Wednesday):** Highest volatility spike of the week
