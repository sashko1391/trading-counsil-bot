# Trading Council Bot 🤖

AI-powered trading intelligence system with 4 specialized agents providing multi-perspective crypto market analysis.

**Status:** 🟢 Phase 1 Complete - Council Infrastructure Ready  
**Created:** February 2026

---

## 🎯 Концепція

Система з **4 AI агентів** аналізує криптовалютний ринок з різних перспектив:

- 🔥 **Grok** - Sentiment Hunter (ловить хайп на X/Twitter)
- 🔍 **Perplexity** - Fact Checker (перевіряє факти, опціонально)
- 🛡️ **Claude** - Risk Manager (фокус на ризиках)
- 🔬 **Gemini** - Pattern Analyst (історичні паттерни)

**Aggregator** (детермінований Python) об'єднує сигнали → **Human-in-the-loop** вирішує.

---

## ✨ Ключові принципи

- ✅ **Human-in-the-loop** - AI радить, людина вирішує
- ✅ **Event-driven** - реагує на події, не за розкладом
- ✅ **Testnet first** - тільки тестовий рахунок
- ✅ **Paper trading** - журнал всіх сигналів для аналізу
- ✅ **Transparent** - зрозумілі рішення без black box

---

## 📊 Архітектура

```
EVENT DETECTOR → RISK GOVERNOR → 4 AI AGENTS (parallel) → AGGREGATOR → TELEGRAM → HUMAN
```

### Consensus Algorithm

| Голоси | Consensus | Strength | Position Size |
|--------|-----------|----------|---------------|
| 4/4 agree | LONG/SHORT | UNANIMOUS | 5% max |
| 3/4 agree | LONG/SHORT | STRONG | 3% max |
| 2/4 agree | LONG/SHORT | WEAK | 2% max |
| Split 2-2 | WAIT | NONE | 0% (no trade) |

---

## 🚀 Quick Start

### 1. Клонуй репозиторій

```bash
git clone https://github.com/your-username/trading-council-bot.git
cd trading-council-bot
```

### 2. Створи віртуальне середовище

```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# або
venv\Scripts\activate     # Windows
```

### 3. Встанови залежності

```bash
pip install -r requirements.txt
pip install -e .  # Встановлює проєкт як пакет
```

### 4. Налаштуй .env

```bash
# Скопіюй template
cp .env.example .env

# Відкрий .env і додай справжні API ключі
```

### 5. Запусти тести

```bash
# Unit тести
pytest tests/test_claude_agent.py -v

# Integration тест (БЕЗ API ключів!)
pytest tests/test_integration.py -v
```

---

## 🔑 API Ключі

### Безкоштовні:

1. **Anthropic (Claude)** - $5 free credits
   - https://console.anthropic.com/
   - Додай в `.env`: `ANTHROPIC_API_KEY=sk-ant-api03-xxxxx`

2. **Google (Gemini)** - БЕЗКОШТОВНО назавжди!
   - https://aistudio.google.com/apikey
   - Додай в `.env`: `GEMINI_API_KEY=AIzaSyxxxxx`

3. **xAI (Grok)** - $25 free credits
   - https://console.x.ai/
   - Додай в `.env`: `OPENAI_API_KEY=xai-xxxxx`

### Опціонально:

4. **Perplexity** - $5/місяць (можна пропустити)
   - Або використай звичайний web search

---

## 📁 Структура проєкту

```
trading-council-bot/
├── config/
│   ├── settings.py      # Налаштування з .env
│   └── prompts.py       # System prompts для агентів
├── src/
│   ├── models/
│   │   └── schemas.py   # Pydantic моделі
│   └── council/
│       ├── base_agent.py      # Базовий клас
│       ├── claude_agent.py    # Risk Manager 🛡️
│       ├── grok_agent.py      # Sentiment Hunter 🔥
│       ├── gemini_agent.py    # Pattern Analyst 🔬
│       ├── perplexity_agent.py # Fact Checker 🔍
│       └── aggregator.py      # Voting algorithm
├── tests/
│   ├── test_claude_agent.py   # Unit тести
│   └── test_integration.py    # Full council test
└── PROJECT_LOG.md             # Детальний лог розробки
```

---

## 🧪 Тестування

### Unit тести (БЕЗ API)

```bash
# Тест Claude агента
pytest tests/test_claude_agent.py -v

# Має вивести: 6 passed
```

### Integration тест (БЕЗ API)

```bash
# Тест всієї ради разом
pytest tests/test_integration.py -v -s

# Має вивести: 3 passed
```

### Тест Aggregator (БЕЗ API)

```bash
# Тест детермінованого алгоритму
python src/council/aggregator.py

# Має вивести: All Aggregator tests passed!
```

### Тест з REAL API

