"""
Claude Agent - Risk Manager 🛡️
Фокусується на управлінні ризиками та виявленні проблем
"""

import json
from anthropic import Anthropic
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import CLAUDE_SYSTEM_PROMPT, format_user_prompt
import instructor
from typing import Optional


class ClaudeAgent(BaseAgent):
    """
    Claude як менеджер ризиків
    
    🧒 ЩО ЦЕ:
    - Наслідується від BaseAgent
    - Використовує Anthropic SDK
    - Instructor для structured output
    - Sync версія (без async) для простоти тестування
    """
    
    def __init__(self, api_key: str):
        """
        Ініціалізація Claude агента
        
        Args:
            api_key: Anthropic API ключ
        """
        super().__init__(api_key, "Claude")
        
        # Створюємо клієнта Anthropic
        self.client = Anthropic(api_key=api_key)
        
        # Патчимо instructor'ом для structured output
        self.client = instructor.from_anthropic(self.client)
    
    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Аналізує подію з фокусом на ризики
        
        Args:
            event: Подія на ринку
            context: Додатковий контекст
        
        Returns:
            Signal з рекомендацією
        
        🔧 ФІКС: Sync метод (без async) для простоти
        """
        
        # Формуємо user prompt
        user_prompt = format_user_prompt(
            event_type=event.event_type,
            pair=event.pair,
            market_data=event.data,
            news=context.get('news', 'No recent news'),
            indicators=context.get('indicators', {})
        )
        
        try:
            # Викликаємо Claude API (sync)
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=CLAUDE_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                response_model=Signal  # Instructor примусить Signal схему
            )
            
            # Instructor повертає готовий Signal!
            return response
            
        except Exception as e:
            # Fallback з короткою thesis
            print(f"❌ Claude analysis failed: {e}")
            
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Analysis error",  # 🔧 ФІКС: коротка thesis
                risk_notes="Technical error",
                sources=[]
            )
    
    def test_connection(self) -> bool:
        """
        Тестує з'єднання з Anthropic API
        
        Returns:
            True якщо API працює
        """
        try:
            # Простий тестовий запит
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=50,
                messages=[
                    {"role": "user", "content": "Reply with: OK"}
                ]
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Claude connection test failed: {e}")
            return False


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing ClaudeAgent...")
    
    # УВАГА: Для тесту потрібен справжній API ключ!
    from config.settings import settings
    
    # Перевіряємо чи є API ключ
    if "fake" in settings.ANTHROPIC_API_KEY.lower():
        print("⚠️ Cannot test: ANTHROPIC_API_KEY is fake")
        print("   To test, add real API key to .env")
        print("\n💡 For mock testing, run: pytest tests/test_claude_agent.py")
        exit(0)
    
    # Створюємо агента
    claude = ClaudeAgent(api_key=settings.ANTHROPIC_API_KEY)
    print(f"✅ ClaudeAgent created: {claude}")
    
    # Тест 1: Перевірка з'єднання
    print("\n🔗 Testing API connection...")
    if claude.test_connection():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed")
        exit(1)
    
    # Тест 2: Тестовий аналіз
    print("\n🧪 Testing analysis...")
    
    # Створюємо тестову подію
    test_event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.8,
        data={
            "price_change": 5.2,
            "current_price": 96500,
            "volume": 2_500_000_000,
            "timeframe": "15min"
        }
    )
    
    test_context = {
        "news": "Bitcoin surges on institutional buying rumors",
        "indicators": {
            "rsi": 78,
            "macd": "bullish",
            "funding_rate": 0.08
        }
    }
    
    # Запускаємо аналіз (sync)
    signal = claude.analyze(test_event, test_context)
    
    print(f"\n✅ Analysis complete:")
    print(f"   Action: {signal.action}")
    print(f"   Confidence: {signal.confidence:.0%}")
    print(f"   Thesis: {signal.thesis[:100]}...")
    print(f"   Invalidation: ${signal.invalidation_price}")
    print(f"   Risks: {signal.risk_notes[:100]}...")
    
    print("\n🎉 ClaudeAgent test complete!")
