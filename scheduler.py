from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import Database
from typing import Callable

class CleaningScheduler:
    def __init__(self, db: Database, notify_callback: Callable):
        self.scheduler = AsyncIOScheduler()
        self.db = db
        self.notify_callback = notify_callback

    def start(self):
        # Проверка каждый час
        self.scheduler.add_job(self._check_schedule, 'interval', hours=1)
        self.scheduler.start()

    async def _check_schedule(self):
        # Используем московское время (UTC+3)
        now = datetime.now(ZoneInfo("Europe/Moscow"))
        
        # Проверяем оба расписания
        for schedule_type in ['room', 'block']:
            user_id, next_cleaning = await self.db.get_next_cleaning(schedule_type)
            if not user_id or not next_cleaning:
                continue

            next_cleaning = datetime.strptime(next_cleaning, '%Y-%m-%d')
            days_until = (next_cleaning.date() - now.date()).days

            if days_until == 1:
                # Напоминание за день до уборки
                await self.notify_callback(schedule_type, user_id, "tomorrow")
            elif days_until == 0:
                # В день уборки каждые 4 часа (в 8:00, 12:00, 16:00, 20:00)
                if now.hour in [12, 15, 18, 21]:
                    await self.notify_callback(schedule_type, user_id, "today")
            elif days_until < 0:
                # После дня уборки каждые 4 часа
                if now.hour in [12, 15, 18, 21]:
                    await self.notify_callback(schedule_type, user_id, "overdue")

    async def schedule_next_cleaning(self, schedule_type: str, user_id: str):
        # Теперь эта логика реализована в методе mark_cleaning_completed
        await self.db.mark_cleaning_completed(schedule_type, user_id)