```bash
# Спочатку додай СПРАВЖНІ ключі в .env

# Тест Claude
python src/council/claude_agent.py

# Тест Gemini (безкоштовно!)
python src/council/gemini_agent.py

# Тест Grok (якщо є xAI ключ)
python src/council/grok_agent.py
```

---

## 💡 Приклад використання

```python
from council.claude_agent import ClaudeAgent
from council.grok_agent import GrokAgent
from council.gemini_agent import GeminiAgent
from council.aggregator import Aggregator
from models.schemas import MarketEvent
from config.settings import settings

# Створюємо агентів
claude = ClaudeAgent(settings.ANTHROPIC_API_KEY)
grok = GrokAgent(settings.OPENAI_API_KEY)
gemini = GeminiAgent(settings.GEMINI_API_KEY)

# Подія на ринку
event = MarketEvent(
    event_type="price_spike",
    pair="BTC/USDT",
    severity=0.85,
    data={"price_change": 6.5, "current_price": 98500}
)

context = {
    "news": "Bitcoin breaks resistance",
    "indicators": {"rsi": 76, "macd": "bullish"}
}

# Отримуємо сигнали (БЕЗ mock - справжні AI!)
claude_signal = claude.analyze(event, context)
grok_signal = grok.analyze(event, context)
gemini_signal = gemini.analyze(event, context)

# Об'єднуємо
aggregator = Aggregator()
council_response = aggregator.aggregate(
    event=event,
    grok=grok_signal,
    perplexity=wait_signal,  # Якщо немає Perplexity
    claude=claude_signal,
    gemini=gemini_signal,
    prompt_hash="example_123"
)

# Результат
print(f"Consensus: {council_response.consensus}")
print(f"Strength: {council_response.consensus_strength}")
print(f"Confidence: {council_response.combined_confidence:.0%}")
print(f"Recommendation: {council_response.recommendation}")
```

**Output приклад:**
```
Consensus: LONG
Strength: STRONG
Confidence: 70%
Recommendation: {
    'action': 'LONG',
    'max_position_size': 0.03,  # 3%
    'invalidation_price': 97000,
    'key_insights': [...]
}
```

---

## 📈 Phase 1 - ЗАВЕРШЕНО ✅

- ✅ Pydantic schemas (Signal, CouncilResponse, MarketEvent)
- ✅ BaseAgent (базовий клас)
- ✅ Claude Agent (Risk Manager)
- ✅ Grok Agent (Sentiment Hunter)
- ✅ Gemini Agent (Pattern Analyst)
- ✅ Perplexity Agent (Fact Checker, опціонально)
- ✅ Aggregator (voting algorithm)
- ✅ Unit тести (6/6 passed)
- ✅ Integration тест (3/3 passed)

---

## 🔜 Phase 2 - Наступні кроки

- ⏳ Event Detectors (price spike, whale transfer, funding extreme)
- ⏳ Risk Governor (hard limits перед Council)
- ⏳ Trade Journal (immutable logging)
- ⏳ Telegram Bot (notifications)
- ⏳ Main orchestrator (event loop)
- ⏳ Binance Testnet integration
- ⏳ Paper trading tracker

---

## 🛡️ Безпека

### Git Secrets

```bash
# .env файл НІКОЛИ не пушиться в Git
# Захищений через .gitignore

# Перевір перед commit:
git status  # .env не має з'являтись

# Опціонально встанови git-secrets:
brew install git-secrets  # Mac
git secrets --install
git secrets --add 'sk-ant-[A-Za-z0-9-]+'
git secrets --add 'sk-[A-Za-z0-9-]+'
```

### API Keys

- ❌ НІКОЛИ не пуш API ключі в Git
- ✅ Використовуй `.env` (вже в `.gitignore`)
- ✅ Для команди створи `.env.example` (БЕЗ ключів)

---

## 📚 Документація

- **PROJECT_LOG.md** - Детальний лог розробки
- **config/prompts.py** - System prompts для кожного агента
- **tests/** - Приклади використання

---

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

MIT License - see LICENSE file

---

## 🙏 Credits

- Built with Claude Sonnet 4.5
- Anthropic API for Claude
- xAI for Grok
- Google for Gemini
- Perplexity (optional)

---

## ⚠️ Disclaimer

**ВАЖЛИВО:** Це освітній проєкт. AI агенти дають рекомендації, але:

- ❌ НЕ є фінансовими порадами
- ❌ НЕ гарантують прибуток
- ❌ Можуть помилятись
- ✅ Тільки для навчання та експериментів
- ✅ Human-in-the-loop обов'язковий
- ✅ Почни з testnet та paper trading

**Трейдинг криптовалютами має високий ризик. Використовуй на свій страх і ризик.**

---

**Made with ❤️ and AI**  
*Last updated: February 10, 2026*
