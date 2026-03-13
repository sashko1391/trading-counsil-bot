"""
Trade Journal - журнал всіх торгових рішень 📓

🧒 ЩО ЦЕ:
- Зберігає кожне рішення ради в JSON файл
- Дозволяє аналізувати минулі рішення
- Використовується Risk Governor для підрахунку денного PnL

🧒 ЧОМУ ЦЕ ВАЖЛИВО:
- Без журналу неможливо навчитись на помилках
- Потрібно для risk management (денний ліміт збитків)
- Auditability (можна перевірити чому було прийнято рішення)
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional
from models.schemas import (
    TradeJournalEntry, 
    CouncilResponse, 
    MarketEvent, 
    RiskCheck
)
import uuid


class TradeJournal:
    """
    Журнал торгових рішень
    
    🧒 ЩО РОБИТЬ:
    1. Зберігає кожне рішення ради як TradeJournalEntry
    2. Читає/записує JSON файл
    3. Рахує PnL за день (для Risk Governor)
    4. Повертає останні записи для аналізу
    """
    
    def __init__(self, journal_path: Path = None):
        """
        Ініціалізація журналу
        
        Args:
            journal_path: Шлях до JSON файлу (за замовчуванням data/trades.json)
        """
        self.journal_path = journal_path or Path("data/trades.json")
        
        # Створюємо папку якщо не існує
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Завантажуємо існуючі записи
        self.entries: List[dict] = self._load()
    
    def _load(self) -> List[dict]:
        """
        Завантажує записи з JSON файлу
        
        Returns:
            Список записів (як dict, бо не всі можуть мати всі поля)
        """
        if not self.journal_path.exists():
            return []
        
        try:
            with open(self.journal_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save(self):
        """Зберігає записи в JSON файл"""
        with open(self.journal_path, 'w', encoding='utf-8') as f:
            json.dump(self.entries, f, indent=2, default=str, ensure_ascii=False)
    
    def add_entry(
        self,
        event: MarketEvent,
        council_response: CouncilResponse,
        risk_check: Optional[RiskCheck] = None
    ) -> str:
        """
        Додає новий запис до журналу
        
        Args:
            event: Подія що тригернула аналіз
            council_response: Відповідь ради
            risk_check: Результат перевірки ризиків (опціонально)
        
        Returns:
            ID нового запису
        
        🧒 ЛОГІКА:
        - Генеруємо унікальний ID
        - Серіалізуємо всі дані в dict
        - Додаємо risk_check як окреме поле
        - Зберігаємо у файл
        """
        entry_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "trigger": event.model_dump(),
            "council_response": council_response.model_dump(),
            
            # Risk Governor результат
            "risk_check": risk_check.model_dump() if risk_check else None,
            "risk_allowed": risk_check.allowed if risk_check else None,
            
            # Ці поля заповнюються пізніше (вручну або автоматично)
            "your_decision": None,
            "entry_price": None,
            "exit_price": None,
            "pnl": None,
            "outcome": None,
            "lessons_learned": None
        }
        
        self.entries.append(entry)
        self._save()
        
        return entry_id
    
    def update_entry(
        self,
        entry_id: str,
        your_decision: Optional[str] = None,
        entry_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        pnl: Optional[float] = None,
        outcome: Optional[str] = None,
        lessons_learned: Optional[str] = None
    ) -> bool:
        """
        Оновлює існуючий запис (після закриття позиції)
        
        Args:
            entry_id: ID запису
            your_decision: Що ви реально зробили ("LONG", "SHORT", "PASS")
            entry_price: Ціна входу
            exit_price: Ціна виходу
            pnl: Прибуток/збиток (як відсоток, наприклад 0.02 = +2%)
            outcome: Короткий опис результату
            lessons_learned: Уроки
        
        Returns:
            True якщо запис знайдено і оновлено
        """
        for entry in self.entries:
            if entry["id"] == entry_id:
                if your_decision is not None:
                    entry["your_decision"] = your_decision
                if entry_price is not None:
                    entry["entry_price"] = entry_price
                if exit_price is not None:
                    entry["exit_price"] = exit_price
                if pnl is not None:
                    entry["pnl"] = pnl
                if outcome is not None:
                    entry["outcome"] = outcome
                if lessons_learned is not None:
                    entry["lessons_learned"] = lessons_learned
                
                self._save()
                return True
        
        return False
    
    def get_daily_pnl(self, target_date: date = None) -> float:
        """
        Рахує PnL за конкретний день
        
        Args:
            target_date: Дата (за замовчуванням сьогодні)
        
        Returns:
            Сумарний PnL за день (від'ємний = збиток)
        
        🧒 ВИКОРИСТОВУЄТЬСЯ Risk Governor'ом
        """
        target = target_date or date.today()
        total_pnl = 0.0
        
        for entry in self.entries:
            try:
                entry_date = datetime.fromisoformat(entry["timestamp"]).date()
                if entry_date == target and entry.get("pnl") is not None:
                    total_pnl += entry["pnl"]
            except (ValueError, KeyError):
                continue
        
        return total_pnl
    
    def get_recent(self, n: int = 10) -> List[dict]:
        """
        Повертає останні N записів
        
        Args:
            n: Кількість записів
        
        Returns:
            Список останніх записів (найновіші першими)
        """
        return list(reversed(self.entries[-n:]))
    
    def get_stats(self) -> dict:
        """
        Повертає статистику по журналу
        
        Returns:
            Dict зі статистикою
        """
        total = len(self.entries)
        
        if total == 0:
            return {
                "total_entries": 0,
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0
            }
        
        trades = [e for e in self.entries if e.get("pnl") is not None]
        wins = [e for e in trades if e["pnl"] > 0]
        
        return {
            "total_entries": total,
            "total_trades": len(trades),
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "total_pnl": sum(e["pnl"] for e in trades),
            "avg_pnl": sum(e["pnl"] for e in trades) / len(trades) if trades else 0.0
        }
    
    def __len__(self) -> int:
        return len(self.entries)
    
    def __repr__(self) -> str:
        return f"TradeJournal(entries={len(self.entries)}, path={self.journal_path})"


# ==============================================================================
# ТЕСТУВАННЯ
# ==============================================================================

if __name__ == "__main__":
    import tempfile
    
    print("🧪 Testing TradeJournal...")
    
    from models.schemas import Signal
    from council.aggregator import Aggregator
    
    # Використовуємо тимчасовий файл
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = TradeJournal(journal_path=Path(tmpdir) / "test_trades.json")
        
        # Створюємо тестові дані
        event = MarketEvent(
            event_type="price_spike",
            instrument="BZ=F",
            severity=0.8,
            data={"price_change": 5.0}
        )
        
        signal = Signal(
            action="LONG",
            confidence=0.8,
            thesis="Test",
            risk_notes="Test risk",
            sources=[]
        )
        
        aggregator = Aggregator()
        response = aggregator.aggregate(
            event=event,
            grok=signal, perplexity=signal,
            claude=signal, gemini=signal,
            prompt_hash="test"
        )
        
        risk = RiskCheck(
            allowed=True,
            reason="All checks passed",
            daily_alerts_count=1,
            cooldown_remaining_sec=0,
        )
        
        # Тест 1: Додаємо запис
        entry_id = journal.add_entry(event, response, risk)
        print(f"✅ Entry added: {entry_id}")
        assert len(journal) == 1
        
        # Тест 2: Оновлюємо запис
        journal.update_entry(entry_id, pnl=0.02, your_decision="LONG", outcome="Win!")
        print(f"✅ Entry updated")
        
        # Тест 3: Денний PnL
        pnl = journal.get_daily_pnl()
        print(f"✅ Daily PnL: {pnl:.2%}")
        assert pnl == 0.02
        
        # Тест 4: Статистика
        stats = journal.get_stats()
        print(f"✅ Stats: {stats}")
        assert stats["win_rate"] == 1.0
        
        # Тест 5: Recent
        recent = journal.get_recent(5)
        print(f"✅ Recent entries: {len(recent)}")
        assert len(recent) == 1
    
    print("\n🎉 All TradeJournal tests passed!")
