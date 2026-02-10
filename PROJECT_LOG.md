# Trading Council Bot - Project Log

**Проєкт:** AI-powered trading council для аналізу крипто-ринків  
**Розпочато:** 9 лютого 2026  
**Статус:** 🟡 В розробці (Phase 1: Infrastructure)

---

## 📋 Зміст

1. [Концепція проєкту](#концепція-проєкту)
2. [Архітектура системи](#архітектура-системи)
3. [Виконані кроки](#виконані-кроки)
4. [Поточна структура файлів](#поточна-структура-файлів)
5. [Наступні кроки](#наступні-кроки)
6. [Нотатки та рішення](#нотатки-та-рішення)

---

## Концепція проєкту

### Основна ідея
Створити систему з 4 AI агентів (Grok, Perplexity, Claude, Gemini), які аналізують криптовалютний ринок і дають рекомендації для трейдингу.

### Ключові принципи
- ✅ **Human-in-the-loop** - AI радить, людина вирішує
- ✅ **Event-driven** - реагує на події, не за розкладом
- ✅ **Testnet first** - тільки тестовий рахунок
- ✅ **Paper trading** - журнал всіх сигналів для аналізу
- ✅ **Transparent** - зрозумілі рішення без black box

### Архітектура (фінальна версія)

```
┌─────────────────────────────────────────────┐
│           EVENT DETECTOR                     │
│  (WebSocket, Whale Alert, Indicators)       │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│           RISK GOVERNOR                      │
│     (Hard limits, no LLM override)          │
└─────────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        ↓           ↓           ↓
   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
   │  GROK  │  │  PERP  │  │ CLAUDE │  │ GEMINI │
   │   🔥   │  │   🔍   │  │   🛡️   │  │   🔬   │
   └────────┘  └────────┘  └────────┘  └────────┘
        ↓           ↓           ↓           ↓
        └───────────┴───────────┴───────────┘
                    ↓
┌─────────────────────────────────────────────┐
│            AGGREGATOR                        │
│     (чистий Python, детермінований)         │
└─────────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
┌──────────────┐        ┌──────────────┐
│ TELEGRAM BOT │        │   JOURNAL    │
└──────────────┘        └──────────────┘
```

---

## Архітектура системи

### Ролі AI агентів

#### 1. Grok 🔥 - Sentiment Hunter
- **Роль:** Агресивний скаут, ловить хайп на X (Twitter)
- **Фокус:** X trending, influencers, memes, retail sentiment
- **Особистість:** Impulsive, FOMO-driven, bullish bias
- **Вага:** 25%

#### 2. Perplexity 🔍 - Fact Checker
- **Роль:** Скептичний журналіст-розслідувач
- **Фокус:** Primary sources, verification, fake news detection
- **Особистість:** Skeptical, evidence-based, bearish bias
- **Вага:** 25%

#### 3. Claude 🛡️ - Risk Manager
- **Роль:** Параноїдальний менеджер ризиків
- **Фокус:** Risk scenarios, invalidation levels, position sizing
- **Особистість:** Cautious, what-if thinker, neutral
- **Вага:** 25%

#### 4. Gemini 🔬 - Pattern Analyst (Historian)
- **Роль:** Науковий аналітик історичних закономірностей
- **Фокус:** Historical patterns, chart analysis, statistics
- **Особистість:** Analytical, data-driven, pattern-focused
- **Вага:** 25%

### Aggregator (не AI!)
- **Роль:** Детермінований алгоритм для об'єднання сигналів
- **Метод:** Voting + weighted confidence + risk checks
- **Чому не 5-й AI:** Transparent, no hallucinations, fast, free

---

## Виконані кроки

### ✅ Крок 1: Структура проєкту (9 лютого 2026)

**Команда:**
```bash
mkdir trading-council-bot
cd trading-council-bot
mkdir -p config src/models src/council src/detectors src/risk src/journal src/notifications tests data/logs scripts
```

**Результат:**
```
trading-council-bot/
├── config/
├── src/
│   ├── models/
│   ├── council/
│   ├── detectors/
│   ├── risk/
│   ├── journal/
│   └── notifications/
├── tests/
├── data/logs/
└── scripts/
```

---

### ✅ Крок 2: Віртуальне середовище

**Команди:**
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
```

**Результат:** Ізольоване середовище для бібліотек проєкту

---

### ✅ Крок 3: Встановлення залежностей

**Файл:** `requirements.txt`

**Вміст:**
```txt
# Основні
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Біржа
ccxt>=4.5.0
python-binance==1.0.19

# AI APIs
anthropic>=0.18.0
openai>=1.12.0
google-generativeai>=0.3.2

# Дані
pandas>=2.1.0
numpy>=1.26.0

# Повідомлення
python-telegram-bot>=20.7

# Async
aiohttp>=3.9.0

# Structured output
instructor>=0.4.0

# Логи
loguru>=0.7.0

# Тести
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

**Команда:**
```bash
pip install -r requirements.txt
```

**Проблема:** `ccxt==4.2.0` не існує  
**Рішення:** Змінено на `ccxt>=4.5.0`

**Результат:** ✅ Всі бібліотеки встановлені

---

### ✅ Крок 4: Файл .env (секретні ключі)

**Файл:** `.env`

**Вміст (поки fake):**
```bash
# EXCHANGE
BINANCE_API_KEY=fake_key_replace_later
BINANCE_API_SECRET=fake_secret_replace_later
BINANCE_TESTNET=true

# AI APIs
ANTHROPIC_API_KEY=sk-ant-fake-key
OPENAI_API_KEY=sk-fake-xai-key
GEMINI_API_KEY=fake-gemini-key

# TELEGRAM
TELEGRAM_BOT_TOKEN=123456789:FAKE-TOKEN
TELEGRAM_CHAT_ID=fake_chat_id

# RISK
MAX_POSITION_SIZE=0.05
MAX_DAILY_LOSS=0.02
MIN_LIQUIDITY=1000000

# PATHS
JOURNAL_PATH=data/trades.json
LOG_LEVEL=INFO
```

**Файл:** `.gitignore`

**Вміст:**
```
# Секрети
.env

# Venv
venv/
__pycache__/
*.pyc

# Дані
data/trades.json
data/logs/*.log

# IDE
.vscode/
.idea/
```

**Результат:** ✅ Секрети захищені від GitHub

---

### ✅ Крок 5: Налаштування (config/settings.py)

**Файл:** `config/settings.py`

**Що робить:**
- Читає змінні з `.env`
- Валідує типи даних (str, float, bool)
- Створює глобальний об'єкт `settings`

**Ключові налаштування:**
```python
class Settings(BaseSettings):
    # Exchange
    BINANCE_API_KEY: str
    BINANCE_TESTNET: bool = True
    
    # AI
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    
    # Risk
    MAX_POSITION_SIZE: float = 0.05  # 5%
    MAX_DAILY_LOSS: float = 0.02     # 2%
    MIN_LIQUIDITY: float = 1_000_000 # $1M
    
    # Council weights
    COUNCIL_WEIGHTS: dict = {
        "grok": 0.25,
        "perplexity": 0.25,
        "claude": 0.25,
        "gemini": 0.25
    }
```

**Тест:**
```bash
python config/settings.py
```

**Результат:**
```
✅ Settings loaded successfully!
📊 Watching pairs: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
🛡️ Max position size: 5.0%
```

---

### ✅ Крок 6: Моделі даних (src/models/schemas.py)

**Що створили:**

#### 1. Signal (відповідь одного агента)
```python
class Signal(BaseModel):
    action: Literal["LONG", "SHORT", "WAIT"]
    confidence: float = Field(ge=0, le=1)
    thesis: str = Field(max_length=500)
    invalidation_price: Optional[float]
    risk_notes: str
    sources: list[str]
```

**Валідація:**
- `action` - тільки LONG/SHORT/WAIT
- `confidence` - тільки 0.0-1.0
- `sources` - тільки URLs (перевірка через validator)

#### 2. CouncilResponse (рішення ради)
```python
class CouncilResponse(BaseModel):
    timestamp: datetime
    event_type: str
    pair: str
    
    # Агенти
    grok: Signal
    perplexity: Signal
    claude: Signal
    gemini: Signal
    
    # Консенсус
    consensus: Literal["LONG", "SHORT", "WAIT", "CONFLICT"]
    consensus_strength: Literal["UNANIMOUS", "STRONG", "WEAK", "NONE"]
    combined_confidence: float
    key_risks: list[str]
```

#### 3. MarketEvent (подія на ринку)
```python
class MarketEvent(BaseModel):
    timestamp: datetime
    event_type: Literal["price_spike", "whale_transfer", "funding_extreme", "volume_surge"]
    pair: str
    data: dict
    severity: float = Field(ge=0, le=1)
```

#### 4. TradeJournalEntry (запис в журналі)
```python
class TradeJournalEntry(BaseModel):
    id: str
    timestamp: datetime
    trigger: MarketEvent
    council_response: CouncilResponse
    
    your_decision: Optional[Literal["LONG", "SHORT", "PASS"]]
    entry_price: Optional[float]
    pnl: Optional[float]
    outcome: Optional[str]
    lessons_learned: Optional[str]
```

#### 5. RiskCheck (перевірка Risk Governor)
```python
class RiskCheck(BaseModel):
    allowed: bool
    reason: str
    volatility: float
    liquidity: float
    daily_loss: float
```

**Тест:** `test_schemas.py`

**Результат:**
```
✅ Signal створено: LONG з впевненістю 0.85
✅ Помилка спіймана: Invalid URL: not-a-url
✅ Помилка спіймана: ValidationError
✅ Event створено: price_spike на BTC/USDT
🎉 Всі тести пройшли!
```

---

## Поточна структура файлів

```
trading-council-bot/
├── .env                    ✅ Секретні ключі (fake поки що)
├── .gitignore              ✅ Захист секретів
├── requirements.txt        ✅ Залежності
├── PROJECT_LOG.md          ✅ Цей файл
├── test_schemas.py         ✅ Тести моделей
│
├── config/
│   ├── __init__.py         ✅
│   └── settings.py         ✅ Налаштування проєкту
│
├── src/
│   ├── models/
│   │   ├── __init__.py     ✅
│   │   └── schemas.py      ✅ Pydantic моделі
│   │
│   ├── council/            🔜 Наступний крок
│   ├── detectors/          ⏳ Пізніше
│   ├── risk/               ⏳ Пізніше
│   ├── journal/            ⏳ Пізніше
│   └── notifications/      ⏳ Пізніше
│
├── data/
│   └── logs/               ✅ Створено
│
└── venv/                   ✅ Віртуальне середовище
```

**Легенда:**
- ✅ Готово
- 🔜 Наступний крок
- ⏳ В черзі

---

## Наступні кроки

### 🔜 Phase 1.1: Council (AI агенти)

**Файли для створення:**

1. `config/prompts.py` - Системні промпти для всіх агентів
2. `src/council/base_agent.py` - Базовий клас для всіх агентів
3. `src/council/claude_agent.py` - Claude (Risk Manager)
4. `src/council/grok_agent.py` - Grok (Sentiment Hunter)
5. `src/council/gemini_agent.py` - Gemini (Pattern Analyst)
6. `src/council/perplexity_agent.py` - Perplexity (Fact Checker)
7. `src/council/aggregator.py` - Aggregator (детермінований алгоритм)

**Пріоритет:** Почнемо з Claude (найпростіший в інтеграції через офіційний SDK)

---

### ⏳ Phase 1.2: Event Detection

**Файли:**
- `src/detectors/event_detector.py` - Головний детектор
- `src/detectors/price_detector.py` - Детектор цінових спайків
- `src/detectors/whale_detector.py` - Детектор whale transfers

**Що робить:**
- Слухає Binance WebSocket
- Інтегрується з Whale Alert
- Рахує технічні індикатори (RSI, MACD)
- Тригерить Council коли виявляє аномалії

---

### ⏳ Phase 1.3: Risk & Journal

**Файли:**
- `src/risk/governor.py` - Risk Governor з hard limits
- `src/journal/logger.py` - Immutable logging
- `src/journal/paper_trader.py` - Paper trading tracker

**Що робить:**
- Risk Governor: перевіряє умови перед запуском Council
- Logger: записує всі сигнали в JSON
- Paper Trader: трекає результати рекомендацій

---

### ⏳ Phase 1.4: Notifications

**Файли:**
- `src/notifications/telegram_bot.py` - Telegram інтеграція

**Що робить:**
- Відправляє alerts в Telegram
- Форматує Council response
- Кнопки для швидких дій

---

### ⏳ Phase 1.5: Main

**Файли:**
- `src/main.py` - Головний файл запуску

**Що робить:**
- Ініціалізує всі компоненти
- Запускає event loop
- Координує роботу системи

---

## Нотатки та рішення

### Чому 4 агенти, а не 3?
**Рішення:** Додали Gemini як Pattern Analyst (історик)  
**Причина:** Gemini сильний в:
- Multimodal analysis (може аналізувати графіки як зображення)
- Pattern matching на великих даних (2M tokens context window)
- Статистичні розрахунки (code execution всередині)
- Historical pattern recognition

### Чому Aggregator не AI?
**Рішення:** Детермінований Python код, не 5-й AI агент  
**Причини:**
- ✅ Transparent (весь алгоритм відкритий і зрозумілий)
- ✅ No hallucinations (код не вигадує факти)
- ✅ Fast (< 1ms виконання)
- ✅ Free (без додаткових API costs)
- ✅ Auditable (можна перевірити кожне рішення)
- ✅ Configurable (легко змінювати ваги та правила)

### Чому testnet first?
**Рішення:** Binance Testnet обов'язковий для початку  
**Причини:**
- ✅ Безпека (fake money, нічого не втратиш)
- ✅ Можна експериментувати без страху
- ✅ Перевірка всієї логіки без ризиків
- ✅ Навчання на помилках безкоштовно

### Як обрати пороги (thresholds)?
**Поточні значення (консервативні):**
```python
PRICE_SPIKE_THRESHOLD = 0.02   # 2% за 5 хвилин
WHALE_THRESHOLD = 1_000_000    # $1M переказ
FUNDING_RATE_EXTREME = 0.001   # 0.1%
MAX_VOLATILITY = 0.10          # 10%
MAX_POSITION_SIZE = 0.05       # 5% портфеля
MAX_DAILY_LOSS = 0.02          # 2% за день
```

**План:**
1. Почати з консервативних значень
2. Записувати всі події в журнал
3. Через 1-2 тижні backtest - подивитись скільки сигналів пропущено
4. Налаштувати пороги на основі даних

### Event-driven vs scheduled?
**Рішення:** Event-driven з тригерами  
**Причини:**
- ✅ Швидша реакція на важливі події
- ✅ Економія API calls (не запитуємо постійно)
- ✅ Більш природно для трейдингу
- ❌ Складніше в реалізації (WebSockets, async)

**Компроміс:** Починаємо з scheduled (кожні 5 хв), потім додамо WebSocket

---

## Питання для вирішення

### 🤔 API ключі (TODO)
- [ ] Отримати Binance Testnet API (https://testnet.binance.vision/)
- [ ] Отримати Anthropic API key для Claude
- [ ] Отримати xAI API key для Grok
- [ ] Отримати Google AI Studio API key для Gemini
- [ ] Отримати Perplexity API key (опціонально)
- [ ] Створити Telegram бота через @BotFather

### 🤔 Prompts (TODO)
- [ ] Фіналізувати system prompts для кожного агента
- [ ] Протестувати structured output через instructor
- [ ] Додати examples в промпти (few-shot learning)

### 🤔 Архітектура (для Phase 2)
- [ ] Як зберігати prompt_hash для auditability?
- [ ] Blockchain logging для immutability?
- [ ] Narrative strength analysis (Gemini feature)
- [ ] Calibration metrics (чи AI predictions точні?)

---

## Корисні команди

### Активація/Деактивація venv
```bash
# Активація
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Деактивація
deactivate
```

### Тестування
```bash
# Тест налаштувань
python config/settings.py

# Тест моделей
python test_schemas.py

# Всі pytest тести (коли будуть)
pytest tests/ -v

# Запуск з coverage
pytest tests/ --cov=src
```

### Оновлення залежностей
```bash
# Оновити все
pip install -r requirements.txt --upgrade

# Оновити одну бібліотеку
pip install --upgrade anthropic

# Показати встановлені версії
pip list

# Показати outdated
pip list --outdated
```

### Git
```bash
# Ініціалізація
git init

# Перший commit
git add .
git commit -m "Initial project structure"

# Перевірка що .env не в git
git status  # .env не має з'являтись
```

---

## Changelog

### 2026-02-10 (ранок)
- ✅ Створено PROJECT_LOG.md
- ✅ Задокументовано всі попередні кроки
- 🔜 **НАСТУПНИЙ КРОК:** Створення Claude агента

### 2026-02-09
- ✅ Початок проєкту
- ✅ Створено структуру папок
- ✅ Налаштовано віртуальне середовище
- ✅ Встановлено залежності
  - Фікс: ccxt версія 4.2.0 → 4.5.0+
- ✅ Створено .env (з fake ключами)
- ✅ Створено .gitignore
- ✅ Створено config/settings.py
  - Тест: ✅ пройдено
- ✅ Створено src/models/schemas.py
  - Signal, CouncilResponse, MarketEvent, TradeJournalEntry, RiskCheck
  - Тест: ✅ всі моделі працюють
- ✅ Створено test_schemas.py
  - Тест: ✅ валідація працює коректно

---

## Resources & Links

### Документація
- Anthropic API: https://docs.anthropic.com/
- OpenAI API (для Grok): https://platform.openai.com/docs
- Google AI Studio: https://ai.google.dev/
- CCXT: https://docs.ccxt.com/
- Pydantic: https://docs.pydantic.dev/
- Instructor: https://python.useinstructor.com/

### Binance
- Testnet: https://testnet.binance.vision/
- API Docs: https://binance-docs.github.io/apidocs/

### Telegram
- BotFather: https://t.me/BotFather
- Bot API: https://core.telegram.org/bots/api

### Tools
- Whale Alert: https://whale-alert.io/
- Glassnode: https://glassnode.com/
- CoinGlass: https://www.coinglass.com/

---

**Кінець PROJECT_LOG.md**

*Останнє оновлення: 10 лютого 2026, ранок*
