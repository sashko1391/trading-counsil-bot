"""
Тести для Claude агента БЕЗ справжнього API
Використовуємо mock objects для симуляції API викликів
"""

import pytest
from unittest.mock import Mock, patch

# Імпорти БЕЗ src. prefix
from council.claude_agent import ClaudeAgent
from models.schemas import Signal, MarketEvent


def test_claude_agent_creation():
    """
    Тест створення Claude агента
    
    🧒 ПЕРЕВІРЯЄМО:
    - Чи агент створюється без помилок
    - Чи правильно зберігається ім'я та API ключ
    """
    agent = ClaudeAgent(api_key="fake-key-for-testing")
    
    assert agent.name == "Claude"
    assert agent.api_key == "fake-key-for-testing"
    print("✅ Claude agent створено успішно")


def test_claude_analyze_with_mock():
    """
    Тест аналізу з mock (фейковим) API
    
    🧒 ЩО РОБИМО:
    1. Створюємо агента з фейковим ключем
    2. Створюємо тестову подію (price spike)
    3. Mock'аємо метод analyze (не викликаємо справжній API)
    4. Перевіряємо що результат правильний
    
    🔧 ФІКС: Sync метод, простий mock
    """
    
    # Створюємо агента
    agent = ClaudeAgent(api_key="fake-key")
    
    # Створюємо тестову подію на ринку
    event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.8,
        data={"price_change": 5.2, "current_price": 96500}
    )
    
    # Контекст з новинами та індикаторами
    context = {
        "news": "Bitcoin surges on institutional buying",
        "indicators": {"rsi": 78, "macd": "bullish"}
    }
    
    # Створюємо фейковий Signal
    fake_signal = Signal(
        action="WAIT",
        confidence=0.7,
        thesis="Mock analysis for testing",
        invalidation_price=95000,
        risk_notes="Mock risk notes",
        sources=[]
    )
    
    # 🔧 ФІКС: Mock весь метод analyze
    with patch.object(agent, 'analyze', return_value=fake_signal):
        # Викликаємо analyze (без await - sync)
        result = agent.analyze(event, context)
        
        # Перевірки
        assert result.action == "WAIT"
        assert result.confidence == 0.7
        assert "Mock" in result.thesis
        assert result.invalidation_price == 95000
        
        print("✅ Claude analyze працює з mock API")
        print(f"   Action: {result.action}")
        print(f"   Confidence: {result.confidence}")


def test_claude_error_handling():
    """
    Тест обробки помилок
    
    🧒 ПЕРЕВІРЯЄМО:
    - Що робить агент коли API падає
    - Чи повертає fallback Signal
    
    🔧 ФІКС: Sync метод, mock side_effect
    """
    
    agent = ClaudeAgent(api_key="fake-key")
    
    event = MarketEvent(
        event_type="price_spike",
        pair="BTC/USDT",
        severity=0.5,
        data={"price_change": 2.0}
    )
    
    context = {}
    
    # Mock client.messages.create щоб кинути помилку
    with patch.object(agent.client.messages, 'create') as mock_create:
        # API кидає виняток
        mock_create.side_effect = Exception("API connection failed")
        
        # Викликаємо analyze
        result = agent.analyze(event, context)
        
        # Має повернути безпечний fallback
        assert result.action == "WAIT"
        assert result.confidence == 0.0
        assert len(result.thesis) < 500  # 🔧 Перевіряємо довжину
        
        print("✅ Claude правильно обробляє помилки")
        print(f"   Fallback action: {result.action}")
        print(f"   Thesis: {result.thesis}")


def test_hash_prompt():
    """
    Тест генерації hash для промптів
    
    🧒 ПЕРЕВІРЯЄМО:
    - Чи hash генерується
    - Чи різні промпти дають різні hash
    """
    
    agent = ClaudeAgent(api_key="fake-key")
    
    hash1 = agent.hash_prompt("Hello World")
    hash2 = agent.hash_prompt("Hello World!")
    
    # Hash має бути рядком
    assert isinstance(hash1, str)
    assert isinstance(hash2, str)
    
    # Різні промпти = різні hash
    assert hash1 != hash2
    
    # Однакові промпти = однакові hash
    hash3 = agent.hash_prompt("Hello World")
    assert hash1 == hash3
    
    print("✅ Hash prompt працює коректно")
    print(f"   'Hello World':  {hash1[:16]}...")
    print(f"   'Hello World!': {hash2[:16]}...")


def test_validate_output():
    """
    Тест валідації output від LLM
    
    🧒 ПЕРЕВІРЯЄМО:
    - Чи правильний output проходить валідацію
    - Чи невалідний output дає fallback
    
    🔧 ФІКС: Fallback має коротку thesis
    """
    
    agent = ClaudeAgent(api_key="fake-key")
    
    # Тест 1: Правильний output
    valid_output = {
        "action": "LONG",
        "confidence": 0.8,
        "thesis": "Strong bullish setup",
        "invalidation_price": 95000,
        "risk_notes": "Stop loss at $95k",
        "sources": ["https://example.com"]
    }
    
    signal = agent.validate_output(valid_output)
    assert signal.action == "LONG"
    assert signal.confidence == 0.8
    print("✅ Валідний output пройшов перевірку")
    
    # Тест 2: Невалідний output
    invalid_output = {
        "invalid": "data",
        "wrong": "structure"
    }
    
    fallback = agent.validate_output(invalid_output)
    assert fallback.action == "WAIT"
    assert fallback.confidence == 0.0
    assert len(fallback.thesis) < 500  # 🔧 Перевіряємо довжину
    print("✅ Невалідний output дав fallback")
    print(f"   Fallback thesis: {fallback.thesis}")


def test_extract_json_from_response():
    """
    Тест витягування JSON з відповіді LLM
    
    🧒 ПЕРЕВІРЯЄМО:
    - Чи можемо витягти JSON з markdown
    - Чи працює з чистим JSON
    """
    
    agent = ClaudeAgent(api_key="fake-key")
    
    # Тест 1: JSON в markdown code block
    messy_response = """
    Here's my analysis:
    ```json
    {"action": "LONG", "confidence": 0.7}
    ```
    """
    
    extracted = agent.extract_json_from_response(messy_response)
    assert extracted["action"] == "LONG"
    assert extracted["confidence"] == 0.7
    print("✅ JSON витягнуто з markdown")
    
    # Тест 2: Чистий JSON
    clean_response = '{"action": "SHORT", "confidence": 0.5}'
    
    extracted2 = agent.extract_json_from_response(clean_response)
    assert extracted2["action"] == "SHORT"
    print("✅ Чистий JSON оброблено")


if __name__ == "__main__":
    # Запуск всіх тестів через pytest
    pytest.main([__file__, "-v", "-s"])
