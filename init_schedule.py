import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import Database

async def init_schedule():
    # Загружаем конфигурацию пользователей
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    db = Database()
    await db.init()

    # Инициализация расписания комнат
    start_date = datetime.strptime(config['room']['start_date'], '%Y-%m-%d')
    await db.initialize_schedule('room', config['room']['users'], start_date)

    # Инициализация расписания блока
    start_date = datetime.strptime(config['block']['start_date'], '%Y-%m-%d')
    await db.initialize_schedule('block', config['block']['users'], start_date)

if __name__ == "__main__":
    asyncio.run(init_schedule())
