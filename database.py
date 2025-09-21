import aiosqlite
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class Database:
    def __init__(self, db_path: str = "cleaning.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Таблицы для хранения очередей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS room_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    position INTEGER NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS block_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    position INTEGER NOT NULL
                )
            """)
            
            # Таблицы для хранения дат уборки
            await db.execute("""
                CREATE TABLE IF NOT EXISTS room_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cleaning_date DATE NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_date DATE
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS block_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cleaning_date DATE NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_date DATE
                )
            """)
            await db.commit()

    async def get_next_cleaning(self, schedule_type: str) -> tuple[str, datetime]:
        table = f"{schedule_type}_schedule"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"""SELECT user_id, cleaning_date 
                   FROM {table}
                   WHERE is_completed = FALSE 
                   ORDER BY cleaning_date LIMIT 1"""
            ) as cursor:
                result = await cursor.fetchone()
                return result if result else (None, None)

    async def get_upcoming_schedule(self, schedule_type: str, limit: int = 3) -> list[tuple[str, datetime]]:
        table = f"{schedule_type}_schedule"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"""SELECT user_id, cleaning_date 
                   FROM {table}
                   WHERE is_completed = FALSE 
                   ORDER BY cleaning_date LIMIT ?""",
                (limit,)
            ) as cursor:
                return await cursor.fetchall()

    async def mark_cleaning_completed(self, schedule_type: str, user_identifier: str) -> bool:
        table = f"{schedule_type}_schedule"
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущую дату уборки
            async with db.execute(
                f"""SELECT cleaning_date 
                   FROM {table}
                   WHERE user_id = ? AND is_completed = FALSE 
                   ORDER BY cleaning_date LIMIT 1""",
                (user_identifier,)
            ) as cursor:
                result = await cursor.fetchone()
                if not result:
                    return False
                
                current_date = datetime.now(ZoneInfo("Europe/Moscow"))
                
                # Отмечаем текущую уборку как выполненную
                await db.execute(
                    f"""UPDATE {table}
                       SET is_completed = TRUE, completed_date = ? 
                       WHERE user_id = ? AND cleaning_date = ?""",
                    (current_date.date(), user_identifier, result[0])
                )
                
                # Получаем последнюю запланированную дату уборки
                async with db.execute(
                    f"""SELECT cleaning_date 
                       FROM {table}
                       WHERE is_completed = FALSE 
                       ORDER BY cleaning_date DESC LIMIT 1"""
                ) as cursor:
                    last_date = await cursor.fetchone()
                    if last_date:
                        last_date = datetime.strptime(last_date[0], '%Y-%m-%d')
                    else:
                        last_date = current_date

                # Определяем следующую дату
                if schedule_type == 'room':
                    next_date = last_date + timedelta(days=14)
                else:
                    # Для блока - то же число следующего месяца
                    if last_date.month == 12:
                        next_date = last_date.replace(year=last_date.year + 1, month=1)
                    else:
                        next_date = last_date.replace(month=last_date.month + 1)

                # Добавляем новую запись для текущего пользователя
                await db.execute(
                    f"""INSERT INTO {table} (user_id, cleaning_date, is_completed)
                       VALUES (?, ?, FALSE)""",
                    (user_identifier, next_date.date())
                )

                # Проверяем количество будущих уборок
                await self._ensure_min_schedule(db, schedule_type, next_date)
                await db.commit()
                return True

    async def _get_next_user_in_queue(self, db, schedule_type: str, current_user: str) -> str:
        queue_table = f"{schedule_type}_queue"
        async with db.execute(
            f"""SELECT user_id FROM {queue_table}
               WHERE position = (
                   SELECT (position % (SELECT COUNT(*) FROM {queue_table})) + 1 
                   FROM {queue_table}
                   WHERE user_id = ?
               )""",
            (current_user,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

    async def _ensure_min_schedule(self, db, schedule_type: str, last_date: datetime):
        """Убеждаемся, что в расписании есть как минимум 3 будущие уборки"""
        schedule_table = f"{schedule_type}_schedule"
        queue_table = f"{schedule_type}_queue"
        
        # Получаем количество будущих уборок
        async with db.execute(
            f"""SELECT COUNT(*) FROM {schedule_table}
               WHERE is_completed = FALSE"""
        ) as cursor:
            count = (await cursor.fetchone())[0]

        # Если уборок меньше 3, добавляем новые
        while count < 3:
            # Получаем последнего пользователя в расписании
            async with db.execute(
                f"""SELECT user_id FROM {schedule_table}
                   WHERE is_completed = FALSE
                   ORDER BY cleaning_date DESC LIMIT 1"""
            ) as cursor:
                last_user = await cursor.fetchone()
                if last_user:
                    last_user = last_user[0]
                else:
                    # Если расписание пустое, берем первого из очереди
                    async with db.execute(
                        f"""SELECT user_id FROM {queue_table}
                           ORDER BY position LIMIT 1"""
                    ) as cursor:
                        last_user = (await cursor.fetchone())[0]
                        last_date = datetime.now()

            # Получаем следующего пользователя
            next_user = await self._get_next_user_in_queue(db, schedule_type, last_user)
            if not next_user:
                break

            # Определяем интервал и следующую дату
            if schedule_type == 'room':
                next_date = last_date + timedelta(days=14)
            else:
                # Для блока - то же число следующего месяца
                if last_date.month == 12:
                    next_date = last_date.replace(year=last_date.year + 1, month=1)
                else:
                    next_date = last_date.replace(month=last_date.month + 1)

            # Добавляем новую уборку
            await db.execute(
                f"""INSERT INTO {schedule_table} (user_id, cleaning_date, is_completed)
                   VALUES (?, ?, FALSE)""",
                (next_user, next_date.date())
            )
            
            last_date = next_date
            count += 1

    async def get_user_stats(self, schedule_type: str) -> list[tuple[str, int, int]]:
        """Возвращает статистику по каждому пользователю: (user_id, вовремя, с опозданием)"""
        table = f"{schedule_type}_schedule"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"""SELECT 
                       user_id,
                       SUM(CASE WHEN date(completed_date) <= date(cleaning_date) THEN 1 ELSE 0 END) as on_time,
                       SUM(CASE WHEN date(completed_date) > date(cleaning_date) THEN 1 ELSE 0 END) as delayed
                   FROM {table}
                   WHERE is_completed = TRUE
                   GROUP BY user_id"""
            ) as cursor:
                return await cursor.fetchall()

    async def initialize_schedule(self, schedule_type: str, users: list[str], start_date: datetime):
        queue_table = f"{schedule_type}_queue"
        schedule_table = f"{schedule_type}_schedule"
        
        async with aiosqlite.connect(self.db_path) as db:
            # Очищаем существующие таблицы
            await db.execute(f"DELETE FROM {queue_table}")
            await db.execute(f"DELETE FROM {schedule_table}")
            
            # Добавляем пользователей в очередь
            for position, user_id in enumerate(users, 1):
                await db.execute(
                    f"INSERT INTO {queue_table} (user_id, position) VALUES (?, ?)",
                    (user_id, position)
                )

            # Создаем начальное расписание
            interval = timedelta(days=14 if schedule_type == 'room' else 30)
            last_date = start_date
            
            # Добавляем первые 3 уборки
            current_user = users[0]
            for _ in range(3):
                await db.execute(
                    f"""INSERT INTO {schedule_table} (user_id, cleaning_date, is_completed)
                       VALUES (?, ?, FALSE)""",
                    (current_user, last_date.date())
                )
                
                # Получаем следующего пользователя
                current_user = await self._get_next_user_in_queue(db, schedule_type, current_user)
                last_date = last_date + interval
            
            await db.commit()
