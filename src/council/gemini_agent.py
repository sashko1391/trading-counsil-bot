"""
Gemini Agent - Pattern Analyst 🔬
Шукає історичні паттерни та статистичні закономірності
"""

from google import genai  # 🔧 ФІКС: Новий SDK
from google.genai import types
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import GEMINI_SYSTEM_PROMPT, format_user_prompt
import json


class GeminiAgent(BaseAgent):
    """
    Gemini як аналітик паттернів
    
    🧒 ЩО ЦЕ:
    - Фокус: Історичні паттерни, статистика, графіки
    - Особистість: Аналітичний, data-driven
    - API: Google Gemini (новий SDK)
    """
    
    def __init__(self, api_key: str):
        """
        Ініціалізація Gemini агента
        
        Args:
            api_key: Google AI Studio API ключ
        """
        super().__init__(api_key, "Gemini")
        
        # 🔧 ФІКС: Новий спосіб ініціалізації
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash-exp"
    
    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Аналізує подію з фокусом на паттерни
        
        Args:
            event: Подія на ринку
            context: Контекст (історичні дані)
        
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
        
        # Додаємо інструкцію для JSON
        full_prompt = f"""{GEMINI_SYSTEM_PROMPT}

{user_prompt}

Respond ONLY with valid JSON matching this exact structure (no markdown, no preamble):
{{
    "action": "LONG" | "SHORT" | "WAIT",
    "confidence": 0.0-1.0,
    "thesis": "max 500 chars with historical examples",
    "invalidation_price": number or null,
    "risk_notes": "what could invalidate the pattern",
    "sources": ["url1", "url2"]
}}"""
        
        try:
            # 🔧 ФІКС: Новий спосіб виклику API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            
            # Витягуємо текст
            response_text = response.text
            
            # Витягуємо JSON з відповіді
            json_data = self.extract_json_from_response(response_text)
            
            # Валідуємо
            return self.validate_output(json_data)
            
        except Exception as e:
            print(f"❌ Gemini analysis failed: {e}")
            
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Gemini analysis error",
                risk_notes="Technical error",
                sources=[]
            )
    
    def test_connection(self) -> bool:
        """Тестує з'єднання з Gemini API"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Reply with: OK"
            )
            return "OK" in response.text
        except Exception as e:
            print(f"❌ Gemini connection test failed: {e}")
            return False


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing GeminiAgent...")
    
    from config.settings import settings
    
    # Перевіряємо API ключ
    if "fake" in settings.GEMINI_API_KEY.lower():
        print("⚠️ Cannot test: GEMINI_API_KEY is fake")
        print("   To test, add real Google AI Studio key to .env")
        print("\n💡 Get free key: https://aistudio.google.com/apikey")
        print("   For mock testing, run: pytest tests/")
        exit(0)
    
    # Створюємо агента
    gemini = GeminiAgent(api_key=settings.GEMINI_API_KEY)
    print(f"✅ GeminiAgent created: {gemini}")
    
    # Тест з'єднання
    print("\n🔗 Testing API connection...")
    if gemini.test_connection():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed")
        exit(1)
    
    # Тестовий аналіз
    print("\n🧪 Testing analysis...")
    
    test_event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.75,
        data={
            "price_change": 4.2,
            "current_price": 97000,
            "volume": 3_000_000_000,
            "pattern": "rising wedge"
        }
    )
    
    test_context = {
        "news": "Similar pattern seen in March 2024",
        "indicators": {
            "rsi": 72,
            "volume_profile": "decreasing",
            "historical_success_rate": 0.75
        }
    }
    
    signal = gemini.analyze(test_event, test_context)
    
    print(f"\n✅ Analysis complete:")
    print(f"   Action: {signal.action}")
    print(f"   Confidence: {signal.confidence:.0%}")
    print(f"   Thesis: {signal.thesis[:100]}...")
    
    print("\n🎉 GeminiAgent test complete!")
