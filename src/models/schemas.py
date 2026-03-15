"""
Pydantic schemas — Oil Trading Intelligence Bot v3.1
Phase 3A: Extended with adversarial stage, probability density,
          historical analogues, confidence decay, regime classification
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, List, Dict
from datetime import datetime
import uuid


# ============================================================
# Agent Signal
# ============================================================

class Signal(BaseModel):
    """Signal from one AI agent"""
    action: Literal["LONG", "SHORT", "WAIT"]
    confidence: float = Field(ge=0, le=1)
    thesis: str = Field(max_length=600)
    invalidation_price: Optional[float] = None
    risk_notes: str = ""
    sources: List[str] = Field(default_factory=list)
    drivers: List[str] = Field(default_factory=list, max_length=5)

    @field_validator("risk_notes", mode="before")
    @classmethod
    def coerce_risk_notes(cls, v):
        # LLMs sometimes return a list instead of a string
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return v

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v):
        # LLMs often return non-URL strings; keep only valid URLs, discard the rest
        return [url for url in v if isinstance(url, str) and url.startswith(("http://", "https://"))]


# ============================================================
# Historical Analogue
# ============================================================

class HistoricalAnalogue(BaseModel):
    """One historical oil market episode analogous to current event"""
    event_name: str
    year: int
    trigger: str
    similarity_score: float = Field(ge=0, le=1)
    price_impact_pct: float
    duration_days: int = Field(ge=0)
    resolution: str
    key_difference: str


# ============================================================
# Debate Steps (adversarial stage)
# ============================================================

class DebateStep(BaseModel):
    """One step in the Opus vs Gemini adversarial debate"""
    model: str
    role: Literal["primary_thesis", "counterargument", "final_verdict"]
    content: str
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    accepted_counterarguments: List[str] = Field(default_factory=list)
    rejected_counterarguments: List[str] = Field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0


class AdversarialResult(BaseModel):
    """Full result of the 3-step adversarial debate stage"""
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instrument: str
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    primary_thesis: DebateStep
    counterargument: DebateStep
    final_verdict: DebateStep

    final_action: Literal["LONG", "SHORT", "WAIT"]
    final_confidence: float = Field(ge=0, le=1)
    confidence_delta: float
    narrative_divergence: str = ""

    total_cost_usd: float = 0.0
    debate_quality: Literal["strong", "weak", "sycophantic"] = "strong"

    @property
    def was_meaningful(self) -> bool:
        """True if debate shifted something (not sycophantic)"""
        return (
            len(self.final_verdict.accepted_counterarguments) > 0
            or abs(self.confidence_delta) > 0.05
        )


# ============================================================
# Probability Density
# ============================================================

class ProbabilityDensity(BaseModel):
    """Probability distribution across directions"""
    bull: float = Field(ge=0, le=1)
    bear: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_sum(self):
        total = self.bull + self.bear + self.neutral
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"bull+bear+neutral must sum to 1.0, got {total:.3f}")
        return self


# ============================================================
# Market Events
# ============================================================

OilEventType = Literal[
    "price_spike",
    "volume_surge",
    "spread_change",
    "news_event",
    "eia_report",
    "opec_event",
    "geopolitical_alert",
    "weather_event",
    "scheduled_event",
    "influencer_signal",   # NEW Phase 3A
    "tanker_alert",        # NEW Phase 3A
]

MarketRegime = Literal["trending_up", "trending_down", "ranging", "breakout", "crisis"]


class MarketEvent(BaseModel):
    """Oil market event"""
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: OilEventType
    instrument: str
    data: dict
    severity: float = Field(ge=0, le=1)
    headline: str = ""
    source_weight: float = Field(default=0.5, ge=0, le=1)
    rag_context_ids: List[str] = Field(default_factory=list)


# ============================================================
# Oil Risk Score
# ============================================================

class OilRiskScore(BaseModel):
    """Oil market risk — 6 categories"""
    geopolitical: float = Field(ge=0, le=1)
    supply: float = Field(ge=0, le=1)
    demand: float = Field(ge=0, le=1)
    financial: float = Field(ge=0, le=1)
    seasonal: float = Field(ge=0, le=1)
    technical: float = Field(ge=0, le=1)

    @property
    def composite(self) -> float:
        weights = {"geopolitical": 0.25, "supply": 0.25, "demand": 0.20,
                   "financial": 0.10, "seasonal": 0.10, "technical": 0.10}
        return round(sum(getattr(self, k) * w for k, w in weights.items()), 3)


# ============================================================
# Oil Forecast (v3.1 — extended)
# ============================================================

class OilForecast(BaseModel):
    """Final oil price forecast — Council output"""
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    instrument: str

    direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float = Field(ge=0, le=1)
    probability_density: Optional[ProbabilityDensity] = None
    timeframe_hours: int = Field(ge=1, le=720)

    current_price: float
    target_price: float
    stop_loss_price: Optional[float] = None

    regime: Optional[MarketRegime] = None
    model_uncertainty: float = Field(default=0.0, ge=0, le=1)
    market_uncertainty: float = Field(default=0.0, ge=0, le=1)

    drivers: List[str]
    risks: List[str]
    invalidation_triggers: List[str] = Field(default_factory=list)
    narrative_divergence: str = ""

    historical_analogues: List[HistoricalAnalogue] = Field(default_factory=list)
    debate_summary: str = ""

    risk_score: OilRiskScore
    agent_votes: Dict[str, str] = Field(default_factory=dict)
    council_cost_usd: float = 0.0

    @property
    def expected_move_pct(self) -> float:
        if self.current_price == 0:
            return 0.0
        return round((self.target_price - self.current_price) / self.current_price * 100, 2)


# ============================================================
# Council Response
# ============================================================

class CouncilResponse(BaseModel):
    """Aggregated response from all agents"""
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    instrument: str

    grok: Signal
    perplexity: Signal
    claude: Signal
    gemini: Signal
    devil_advocate: Optional[Signal] = None   # NEW Phase 3A

    consensus: Literal["LONG", "SHORT", "WAIT", "CONFLICT"]
    consensus_strength: Literal["UNANIMOUS", "STRONG", "WEAK", "NONE"]
    combined_confidence: float = Field(ge=0, le=1)
    key_risks: List[str]

    invalidation_price: Optional[float] = None
    recommendation: dict

    forecast: Optional[OilForecast] = None
    adversarial_result: Optional[AdversarialResult] = None  # NEW Phase 3A

    prompt_hash: str
    total_cost_usd: float = 0.0


# ============================================================
# Agent Performance (for dynamic weights)
# ============================================================

class AgentPerformanceRecord(BaseModel):
    """Per-agent accuracy record for quarterly weight recalibration"""
    agent_name: str
    signal_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    instrument: str

    predicted_action: Literal["LONG", "SHORT", "WAIT"]
    predicted_confidence: float = Field(ge=0, le=1)

    actual_direction: Optional[Literal["UP", "DOWN", "FLAT"]] = None
    was_correct: Optional[bool] = None
    brier_score: Optional[float] = Field(None, description="Lower is better, range 0-2")


# ============================================================
# Trade Journal Entry
# ============================================================

class TradeJournalEntry(BaseModel):
    id: str
    timestamp: datetime
    trigger: MarketEvent
    council_response: CouncilResponse

    your_decision: Optional[Literal["LONG", "SHORT", "PASS"]] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    outcome: Optional[str] = None
    lessons_learned: Optional[str] = None


# ============================================================
# Risk Check
# ============================================================

class RiskCheck(BaseModel):
    allowed: bool
    reason: str
    oil_risk_score: Optional[OilRiskScore] = None
    daily_alerts_count: int = 0
    cooldown_remaining_sec: int = 0
