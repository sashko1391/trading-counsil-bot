"""
Perplexity Agent - Fact Checker 🔍
Перевіряє факти та первинні джерела

⚠️ УВАГА: Perplexity API платний ($5/місяць)
Можна замінити на звичайний web search або пропустити
"""

from openai import OpenAI
from council.base_agent import BaseAgent
from models.schemas import Signal, MarketEvent
from config.prompts import PERPLEXITY_SYSTEM_PROMPT, format_user_prompt
import instructor


class PerplexityAgent(BaseAgent):
    """
    Perplexity як fact checker
    
    🧒 ЩО ЦЕ:
    - Фокус: Первинні джерела, перевірка фактів
    - Особистість: Скептичний, bearish bias
    - API: Perplexity через OpenAI SDK
    
    ⚠️ ОПЦІОНАЛЬНО: Можна не використовувати якщо немає API ключа
    """
    
    def __init__(self, api_key: str):
        """
        Ініціалізація Perplexity агента
        
        Args:
            api_key: Perplexity API ключ
        """
        super().__init__(api_key, "Perplexity")
        
        # Створюємо OpenAI клієнта для Perplexity
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        # Патчимо instructor'ом
        self.client = instructor.from_openai(self.client)
    
    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Аналізує подію з фокусом на fact-checking
        
        Args:
            event: Подія на ринку
            context: Контекст (новини для перевірки)
        
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
            # Викликаємо Perplexity API
            response = self.client.chat.completions.create(
                model="llama-3.1-sonar-small-128k-online",  # Perplexity model
                messages=[
                    {"role": "system", "content": PERPLEXITY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_model=Signal,
                max_tokens=1000
            )
            
            return response
            
        except Exception as e:
            print(f"❌ Perplexity analysis failed: {e}")
            
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis="Perplexity analysis error",
                risk_notes="Technical error",
                sources=[]
            )
    
    def test_connection(self) -> bool:
        """Тестує з'єднання з Perplexity API"""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-sonar-small-128k-online",
                messages=[
                    {"role": "user", "content": "Reply with: OK"}
                ],
                max_tokens=10
            )
            return True
        except Exception as e:
            print(f"❌ Perplexity connection test failed: {e}")
            return False


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing PerplexityAgent...")
    
    from config.settings import settings
    
    # Перевіряємо API ключ
    # ⚠️ Якщо немає Perplexity ключа - це нормально!
    print("⚠️ Perplexity API is optional and paid")
    print("   You can skip this agent or use web search instead")
    
    if not hasattr(settings, 'PERPLEXITY_API_KEY'):
        print("\n💡 No PERPLEXITY_API_KEY in settings - agent will be skipped")
        print("   Add to .env if you want to use it:")
        print("   PERPLEXITY_API_KEY=pplx-xxxxx")
        exit(0)
    
    if "fake" in settings.PERPLEXITY_API_KEY.lower():
        print("⚠️ Cannot test: PERPLEXITY_API_KEY is fake")
        exit(0)
    
    # Створюємо агента
    perplexity = PerplexityAgent(api_key=settings.PERPLEXITY_API_KEY)
    print(f"✅ PerplexityAgent created: {perplexity}")
    
    # Тест з'єднання
    print("\n🔗 Testing API connection...")
    if perplexity.test_connection():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed")
        exit(1)
    
    print("\n🎉 PerplexityAgent test complete!")
