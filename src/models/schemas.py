"""
Pydantic моделі для структурованих даних
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime


class Signal(BaseModel):
    """Сигнал від одного AI агента"""
    
    action: Literal["LONG", "SHORT", "WAIT"]
    confidence: float = Field(ge=0, le=1, description="Впевненість 0.0-1.0")
    thesis: str = Field(max_length=500, description="Чому цей action")
    invalidation_price: Optional[float] = Field(None, description="Ціна де теза ламається")
    risk_notes: str = Field(description="Що може піти не так")
    sources: list[str] = Field(default_factory=list, description="URLs джерел")
    
    @field_validator('sources')
    @classmethod
    def validate_sources(cls, v):
        """Перевіряє що sources - це URLs"""
        for url in v:
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL: {url}")
        return v


class CouncilResponse(BaseModel):
    """Агрегована відповідь від всіх агентів"""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str
    pair: str
    
    # Індивідуальні сигнали
    grok: Signal
    perplexity: Signal
    claude: Signal
    gemini: Signal
    
    # Агрегація
    consensus: Literal["LONG", "SHORT", "WAIT", "CONFLICT"]
    consensus_strength: Literal["UNANIMOUS", "STRONG", "WEAK", "NONE"]
    combined_confidence: float = Field(ge=0, le=1)
    key_risks: list[str]
    
    invalidation_price: Optional[float] = None
    recommendation: dict
    
    # Метадані
    prompt_hash: str = Field(description="SHA256 промпту")


class MarketEvent(BaseModel):
    """Подія на ринку"""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: Literal["price_spike", "whale_transfer", "funding_extreme", "volume_surge"]
    pair: str
    data: dict
    severity: float = Field(ge=0, le=1, description="Важливість події")


class TradeJournalEntry(BaseModel):
    """Запис в журналі торгів"""
    
    id: str
    timestamp: datetime
    trigger: MarketEvent
    council_response: CouncilResponse
    
    # Твоє рішення
    your_decision: Optional[Literal["LONG", "SHORT", "PASS"]] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    
    # Результат
    outcome: Optional[str] = None
    lessons_learned: Optional[str] = None


class RiskCheck(BaseModel):
    """Результат перевірки Risk Governor"""
    
    allowed: bool
    reason: str
    volatility: float
    liquidity: float
    daily_loss: float
