#!/usr/bin/env python3
"""Generate Architecture PDF for Oil Trading Intelligence Bot (Ukrainian)."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

# Register DejaVu fonts (Cyrillic support)
pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuBd", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuMono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))

# Register font family for <b> tag support
pdfmetrics.registerFontFamily(
    "DejaVu", normal="DejaVu", bold="DejaVuBd",
)

# Colors
DARK = HexColor("#1a1a2e")
ACCENT = HexColor("#00d4aa")
GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#f0f0f0")
TABLE_HEADER = HexColor("#1a1a2e")
TABLE_ALT = HexColor("#f8f9fa")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "ARCHITECTURE.pdf")


def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "Cover", fontSize=26, leading=32, textColor=DARK,
        alignment=TA_CENTER, spaceAfter=12, fontName="DejaVuBd",
    ))
    styles.add(ParagraphStyle(
        "CoverSub", fontSize=13, leading=17, textColor=GRAY,
        alignment=TA_CENTER, spaceAfter=6, fontName="DejaVu",
    ))
    styles.add(ParagraphStyle(
        "H1", fontSize=16, leading=20, textColor=DARK,
        spaceBefore=20, spaceAfter=10, fontName="DejaVuBd",
    ))
    styles.add(ParagraphStyle(
        "H2", fontSize=12, leading=16, textColor=DARK,
        spaceBefore=14, spaceAfter=6, fontName="DejaVuBd",
    ))
    styles.add(ParagraphStyle(
        "H3", fontSize=10, leading=13, textColor=DARK,
        spaceBefore=10, spaceAfter=4, fontName="DejaVuBd",
    ))
    styles.add(ParagraphStyle(
        "Body", fontSize=9, leading=13, textColor=black,
        spaceAfter=6, fontName="DejaVu", alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        "BulletItem", fontSize=9, leading=13, textColor=black,
        spaceAfter=3, fontName="DejaVu", leftIndent=18,
        bulletIndent=6, bulletFontName="DejaVu",
    ))
    styles.add(ParagraphStyle(
        "CodeBlock", fontSize=8, leading=11, textColor=HexColor("#333"),
        fontName="DejaVuMono", backColor=LIGHT_GRAY, leftIndent=12,
        rightIndent=12, spaceBefore=4, spaceAfter=4,
        borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        "Caption", fontSize=8, leading=10, textColor=GRAY,
        alignment=TA_CENTER, spaceAfter=8, fontName="DejaVu",
    ))
    styles.add(ParagraphStyle(
        "Footer", fontSize=8, leading=10, textColor=GRAY,
        alignment=TA_CENTER, fontName="DejaVu",
    ))
    return styles


_CELL_STYLE = ParagraphStyle(
    "Cell", fontSize=8, leading=11, fontName="DejaVu", textColor=black,
)
_HEADER_CELL_STYLE = ParagraphStyle(
    "HeaderCell", fontSize=8, leading=11, fontName="DejaVuBd", textColor=white,
)


def _wrap(text, style=None):
    """Wrap cell text in a Paragraph for proper text wrapping."""
    if isinstance(text, Paragraph):
        return text
    s = style or _CELL_STYLE
    # Convert newlines to <br/> for reportlab
    t = str(text).replace("\n", "<br/>")
    return Paragraph(t, s)


def make_table(headers, rows, col_widths=None):
    """Create a styled table with Cyrillic-safe font and auto-wrapping cells."""
    wrapped_headers = [_wrap(h, _HEADER_CELL_STYLE) for h in headers]
    wrapped_rows = [[_wrap(cell) for cell in row] for row in rows]
    data = [wrapped_headers] + wrapped_rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT))
    t.setStyle(TableStyle(style))
    return t


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceBefore=6, spaceAfter=6)


def build_pdf():
    s = build_styles()
    story = []

    # ── ОБКЛАДИНКА ──
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("OIL TRADING INTELLIGENCE BOT", s["Cover"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Документ архітектури системи", s["CoverSub"]))
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph("Версія 1.0", s["CoverSub"]))
    story.append(Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y')}", s["CoverSub"]))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("КОНФІДЕНЦІЙНО", s["CoverSub"]))
    story.append(PageBreak())

    # ── ЗМІСТ ──
    story.append(Paragraph("Зміст", s["H1"]))
    toc = [
        "1. Загальний огляд",
        "2. Архітектура системи",
        "3. Джерела даних та детекція подій",
        "4. AI-агенти та аналіз",
        "5. Консенсусна агрегація",
        "6. Управління ризиками",
        "7. Сповіщення та зберігання даних",
        "8. Пошук знань (RAG)",
        "9. API-сервер та фронтенд",
        "10. Архітектура деплойменту",
        "11. Моделі даних та схеми",
        "12. Зовнішні залежності",
        "13. Безпека",
        "14. Характеристики продуктивності",
        "15. Операційні витрати",
    ]
    for item in toc:
        story.append(Paragraph(item, s["Body"]))
    story.append(PageBreak())

    # ── 1. ЗАГАЛЬНИЙ ОГЛЯД ──
    story.append(Paragraph("1. Загальний огляд", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "Oil Trading Intelligence Bot — мультиагентна AI-система, яка моніторить ринки "
        "сирої нафти та нафтопродуктів у реальному часі. Система поєднує чотири спеціалізовані "
        "AI-агенти (Claude, Grok, Perplexity, Gemini) з автоматичним моніторингом ринку, "
        "консенсусним прийняттям рішень, управлінням ризиками та миттєвими сповіщеннями "
        "через Telegram.",
        s["Body"]
    ))
    story.append(Paragraph(
        "Система працює виключно з <b>Brent Crude (BZ=F)</b> та <b>Дистилятами (HO=F проксі)</b>, "
        "використовуючи детерміністичний 5-етапний конвеєр: Детекція подій, Аналіз агентів, "
        "Консенсусна агрегація, Фільтрація ризиків та Сповіщення.",
        s["Body"]
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(make_table(
        ["Параметр", "Значення"],
        [
            ["Цільові інструменти", "Brent Crude (BZ=F), Дистиляти (HO=F проксі)"],
            ["AI-агенти", "4 (Claude, Grok, Perplexity, Gemini)"],
            ["Інтервал опитування", "15 хвилин (налаштовується)"],
            ["Технічний стек", "Python 3.12, FastAPI, React, Docker"],
            ["Деплоймент", "Docker Compose + Caddy (авто-SSL)"],
            ["Тести", "466 пройдено"],
            ["Статус", "Продакшн (всі 7 фаз завершені)"],
        ],
        col_widths=[50 * mm, 120 * mm],
    ))
    story.append(PageBreak())

    # ── 2. АРХІТЕКТУРА СИСТЕМИ ──
    story.append(Paragraph("2. Архітектура системи", s["H1"]))
    story.append(hr())
    story.append(Paragraph("5-етапний конвеєр", s["H2"]))

    pipeline_data = [
        ["Етап", "Компонент", "Опис"],
        ["1. Детекція", "OilPriceWatcher\nOilNewsScanner\nScheduledEvents\n+6 збагачувачів",
         "Виявляє стрибки цін, сплески обсягу, новинні події, заплановані каталізатори. "
         "Збагачує даними OVX волатильності, DXY/валют, COT позиціонування, погоди, "
         "маржі нафтопереробки, сезонних патернів."],
        ["2. Аналіз", "4 AI-агенти\n(паралельне виконання)",
         "Кожен агент незалежно аналізує подію та повертає структурований Signal "
         "(дія, впевненість, теза, ризики, драйвери)."],
        ["3. Агрегація", "Aggregator\n(детерміністичний Python)",
         "Зважене голосування за впевненістю формує CouncilResponse з консенсусом "
         "(LONG/SHORT/WAIT/CONFLICT) та силою (UNANIMOUS/STRONG/WEAK/NONE)."],
        ["4. Ризики", "RiskGovernor\n(6 категорій скорингу)",
         "Оцінює геополітичні, пропозиції, попиту, фінансові, сезонні та технічні ризики. "
         "Застосовує денні ліміти, кулдаун та пороги впевненості."],
        ["5. Вихід", "TelegramNotifier\nTradeJournal\nForecastTracker\nФронтенд-дашборд",
         "Надсилає алерти в Telegram, логує рішення, відстежує точність прогнозів "
         "(Brier Score), оновлює дашборд War Room."],
    ]
    story.append(make_table(
        pipeline_data[0], pipeline_data[1:],
        col_widths=[28 * mm, 42 * mm, 100 * mm],
    ))
    story.append(PageBreak())

    # ── 3. ДЖЕРЕЛА ДАНИХ ──
    story.append(Paragraph("3. Джерела даних та детекція подій", s["H1"]))
    story.append(hr())

    story.append(Paragraph("3.1 Основні вотчери", s["H2"]))
    story.append(make_table(
        ["Вотчер", "Джерело", "Що виявляє"],
        [
            ["OilPriceWatcher", "yfinance (BZ=F, HO=F)",
             "Стрибки ціни (>2%), сплески обсягу (>2x середнього), зміни крек-спреду (>5%)"],
            ["OilNewsScanner", "10 RSS-каналів (EIA, Reuters, Bloomberg, OilPrice, OPEC...)",
             "Релевантні новини нафтового ринку зі скорингом серйозності"],
            ["ScheduledEvents", "Вбудований календар",
             "Засідання ОПЕК, звіти EIA, рішення FOMC"],
        ],
        col_widths=[35 * mm, 45 * mm, 90 * mm],
    ))

    story.append(Paragraph("3.2 Джерела збагачення", s["H2"]))
    story.append(make_table(
        ["Джерело", "Дані", "API"],
        [
            ["OVX (^OVX)", "Індекс волатильності нафти, класифікація режимів", "yfinance (безкоштовно)"],
            ["DXY + валюти", "Індекс долара, EUR/USD, USD/CNY тренди", "yfinance (безкоштовно)"],
            ["CFTC COT", "Нетто-позиції Money Manager, перцентиль 52 тижні", "CFTC SODA API (безкоштовно)"],
            ["Погода/урагани", "Відстеження штормів Мексиканської затоки, NOAA алерти", "NOAA NHC API (безкоштовно)"],
            ["Маржа НПЗ", "Крек-спред 3-2-1, бензин/пічне паливо", "yfinance (безкоштовно)"],
            ["Сезонні патерни", "12-місячна база попиту", "Вбудовано"],
            ["Дані EIA", "Тижневі звіти про запаси нафти", "EIA API (безкоштовно)"],
        ],
        col_widths=[35 * mm, 55 * mm, 80 * mm],
    ))

    story.append(Paragraph("3.3 Brent: визначення активного контракту", s["H2"]))
    story.append(Paragraph(
        "Тікер BZ=F на Yahoo Finance може перейти на наступний контрактний місяць раніше, "
        "ніж фактично закінчиться поточний фронт-місяць. Система автоматично виявляє "
        "цей перехід, перевіряючи underlyingSymbol, і переключається на конкретний "
        "контракт ближнього місяця (напр., BZK26.NYM для травня 2026), забезпечуючи "
        "відповідність цін TradingView та Investing.com.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 4. AI-АГЕНТИ ──
    story.append(Paragraph("4. AI-агенти та аналіз", s["H1"]))
    story.append(hr())

    story.append(make_table(
        ["Агент", "Модель", "Провайдер", "Роль", "Фокус"],
        [
            ["Claude", "claude-sonnet-4", "Anthropic", "Ризик-CFO",
             "Контанго, крек-спреди,\nквоти ОПЕК, геопремія"],
            ["Grok", "grok-3", "xAI", "Настрої",
             "X/Twitter, гарячі новини,\nчутки, чатер танкерів"],
            ["Perplexity", "sonar", "Perplexity", "Факти",
             "EIA/IEA/ОПЕК дані,\nкрос-референс запасів"],
            ["Gemini", "gemini-2.5-flash", "Google", "Макро",
             "Сезонний попит, Китай,\nUSD, контанго/бекворд."],
        ],
        col_widths=[20 * mm, 28 * mm, 22 * mm, 18 * mm, 82 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Вихід агента: схема Signal", s["H2"]))
    story.append(make_table(
        ["Поле", "Тип", "Опис"],
        [
            ["action", "LONG / SHORT / WAIT", "Рекомендація напрямку торгівлі"],
            ["confidence", "0.0 - 1.0", "Рівень впевненості агента"],
            ["thesis", "рядок (макс. 500 символів)", "Обґрунтування українською"],
            ["risk_notes", "рядок (макс. 500 символів)", "Ключові ризики українською"],
            ["invalidation_price", "float (опціонально)", "Ціна, що скасовує тезу"],
            ["drivers", "список (1-3)", "Ключові ринкові драйвери з таксономії"],
            ["sources", "список URL", "Джерела інформації"],
        ],
        col_widths=[35 * mm, 40 * mm, 95 * mm],
    ))

    story.append(Paragraph("Адверсаріальний етап (Адвокат диявола)", s["H2"]))
    story.append(Paragraph(
        "Віртуальний 5-й агент аргументує проти консенсусу через 3-крокову дебатну модель: "
        "основна теза, контраргумент та фінальний вердикт. Включає детекцію підлабузництва, "
        "яка знижує впевненість, коли дебати не виявляють суттєвих заперечень. "
        "Цей етап може зсунути загальну впевненість на +/- 10%.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 5. АГРЕГАЦІЯ ──
    story.append(Paragraph("5. Консенсусна агрегація", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "Агрегатор використовує <b>детерміністичний Python-код</b> (без AI) для об'єднання "
        "4 сигналів агентів у єдиний CouncilResponse через зважене голосування за впевненістю.",
        s["Body"]
    ))

    story.append(make_table(
        ["Сила", "Критерій"],
        [
            ["UNANIMOUS", "Всі 4 агенти згодні + загальна впевненість > 80%"],
            ["STRONG", "3+ агенти згодні + загальна впевненість > 70%"],
            ["WEAK", "Змішані голоси + загальна впевненість 50-70%"],
            ["NONE", "Немає чіткого консенсусу або всі агенти кажуть WAIT"],
        ],
        col_widths=[35 * mm, 135 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Ваги агентів динамічно калібруються на основі історичної точності, яка відстежується "
        "через Brier Score. Надмірно впевнені агенти зменшуються; недостатньо впевнені — підсилюються.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 6. УПРАВЛІННЯ РИЗИКАМИ ──
    story.append(Paragraph("6. Управління ризиками", s["H1"]))
    story.append(hr())

    story.append(Paragraph("6-категорійний OilRiskScore", s["H2"]))
    story.append(make_table(
        ["Категорія", "Вага", "Приклади"],
        [
            ["Геополітика", "25%", "Конфлікти, санкції, вузькі місця (Ормуз, Суец)"],
            ["Пропозиція", "25%", "Скорочення ОПЕК, збої видобутку, зупинка НПЗ"],
            ["Попит", "20%", "Ризик рецесії, уповільнення Китаю, перехід на EV"],
            ["Фінанси", "10%", "Волатильність валют, рішення щодо ставок, кредитний стрес"],
            ["Сезонність", "10%", "Q1 опалювальний попит, Q3 сезон автоподорожей"],
            ["Технічний", "10%", "Сплески волатильності, пробої графіків, режим OVX"],
        ],
        col_widths=[30 * mm, 20 * mm, 120 * mm],
    ))

    story.append(Paragraph("Правила блокування", s["H2"]))
    story.append(make_table(
        ["Правило", "Поріг", "Дія"],
        [
            ["Низька впевненість", "< 60%", "БЛОКУВАТИ алерт"],
            ["Слабкий консенсус", "< STRONG", "БЛОКУВАТИ алерт"],
            ["Денний ліміт", "> 10 алертів/день", "БЛОКУВАТИ решту"],
            ["Кулдаун", "< 30 хв з останнього", "БЛОКУВАТИ (запобігання чурну)"],
            ["Високий ризик", "Композитний > 85%", "БЛОКУВАТИ алерт"],
            ["Близькість ОПЕК", "Засідання протягом 24 год", "Підвищити оцінку ризику"],
        ],
        col_widths=[35 * mm, 40 * mm, 95 * mm],
    ))
    story.append(PageBreak())

    # ── 7. СПОВІЩЕННЯ ──
    story.append(Paragraph("7. Сповіщення та зберігання даних", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Компонент", "Призначення", "Сховище"],
        [
            ["Telegram Notifier", "Алерти в реальному часі на декілька чатів", "Telegram Bot API"],
            ["Digest Summarizer", "Періодичне резюме через Gemini Flash", "Пам'ять + Telegram"],
            ["Trade Journal", "Повний аудит-трейл усіх рішень", "data/trades.json"],
            ["Денне резюме", "Підсумок тренду та статистики за день", "data/daily_summary.json"],
            ["Історія дайджестів", "Архів погодинних/6-годинних алертів", "data/digest_history.json"],
            ["Пам'ять агентів", "Історія рішень кожного агента для контексту", "data/agent_memory.json"],
            ["Трекер прогнозів", "Brier Score + відстеження точності", "data/forecast_tracker.json"],
        ],
        col_widths=[35 * mm, 55 * mm, 80 * mm],
    ))
    story.append(PageBreak())

    # ── 8. RAG ──
    story.append(Paragraph("8. Пошук знань (RAG)", s["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "Векторний пошук знань збагачує контекст агентів доменною експертизою.",
        s["Body"]
    ))
    story.append(make_table(
        ["Компонент", "Технологія"],
        [
            ["Векторна БД", "Pinecone (serverless)"],
            ["Модель ембедингів", "text-embedding-3-small (OpenAI, 1536 вимірів)"],
            ["База знань", "4 документи: основи ринку, історія ОПЕК, сезонні патерни, гайд EIA"],
            ["Потік запиту", "Формування запиту → Ембединг → Пошук top-5 схожих чанків → Інжекція в промпт"],
            ["Фолбек", "Якщо Pinecone/OpenAI недоступні, агенти продовжують без RAG-контексту"],
        ],
        col_widths=[35 * mm, 135 * mm],
    ))
    story.append(PageBreak())

    # ── 9. API ТА ФРОНТЕНД ──
    story.append(Paragraph("9. API-сервер та фронтенд", s["H1"]))
    story.append(hr())

    story.append(Paragraph("9.1 REST API ендпоінти", s["H2"]))
    story.append(make_table(
        ["Метод", "Шлях", "Опис"],
        [
            ["GET", "/api/status", "Статус системи, аптайм, підключені клієнти"],
            ["GET", "/api/forecast", "Останній OilForecast"],
            ["GET", "/api/council", "Останній CouncilResponse (голоси всіх агентів)"],
            ["GET", "/api/prices", "Поточні ціни BZ=F та LGO"],
            ["GET", "/api/agents", "Статуси агентів"],
            ["GET", "/api/risk", "Перевірка ризиків + 6-категорійна оцінка"],
            ["GET", "/api/signals", "Історія сигналів (останні 20)"],
            ["GET", "/api/history/daily", "Денні підсумки"],
            ["GET", "/api/history/digests", "Історія дайджестів"],
            ["GET", "/api/history/agents/all", "Пам'ять усіх агентів"],
            ["WS", "/ws", "WebSocket у реальному часі (авто-бродкаст)"],
        ],
        col_widths=[18 * mm, 50 * mm, 102 * mm],
    ))

    story.append(Paragraph("9.2 Фронтенд: War Room Dashboard", s["H2"]))
    story.append(Paragraph(
        "React SPA з matrix-стилем. Функції: графіки цін у реальному часі (SVG), "
        "панель консенсусу агентів, індикатор ризику, таблиця історії сигналів, "
        "панель історії (вкладки: денні/дайджести/пам'ять агентів з графіками трендів). "
        "Три теми на вибір: Matrix (зелена), Amber (помаранчева), Cyber (блакитна). "
        "WebSocket з авто-перепідключенням та фолбеком на REST-поллінг.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 10. ДЕПЛОЙМЕНТ ──
    story.append(Paragraph("10. Архітектура деплойменту", s["H1"]))
    story.append(hr())

    story.append(make_table(
        ["Сервіс", "Контейнер", "Порт", "Роль"],
        [
            ["bot", "oil-bot (Python 3.12-slim)", "8000 (внутрішній)",
             "Бекенд: FastAPI + WebSocket + конвеєр бота"],
            ["frontend", "oil-frontend (Node → serve)", "3000 (внутрішній)",
             "React SPA статичний сервер"],
            ["caddy", "caddy:2-alpine", "80, 443 (зовнішній)",
             "Зворотний проксі, авто-SSL (Let's Encrypt)"],
        ],
        col_widths=[25 * mm, 50 * mm, 35 * mm, 60 * mm],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Маршрутизація (Caddyfile)", s["H2"]))
    story.append(make_table(
        ["Шлях", "Призначення"],
        [
            ["/api/*", "bot:8000 (FastAPI бекенд)"],
            ["/ws", "bot:8000 (WebSocket)"],
            ["/*", "frontend:3000 (React SPA)"],
        ],
        col_widths=[40 * mm, 130 * mm],
    ))

    story.append(Paragraph("Персистентність даних", s["H2"]))
    story.append(Paragraph(
        "Дані бота (угоди, журнал, метрики) зберігаються у Docker named volume "
        "<b>bot-data:/app/data</b>, що забезпечує персистентність при перезапуску контейнерів. "
        "SSL-сертифікати Caddy зберігаються у volume <b>caddy-data</b>.",
        s["Body"]
    ))
    story.append(PageBreak())

    # ── 11. МОДЕЛІ ДАНИХ ──
    story.append(Paragraph("11. Моделі даних та схеми", s["H1"]))
    story.append(hr())
    story.append(Paragraph("Усі моделі використовують <b>Pydantic v2</b> зі строгою валідацією.", s["Body"]))
    story.append(make_table(
        ["Модель", "Призначення", "Ключові поля"],
        [
            ["Signal", "Рекомендація одного агента", "action, confidence, thesis, risk_notes, drivers"],
            ["MarketEvent", "Виявлена аномалія/новина", "event_type, instrument, severity, headline, data"],
            ["CouncilResponse", "Агрегований результат", "4x Signal + consensus + strength + confidence"],
            ["OilForecast", "Прогноз для дії", "direction, target_price, current_price, timeframe, drivers"],
            ["OilRiskScore", "6-категорійний ризик", "geopolitical, supply, demand, financial, seasonal, technical"],
            ["RiskCheck", "Рішення гейту", "allowed (bool), reason, daily_alerts_count"],
        ],
        col_widths=[30 * mm, 40 * mm, 100 * mm],
    ))
    story.append(PageBreak())

    # ── 12. ЗАЛЕЖНОСТІ ──
    story.append(Paragraph("12. Зовнішні залежності", s["H1"]))
    story.append(hr())

    story.append(Paragraph("12.1 API третіх сторін", s["H2"]))
    story.append(make_table(
        ["Сервіс", "Використання", "Авторизація", "Вартість"],
        [
            ["Anthropic (Claude)", "Аналіз ризиків", "API ключ", "~$45-75/міс"],
            ["xAI (Grok)", "Аналіз настроїв", "API ключ", "~$30-45/міс"],
            ["Perplexity", "Верифікація фактів", "API ключ", "~$7-15/міс"],
            ["Google (Gemini)", "Макро + дайджести", "API ключ", "~$1-4/міс"],
            ["OpenAI", "Ембединги (RAG)", "API ключ", "< $1/міс"],
            ["Pinecone", "Векторна БД", "API ключ", "Безкоштовно"],
            ["Yahoo Finance", "Дані цін", "Без авторизації", "Безкоштовно"],
            ["CFTC SODA", "COT позиціонування", "Без авторизації", "Безкоштовно"],
            ["NOAA", "Погода/урагани", "Без авторизації", "Безкоштовно"],
            ["EIA", "Статистика енергетики", "API ключ (безкоштовно)", "Безкоштовно"],
            ["Telegram", "Сповіщення", "Токен бота", "Безкоштовно"],
        ],
        col_widths=[35 * mm, 40 * mm, 35 * mm, 60 * mm],
    ))

    story.append(Paragraph("12.2 Ключові Python-пакети", s["H2"]))
    story.append(make_table(
        ["Пакет", "Версія", "Призначення"],
        [
            ["pydantic", ">= 2.5", "Валідація даних та схеми"],
            ["anthropic", ">= 0.18", "Клієнт Claude API"],
            ["openai", ">= 1.12", "OpenAI + xAI/Perplexity (сумісний ендпоінт)"],
            ["google-genai", ">= 0.3", "Клієнт Gemini API"],
            ["yfinance", ">= 0.2.30", "Ринкові дані (ціни, OVX, DXY)"],
            ["httpx", ">= 0.27", "Асинхронний HTTP-клієнт"],
            ["fastapi", ">= 0.110", "REST API фреймворк"],
            ["feedparser", ">= 6.0", "Парсинг RSS новин"],
            ["pinecone", ">= 5.0", "Клієнт векторної БД"],
            ["loguru", ">= 0.7", "Структуроване логування"],
        ],
        col_widths=[35 * mm, 25 * mm, 110 * mm],
    ))
    story.append(PageBreak())

    # ── 13. БЕЗПЕКА ──
    story.append(Paragraph("13. Безпека", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Аспект", "Реалізація"],
        [
            ["Управління секретами", "Усі API-ключі у .env (ніколи не комітяться у git)"],
            ["Валідація вводу", "Pydantic-схеми забезпечують структуру всіх зовнішніх даних"],
            ["HTTPS", "Caddy автоматично отримує сертифікати Let's Encrypt"],
            ["Заголовки безпеки", "X-Content-Type-Options, X-Frame-Options, Referrer-Policy"],
            ["Non-root контейнер", "Бот працює як appuser всередині Docker"],
            ["Обмеження частоти", "Кулдаун + денні ліміти алертів запобігають спаму"],
            ["Аудит-трейл", "Кожне рішення логується з хешем промпту (SHA256)"],
            ["Ізоляція даних", "Dry-run торгівлі в окремому файлі від продакшну"],
        ],
        col_widths=[40 * mm, 130 * mm],
    ))
    story.append(PageBreak())

    # ── 14. ПРОДУКТИВНІСТЬ ──
    story.append(Paragraph("14. Характеристики продуктивності", s["H1"]))
    story.append(hr())
    story.append(make_table(
        ["Операція", "Тривалість"],
        [
            ["Отримання ціни (yfinance)", "200-500 мс"],
            ["Опитування новин (10 RSS)", "500-1000 мс"],
            ["Один виклик AI-агента", "2-5 секунд"],
            ["4 агенти паралельно", "2-5 секунд (одночасно)"],
            ["Агрегація (детерміністична)", "< 100 мс"],
            ["Перевірка ризиків", "< 50 мс"],
            ["Сповіщення Telegram", "500-1000 мс"],
            ["Повний цикл опитування", "~7-10 секунд"],
        ],
        col_widths=[50 * mm, 120 * mm],
    ))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Використання ресурсів", s["H2"]))
    story.append(make_table(
        ["Компонент", "Пам'ять", "CPU"],
        [
            ["Bot (Python)", "300-500 МБ", "Низький (в основному I/O очікування)"],
            ["Frontend (React)", "50-100 МБ", "Мінімальний"],
            ["Caddy (проксі)", "20-30 МБ", "Мінімальний"],
            ["Разом", "~500-700 МБ", "1-2 vCPU достатньо"],
        ],
        col_widths=[40 * mm, 60 * mm, 70 * mm],
    ))
    story.append(PageBreak())

    # ── 15. ВИТРАТИ ──
    story.append(Paragraph("15. Операційні витрати", s["H1"]))
    story.append(hr())
    story.append(Paragraph("Орієнтовні місячні витрати (50 циклів опитування/день, ~10 подій/день):", s["Body"]))
    story.append(make_table(
        ["Категорія", "Сервіс", "Орієнтовна вартість/міс"],
        [
            ["AI-агенти", "Claude + Grok + Perplexity + Gemini", "$80-140"],
            ["Ембединги", "OpenAI text-embedding-3-small", "< $1"],
            ["Векторна БД", "Pinecone (безкоштовний план)", "$0"],
            ["Ринкові дані", "yfinance + CFTC + NOAA + EIA", "$0"],
            ["Інфраструктура", "Hetzner CPX22 (4 vCPU, 8 ГБ RAM)", "~$12"],
            ["Домен + SSL", "Caddy + Let's Encrypt", "$0 (авто)"],
            ["Сповіщення", "Telegram Bot API", "$0"],
            ["", "", ""],
            ["РАЗОМ", "", "$92-153/місяць"],
        ],
        col_widths=[35 * mm, 70 * mm, 65 * mm],
    ))

    story.append(Spacer(1, 10 * mm))
    story.append(hr())
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Згенеровано: {datetime.now().strftime('%d.%m.%Y')} | "
        "Oil Trading Intelligence Bot v1.0 | "
        "Усі права захищені.",
        s["Footer"]
    ))

    # Build PDF
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="Oil Trading Intelligence Bot — Архітектура",
        author="Trading Council",
    )
    doc.build(story)
    print(f"PDF згенеровано: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
