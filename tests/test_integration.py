"""
Integration Test - Вся рада разом! 🎯

Тестує:
1. Всі 4 агенти (Claude, Grok, Gemini, Perplexity)
2. Aggregator
3. Повний flow: Event → Signals → Consensus → Recommendation

🧒 ПРАЦЮЄ БЕЗ СПРАВЖНІХ API КЛЮЧІВ!
Використовуємо mock objects
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Імпорти
from council.claude_agent import ClaudeAgent
from council.grok_agent import GrokAgent
from council.gemini_agent import GeminiAgent
from council.perplexity_agent import PerplexityAgent
from council.aggregator import Aggregator
from models.schemas import Signal, MarketEvent, CouncilResponse


# ==============================================================================
# ФІКСТУРИ (підготовка даних для тестів)
# ==============================================================================

@pytest.fixture
def test_event():
    """Створює тестову подію на ринку"""
    return MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.85,
        data={
            "price_change": 6.5,
            "current_price": 98500,
            "volume": 4_200_000_000,
            "timeframe": "15min",
            "trigger": "Broke resistance at $98k"
        }
    )


@pytest.fixture
def test_context():
    """Створює тестовий контекст"""
    return {
        "news": "Bitcoin breaks $98k resistance, institutional buying accelerates",
        "indicators": {
            "rsi": 76,
            "macd": "bullish_crossover",
            "volume_profile": "high",
            "funding_rate": 0.06,
            "twitter_sentiment": "extremely_bullish"
        }
    }


@pytest.fixture
def mock_grok_signal():
    """Mock сигнал від Grok (бичачий, високий confidence)"""
    return Signal(
        action="LONG",
        confidence=0.90,
        thesis="🔥 MASSIVE FOMO on X! Everyone talking about $100k BTC. Retail piling in. This is peak hype territory.",
        invalidation_price=97000,
        risk_notes="Hype can disappear instantly. Watch for sentiment shift.",
        sources=["https://x.com/crypto_influencer1", "https://x.com/whale_tracker"]
    )


@pytest.fixture
def mock_perplexity_signal():
    """Mock сигнал від Perplexity (скептичний, низький confidence)"""
    return Signal(
        action="WAIT",
        confidence=0.45,
        thesis="News is real but already 2 hours old. Can't verify if institutional buying is ongoing. Possible fake hype.",
        invalidation_price=None,
        risk_notes="Old news, likely priced in. Wait for fresh confirmation.",
        sources=["https://bloomberg.com/crypto", "https://coindesk.com/markets"]
    )


@pytest.fixture
def mock_claude_signal():
    """Mock сигнал від Claude (обережний, середній confidence)"""
    return Signal(
        action="LONG",
        confidence=0.65,
        thesis="Risk/reward acceptable IF small position. Funding rate elevated = overleveraged longs. Stop at $97k critical.",
        invalidation_price=97000,
        risk_notes="High funding = risk of long squeeze. Max 2% position. Set tight stop-loss.",
        sources=[]
    )


@pytest.fixture
def mock_gemini_signal():
    """Mock сигнал від Gemini (аналітичний, високий confidence)"""
    return Signal(
        action="LONG",
        confidence=0.80,
        thesis="Pattern matches breakout from March 2024 (led to +15% in 3 days). Volume confirms. Success rate: 7/10 historically.",
        invalidation_price=96500,
        risk_notes="Pattern fails if volume drops or breaks below $96.5k support.",
        sources=["https://tradingview.com/chart", "https://glassnode.com/btc"]
    )


# ==============================================================================
# ТЕСТИ
# ==============================================================================

def test_council_integration_mock(
    test_event, 
    test_context,
    mock_grok_signal,
    mock_perplexity_signal,
    mock_claude_signal,
    mock_gemini_signal
):
    """
    🎯 ГОЛОВНИЙ INTEGRATION TEST
    
    Тестує повний flow:
    1. Створюємо всіх агентів
    2. Mock'аємо їхні відповіді
    3. Aggregator об'єднує сигнали
    4. Перевіряємо consensus
    
    🧒 ЩО ОЧІКУЄМО:
    - Grok: LONG (0.90)
    - Perplexity: WAIT (0.45)
    - Claude: LONG (0.65)
    - Gemini: LONG (0.80)
    
    Консенсус: 3/4 LONG → STRONG consensus
    """
    
    print("\n" + "="*70)
    print("🎯 INTEGRATION TEST: Full Council Analysis")
    print("="*70)
    
    # 1. Створюємо агентів (з fake ключами)
    grok = GrokAgent(api_key="fake-grok-key")
    perplexity = PerplexityAgent(api_key="fake-perp-key")
    claude = ClaudeAgent(api_key="fake-claude-key")
    gemini = GeminiAgent(api_key="fake-gemini-key")
    
    print(f"\n✅ Created 4 agents:")
    print(f"   - {grok}")
    print(f"   - {perplexity}")
    print(f"   - {claude}")
    print(f"   - {gemini}")
    
    # 2. Mock'аємо їхні analyze методи
    with patch.object(grok, 'analyze', return_value=mock_grok_signal), \
         patch.object(perplexity, 'analyze', return_value=mock_perplexity_signal), \
         patch.object(claude, 'analyze', return_value=mock_claude_signal), \
         patch.object(gemini, 'analyze', return_value=mock_gemini_signal):
        
        # 3. Викликаємо аналіз від кожного агента
        print(f"\n📊 Event: {test_event.event_type} on {test_event.pair}")
        print(f"   Price change: +{test_event.data['price_change']}%")
        print(f"   Current price: ${test_event.data['current_price']:,}")
        
        print(f"\n🤖 Calling all agents...")
        
        grok_result = grok.analyze(test_event, test_context)
        perp_result = perplexity.analyze(test_event, test_context)
        claude_result = claude.analyze(test_event, test_context)
        gemini_result = gemini.analyze(test_event, test_context)
        
        # 4. Виводимо індивідуальні сигнали
        print(f"\n📋 Individual Signals:")
        print(f"\n   🔥 GROK (Sentiment Hunter):")
        print(f"      Action: {grok_result.action}")
        print(f"      Confidence: {grok_result.confidence:.0%}")
        print(f"      Thesis: {grok_result.thesis[:80]}...")
        
        print(f"\n   🔍 PERPLEXITY (Fact Checker):")
        print(f"      Action: {perp_result.action}")
        print(f"      Confidence: {perp_result.confidence:.0%}")
        print(f"      Thesis: {perp_result.thesis[:80]}...")
        
        print(f"\n   🛡️ CLAUDE (Risk Manager):")
        print(f"      Action: {claude_result.action}")
        print(f"      Confidence: {claude_result.confidence:.0%}")
        print(f"      Thesis: {claude_result.thesis[:80]}...")
        
        print(f"\n   🔬 GEMINI (Pattern Analyst):")
        print(f"      Action: {gemini_result.action}")
        print(f"      Confidence: {gemini_result.confidence:.0%}")
        print(f"      Thesis: {gemini_result.thesis[:80]}...")
        
        # 5. Aggregator об'єднує
        print(f"\n⚡ Aggregating signals...")
        
        aggregator = Aggregator()
        council_response = aggregator.aggregate(
            event=test_event,
            grok=grok_result,
            perplexity=perp_result,
            claude=claude_result,
            gemini=gemini_result,
            prompt_hash="test_integration_hash_123"
        )
        
        # 6. Виводимо консенсус
        print(f"\n" + "="*70)
        print(f"🎯 COUNCIL DECISION")
        print(f"="*70)
        print(f"\n   Consensus: {council_response.consensus}")
        print(f"   Strength: {council_response.consensus_strength}")
        print(f"   Combined Confidence: {council_response.combined_confidence:.0%}")
        print(f"   Votes: LONG=3, WAIT=1")
        
        print(f"\n   💡 Recommendation:")
        rec = council_response.recommendation
        print(f"      Action: {rec['action']}")
        print(f"      Max Position: {rec['max_position_size']:.1%}")
        print(f"      Invalidation: ${council_response.invalidation_price:,}")
        
        print(f"\n   ⚠️ Key Risks ({len(council_response.key_risks)}):")
        for i, risk in enumerate(council_response.key_risks[:3], 1):
            print(f"      {i}. {risk[:65]}...")
        
        # 7. Перевірки (assertions)
        print(f"\n" + "="*70)
        print(f"🧪 Running Assertions...")
        print(f"="*70)
        
        # Consensus має бути LONG (3/4 votes)
        assert council_response.consensus == "LONG", "Expected LONG consensus"
        print(f"   ✅ Consensus is LONG")
        
        # Strength має бути STRONG (3/4)
        assert council_response.consensus_strength == "STRONG", "Expected STRONG"
        print(f"   ✅ Strength is STRONG (3/4 votes)")
        
        # Combined confidence має бути середнє зважене
        expected_conf = (0.90*0.25 + 0.45*0.25 + 0.65*0.25 + 0.80*0.25)
        assert abs(council_response.combined_confidence - expected_conf) < 0.01
        print(f"   ✅ Combined confidence: {council_response.combined_confidence:.0%}")
        
        # Invalidation має бути max для LONG
        assert council_response.invalidation_price == 97000  # max(97000, 96500)
        print(f"   ✅ Invalidation price: ${council_response.invalidation_price:,}")
        
        # Position size має бути розумний
        assert 0.01 <= rec['max_position_size'] <= 0.05
        print(f"   ✅ Position size: {rec['max_position_size']:.1%}")
        
        # Має бути ризики
        assert len(council_response.key_risks) == 4  # По одному від кожного
        print(f"   ✅ All {len(council_response.key_risks)} risks collected")
        
        print(f"\n" + "="*70)
        print(f"🎉 ALL INTEGRATION TESTS PASSED!")
        print(f"="*70)
        
        return council_response


def test_unanimous_consensus():
    """
    Тест UNANIMOUS консенсусу (всі 4 згодні)
    """
    print("\n🧪 Testing UNANIMOUS consensus...")
    
    # Всі агенти кажуть LONG
    all_long = Signal(
        action="LONG",
        confidence=0.85,
        thesis="Strong bullish setup",
        invalidation_price=95000,
        risk_notes="Minimal risk",
        sources=[]
    )
    
    event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.9,
        data={"price_change": 8.0}
    )
    
    aggregator = Aggregator()
    response = aggregator.aggregate(
        event=event,
        grok=all_long,
        perplexity=all_long,
        claude=all_long,
        gemini=all_long,
        prompt_hash="unanimous_test"
    )
    
    assert response.consensus == "LONG"
    assert response.consensus_strength == "UNANIMOUS"
    print(f"   ✅ UNANIMOUS consensus detected (4/4 LONG)")


def test_conflict_consensus():
    """
    Тест CONFLICT консенсусу (розділені порівну)
    """
    print("\n🧪 Testing CONFLICT consensus...")
    
    long_signal = Signal(
        action="LONG",
        confidence=0.7,
        thesis="Bullish",
        risk_notes="Some risk",
        sources=[]
    )
    
    short_signal = Signal(
        action="SHORT",
        confidence=0.7,
        thesis="Bearish",
        risk_notes="Some risk",
        sources=[]
    )
    
    event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.5,
        data={"price_change": 2.0}
    )
    
    aggregator = Aggregator()
    response = aggregator.aggregate(
        event=event,
        grok=long_signal,
        perplexity=short_signal,
        claude=long_signal,
        gemini=short_signal,
        prompt_hash="conflict_test"
    )
    
    # 2 LONG vs 2 SHORT = CONFLICT → force WAIT
    assert response.consensus == "WAIT"
    assert response.consensus_strength == "NONE"
    print(f"   ✅ CONFLICT handled (forced to WAIT)")


# ==============================================================================
# MAIN - запуск всіх тестів
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "🚀"*35)
    print("   TRADING COUNCIL BOT - INTEGRATION TEST SUITE")
    print("🚀"*35)
    
    pytest.main([__file__, "-v", "-s", "--tb=short"])
