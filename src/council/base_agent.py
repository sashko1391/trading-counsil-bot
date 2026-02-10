"""
Базовий клас для всіх AI агентів
Всі агенти (Grok, Perplexity, Claude, Gemini) наслідуються від BaseAgent
"""

from abc import ABC, abstractmethod
from models.schemas import Signal, MarketEvent
import hashlib
import json
from typing import Optional


class BaseAgent(ABC):
    """
    Абстрактний базовий клас для агентів ради
    
    🧒 ЩО ЦЕ:
    - ABC = Abstract Base Class (абстрактний базовий клас)
    - "Абстрактний" означає що цей клас - це шаблон, а не готовий агент
    - Всі агенти (Claude, Grok, Gemini, Perplexity) будуть створені за цим шаблоном
    
    🧒 АНАЛОГІЯ:
    - Це як форма для печива - сама форма не є печивом
    - Але з неї можна зробити багато печив (агентів)
    """
    
    def __init__(self, api_key: str, name: str):
        """
        Ініціалізація агента
        
        Args:
            api_key: API ключ для AI сервісу
            name: Ім'я агента ("Grok", "Claude", etc.)
        """
        self.api_key = api_key
        self.name = name
    
    @abstractmethod
    def analyze(self, event: MarketEvent, context: dict) -> Signal:
        """
        Аналізує подію на ринку та повертає сигнал
        
        Args:
            event: Подія на ринку (MarketEvent)
            context: Додатковий контекст (новини, індикатори, тощо)
        
        Returns:
            Signal з рекомендацією
        
        🧒 ПОЯСНЕННЯ:
        - @abstractmethod = "абстрактний метод"
        - Це означає: кожен агент ОБОВ'ЯЗКОВО має реалізувати цей метод
        - Прибрали async - буде sync для простоти
        """
        pass
    
    def hash_prompt(self, prompt: str) -> str:
        """
        Генерує SHA256 hash промпту для auditability
        
        Args:
            prompt: Текст промпту
        
        Returns:
            Hex string з hash
        """
        return hashlib.sha256(prompt.encode()).hexdigest()
    
    def validate_output(self, output: dict) -> Signal:
        """
        Перевіряє що вивід LLM відповідає схемі Signal
        
        Args:
            output: Словник з відповіддю LLM
        
        Returns:
            Валідний Signal або fallback Signal якщо помилка
        """
        try:
            # Спробувати створити Signal з output
            return Signal(**output)
        except Exception as e:
            # Якщо помилка - повернути безпечний fallback
            print(f"⚠️ {self.name} output validation failed: {e}")
            return Signal(
                action="WAIT",
                confidence=0.0,
                thesis=f"Parse error in {self.name}",  # 🔧 ФІКС: коротка thesis
                risk_notes="Technical error in agent",
                sources=[]
            )
    
    def extract_json_from_response(self, response_text: str) -> dict:
        """
        Витягує JSON з відповіді LLM
        
        Args:
            response_text: Текст відповіді від LLM
        
        Returns:
            Словник з JSON
        """
        # Видалити markdown code blocks якщо є
        text = response_text.strip()
        
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()
        elif text.startswith("```"):
            text = text.replace("```", "").strip()
        
        # Знайти перший { та останній }
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            json_text = text[start:end]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
        else:
            raise ValueError("No JSON found in response")
    
    def format_context(self, context: dict) -> str:
        """
        Форматує context в читабельний текст
        
        Args:
            context: Словник з контекстом
        
        Returns:
            Відформатований текст
        """
        formatted = []
        
        for key, value in context.items():
            if isinstance(value, dict):
                formatted.append(f"{key.upper()}:")
                for k, v in value.items():
                    formatted.append(f"  - {k}: {v}")
            else:
                formatted.append(f"{key.upper()}: {value}")
        
        return "\n".join(formatted)
    
    def __repr__(self) -> str:
        """Строкове представлення агента"""
        return f"{self.__class__.__name__}(name={self.name})"


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    print("🧪 Testing BaseAgent...")
    
    # Створимо тестовий агент
    class TestAgent(BaseAgent):
        """Тестовий агент для перевірки BaseAgent"""
        
        def analyze(self, event: MarketEvent, context: dict) -> Signal:
            """Проста реалізація для тесту"""
            return Signal(
                action="WAIT",
                confidence=0.5,
                thesis="Test analysis",
                risk_notes="Test risk",
                sources=[]
            )
    
    # Тест 1: Створення агента
    agent = TestAgent(api_key="test_key", name="TestAgent")
    print(f"✅ Agent created: {agent}")
    
    # Тест 2: Hash промпту
    hash1 = agent.hash_prompt("Hello World")
    hash2 = agent.hash_prompt("Hello World!")
    print(f"✅ Hash test:")
    print(f"   'Hello World':  {hash1[:16]}...")
    print(f"   'Hello World!': {hash2[:16]}...")
    print(f"   Are different: {hash1 != hash2}")
    
    # Тест 3: Валідація output
    valid_output = {
        "action": "LONG",
        "confidence": 0.8,
        "thesis": "Test thesis",
        "risk_notes": "Test risk",
        "sources": ["https://example.com"]
    }
    signal = agent.validate_output(valid_output)
    print(f"✅ Valid output: {signal.action} ({signal.confidence})")
    
    # Тест 4: Невалідний output (fallback)
    invalid_output = {"invalid": "data"}
    fallback_signal = agent.validate_output(invalid_output)
    print(f"✅ Invalid output fallback: {fallback_signal.action}")
    print(f"   Thesis length: {len(fallback_signal.thesis)} chars (must be <500)")
    
    # Тест 5: Витяг JSON з тексту
    messy_response = """
    Here's my analysis:
    ```json
    {"action": "LONG", "confidence": 0.7, "thesis": "Good setup", "risk_notes": "Some risk", "sources": []}
    ```
    """
    extracted = agent.extract_json_from_response(messy_response)
    print(f"✅ JSON extracted: {extracted['action']}")
    
    print("\n🎉 All BaseAgent tests passed!")
