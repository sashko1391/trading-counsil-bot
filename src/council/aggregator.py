"""
Aggregator - об'єднує сигнали від всіх агентів
Це НЕ AI, а детермінований Python код

🧒 ЧОМУ НЕ AI:
- Transparent (зрозумілий алгоритм)
- Fast (< 1ms)
- No hallucinations
- Free (без API costs)
"""

from models.schemas import Signal, CouncilResponse, MarketEvent
from typing import Dict, List, Literal, Tuple
from datetime import datetime
import hashlib


class Aggregator:
    """
    Агрегатор сигналів від ради AI агентів
    
    🧒 ЩО РОБИТЬ:
    1. Збирає сигнали від всіх 4 агентів
    2. Рахує consensus (голосування)
    3. Рахує combined confidence (зважена середня)
    4. Визначає invalidation price
    5. Збирає всі ризики
    6. Генерує рекомендацію
    """
    
    def __init__(self, weights: dict = None):
        """
        Ініціалізація агрегатора
        
        Args:
            weights: Ваги для агентів (за замовчуванням рівні)
        """
        self.weights = weights or {
            "grok": 0.25,
            "perplexity": 0.25,
            "claude": 0.25,
            "gemini": 0.25
        }
        
        # Перевіряємо що ваги в сумі дають 1.0
        total = sum(self.weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights must sum to 1.0, got {total}"
    
    def aggregate(
        self,
        event: MarketEvent,
        grok: Signal,
        perplexity: Signal,
        claude: Signal,
        gemini: Signal,
        prompt_hash: str
    ) -> CouncilResponse:
        """
        Об'єднує сигнали від всіх агентів
        
        Args:
            event: Подія що тригернула аналіз
            grok: Сигнал від Grok
            perplexity: Сигнал від Perplexity
            claude: Сигнал від Claude
            gemini: Сигнал від Gemini
            prompt_hash: Hash промптів для auditability
        
        Returns:
            CouncilResponse з консенсусом та рекомендацією
        """
        
        signals = {
            "grok": grok,
            "perplexity": perplexity,
            "claude": claude,
            "gemini": gemini
        }
        
        # 1. Визначаємо consensus
        consensus, strength = self._calculate_consensus(signals)
        
        # 2. Рахуємо combined confidence
        combined_conf = self._calculate_combined_confidence(signals)
        
        # 3. Збираємо всі ризики
        key_risks = self._collect_risks(signals)
        
        # 4. Визначаємо invalidation price
        invalidation = self._calculate_invalidation_price(signals, consensus)
        
        # 5. Генеруємо рекомендацію
        recommendation = self._generate_recommendation(
            consensus, 
            strength, 
            combined_conf,
            invalidation,
            signals
        )
        
        # Створюємо відповідь
        return CouncilResponse(
            timestamp=datetime.now(),
            event_type=event.event_type,
            pair=event.pair,
            grok=grok,
            perplexity=perplexity,
            claude=claude,
            gemini=gemini,
            consensus=consensus,
            consensus_strength=strength,
            combined_confidence=combined_conf,
            key_risks=key_risks,
            invalidation_price=invalidation,
            recommendation=recommendation,
            prompt_hash=prompt_hash
        )
    
    def _calculate_consensus(
        self, 
        signals: Dict[str, Signal]
    ) -> Tuple[Literal["LONG", "SHORT", "WAIT", "CONFLICT"], 
               Literal["UNANIMOUS", "STRONG", "WEAK", "NONE"]]:
        """
        Рахує consensus через голосування
        
        Returns:
            (consensus_action, consensus_strength)
        
        🧒 ПРАВИЛА:
        - 4/4 = UNANIMOUS (всі згодні)
        - 3/4 = STRONG (сильна більшість)
        - 2/4 = WEAK (слабка більшість)
        - 1/4 або розділені = CONFLICT → WAIT (безпечно)
        """
        
        # Рахуємо голоси
        votes = {"LONG": 0, "SHORT": 0, "WAIT": 0}
        
        for signal in signals.values():
            votes[signal.action] += 1
        
        # Знаходимо переможця
        max_votes = max(votes.values())
        winners = [action for action, count in votes.items() if count == max_votes]
        
        # Визначаємо consensus
        if len(winners) > 1:
            # Розділені голоси - конфлікт → БЕЗПЕЧНИЙ WAIT
            return "WAIT", "NONE"  # 🔧 ФІКС: одразу повертаємо WAIT
        
        consensus = winners[0]
        
        # Визначаємо силу
        if max_votes == 4:
            strength = "UNANIMOUS"
        elif max_votes == 3:
            strength = "STRONG"
        elif max_votes == 2:
            strength = "WEAK"
        else:
            strength = "NONE"
        
        return consensus, strength
    
    def _calculate_combined_confidence(self, signals: Dict[str, Signal]) -> float:
        """
        Рахує зважену середню confidence
        
        Returns:
            Combined confidence (0.0-1.0)
        
        🧒 ФОРМУЛА:
        grok * 0.25 + perp * 0.25 + claude * 0.25 + gemini * 0.25
        """
        combined = 0.0
        
        for name, signal in signals.items():
            weight = self.weights.get(name, 0.25)
            combined += signal.confidence * weight
        
        return round(combined, 2)
    
    def _collect_risks(self, signals: Dict[str, Signal]) -> List[str]:
        """
        Збирає всі унікальні ризики від агентів
        
        Returns:
            Список ризиків
        """
        risks = []
        
        for name, signal in signals.items():
            if signal.risk_notes and signal.risk_notes not in risks:
                # Додаємо з префіксом агента
                risk = f"[{name.upper()}] {signal.risk_notes}"
                risks.append(risk)
        
        return risks
    
    def _calculate_invalidation_price(
        self, 
        signals: Dict[str, Signal],
        consensus: str
    ) -> float:
        """
        Визначає invalidation price
        
        🧒 ЛОГІКА:
        - LONG → бере МАКСИМАЛЬНИЙ invalidation (найобережніший)
        - SHORT → бере МІНІМАЛЬНИЙ invalidation (найобережніший)
        - WAIT/CONFLICT → None
        """
        
        if consensus in ["WAIT", "CONFLICT"]:
            return None
        
        # Збираємо всі invalidation prices
        prices = [
            s.invalidation_price 
            for s in signals.values() 
            if s.invalidation_price is not None
        ]
        
        if not prices:
            return None
        
        # LONG → максимальний (найвищий stop-loss)
        # SHORT → мінімальний (найнижчий stop-loss)
        if consensus == "LONG":
            return max(prices)
        else:  # SHORT
            return min(prices)
    
    def _generate_recommendation(
        self,
        consensus: str,
        strength: str,
        confidence: float,
        invalidation: float,
        signals: Dict[str, Signal]
    ) -> dict:
        """
        Генерує структуровану рекомендацію
        
        Returns:
            Dict з рекомендацією
        """
        
        # Базова рекомендація
        rec = {
            "action": consensus,
            "strength": strength,
            "confidence": confidence
        }
        
        # Якщо WAIT або CONFLICT - тільки базова інфа
        if consensus in ["WAIT", "CONFLICT"]:
            rec["reason"] = "Insufficient consensus or high uncertainty"
            return rec
        
        # Для LONG/SHORT додаємо деталі
        rec["invalidation_price"] = invalidation
        
        # Position sizing на основі strength + confidence
        if strength == "UNANIMOUS" and confidence >= 0.8:
            max_position = 0.05  # 5% (максимум)
        elif strength == "STRONG" and confidence >= 0.7:
            max_position = 0.03  # 3%
        elif strength in ["STRONG", "WEAK"] and confidence >= 0.6:
            max_position = 0.02  # 2%
        else:
            max_position = 0.01  # 1% (мінімум)
        
        rec["max_position_size"] = max_position
        
        # Збираємо ключові insights
        insights = []
        for name, signal in signals.items():
            if signal.action == consensus:
                # Якщо агент згоден з консенсусом - додаємо його thesis
                insight = f"{name.upper()}: {signal.thesis[:100]}"
                insights.append(insight)
        
        rec["key_insights"] = insights
        
        return rec


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing Aggregator...")
    
    # Створюємо тестові сигнали
    grok_signal = Signal(
        action="LONG",
        confidence=0.85,
        thesis="Massive FOMO on X, retail buying heavily",
        invalidation_price=95000,
        risk_notes="Could be fake hype",
        sources=["https://x.com/example"]
    )
    
    perp_signal = Signal(
        action="WAIT",
        confidence=0.4,
        thesis="Can't verify the news from primary sources",
        invalidation_price=None,
        risk_notes="Unverified information",
        sources=[]
    )
    
    claude_signal = Signal(
        action="LONG",
        confidence=0.6,
        thesis="Risk/reward is acceptable if stop at $95k",
        invalidation_price=95000,
        risk_notes="High volatility, small position recommended",
        sources=[]
    )
    
    gemini_signal = Signal(
        action="LONG",
        confidence=0.75,
        thesis="Similar pattern in March 2024 led to +12% move",
        invalidation_price=94500,
        risk_notes="Pattern could fail if volume drops",
        sources=["https://tradingview.com/example"]
    )
    
    # Створюємо тестову подію
    test_event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.8,
        data={"price_change": 5.2}
    )
    
    # Створюємо aggregator
    agg = Aggregator()
    
    # Агрегуємо
    response = agg.aggregate(
        event=test_event,
        grok=grok_signal,
        perplexity=perp_signal,
        claude=claude_signal,
        gemini=gemini_signal,
        prompt_hash="test_hash_123"
    )
    
    # Перевірки
    print(f"\n✅ Aggregation complete:")
    print(f"   Consensus: {response.consensus} ({response.consensus_strength})")
    print(f"   Combined confidence: {response.combined_confidence:.0%}")
    print(f"   Votes: LONG=3, WAIT=1 → Should be STRONG")
    assert response.consensus == "LONG"
    assert response.consensus_strength == "STRONG"
    
    print(f"\n   Invalidation: ${response.invalidation_price}")
    print(f"   Should be max(95000, 94500) = 95000 for LONG")
    assert response.invalidation_price == 95000
    
    print(f"\n   Key risks ({len(response.key_risks)}):")
    for risk in response.key_risks:
        print(f"      - {risk[:60]}...")
    
    print(f"\n   Recommendation:")
    print(f"      Action: {response.recommendation['action']}")
    print(f"      Max position: {response.recommendation['max_position_size']:.1%}")
    
    print("\n🎉 All Aggregator tests passed!")
