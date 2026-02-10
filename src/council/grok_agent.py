"""
Grok Agent - Sentiment Hunter 🔥
Ловить хайп та FOMO на X (Twitter)
"""

from openai import OpenAI
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import GROK_SYSTEM_PROMPT, format_user_prompt
import instructor
import json


class GrokAgent(BaseAgent):
    """
    Grok як мисливець за sentiment
    
    🧒 ЩО ЦЕ:
    - Фокус: X/Twitter trending, memes, retail FOMO
    - Особистість: Агресивний, bullish bias
    - API: xAI через OpenAI SDK
    """
    
    def __init__(self, api_key: str):
        """
        Ініціалізація Grok агента
        
        Args:
            api_key: xAI API ключ
        """
        super().__init__(api_key, "Grok")
        
        # Створюємо OpenAI клієнта для xAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"  # xAI endpoint
        )
        
        # Патчимо instructor'ом
        self.client = instructor.from_openai(self.client)
    
    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Аналізує подію з фокусом на sentiment
        
        Args:
            event: Подія на ринку
            context: Контекст (новини, тренди)
        
        Returns:
            Signal з рекомендацією
        """
        
        # Формуємо prompt
        user_prompt = format_user_prompt(
            event_type=event.event_type,
            pair=event.pair,
            market_data=event.data,
            news=context.get('news', 'No recent news'),
            indicators=context.get('indicators', {})
        )
        
        try:
            # Викликаємо Grok API
            response = self.client.chat.completions.create(
                model="grok-beta",  # xAI model
                messages=[
                    {"role": "system", "content": GROK_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_model=Signal,
                max_tokens=1000
            )
            
            return response
            
        except Exception as e:
            print(f"❌ Grok analysis failed: {e}")
            
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Grok analysis error",
                risk_notes="Technical error",
                sources=[]
            )
    
    def test_connection(self) -> bool:
        """Тестує з'єднання з xAI API"""
        try:
            response = self.client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "user", "content": "Reply with: OK"}
                ],
                max_tokens=10
            )
            return True
        except Exception as e:
            print(f"❌ Grok connection test failed: {e}")
            return False


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing GrokAgent...")
    
    from config.settings import settings
    
    # Перевіряємо API ключ
    if "fake" in settings.OPENAI_API_KEY.lower():
        print("⚠️ Cannot test: OPENAI_API_KEY is fake")
        print("   To test, add real xAI key to .env")
        print("\n💡 Get $25 free credits: https://console.x.ai/")
        print("   For mock testing, run: pytest tests/")
        exit(0)
    
    # Створюємо агента
    grok = GrokAgent(api_key=settings.OPENAI_API_KEY)
    print(f"✅ GrokAgent created: {grok}")
    
    # Тест з'єднання
    print("\n🔗 Testing API connection...")
    if grok.test_connection():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed")
        exit(1)
    
    # Тестовий аналіз
    print("\n🧪 Testing analysis...")
    
    test_event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.9,
        data={
            "price_change": 8.5,
            "current_price": 98000,
            "volume": 5_000_000_000
        }
    )
    
    test_context = {
        "news": "Bitcoin explodes! Retail FOMO kicking in!",
        "indicators": {"rsi": 85, "twitter_mentions": "trending"}
    }
    
    signal = grok.analyze(test_event, test_context)
    
    print(f"\n✅ Analysis complete:")
    print(f"   Action: {signal.action}")
    print(f"   Confidence: {signal.confidence:.0%}")
    print(f"   Thesis: {signal.thesis[:100]}...")
    
    print("\n🎉 GrokAgent test complete!")
