import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from dotenv import load_dotenv
from database import Database
from scheduler import CleaningScheduler

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
db = Database()
CHAT_ID = os.getenv("CHAT_ID")

# Словарь с текстами напоминаний
REMINDER_TEXTS = {
    'room': {
        'tomorrow': "Завтра твоя очередь убираться в комнате! 🧹",
        'today': "Сегодня твоя очередь убираться в комнате! Не забудь отметить выполнение командой /done_room 🧹",
        'overdue': "Ты пропустил уборку в комнате! Пожалуйста, сделай её как можно скорее и отметь командой /done_room 😕"
    },
    'block': {
        'tomorrow': "Завтра твоя очередь убираться в блоке! 🧹",
        'today': "Сегодня твоя очередь убираться в блоке! Не забудь отметить выполнение командой /done_block 🧹",
        'overdue': "Ты пропустил уборку в блоке! Пожалуйста, сделай её как можно скорее и отметь командой /done_block 😕"
    }
}

async def notify_about_cleaning(schedule_type: str, user_identifier: str, reminder_type: str):
    """Отправка напоминания о уборке"""
    text = REMINDER_TEXTS[schedule_type][reminder_type]
    # Если это username, используем его напрямую, иначе формируем ссылку через ID
    if user_identifier.startswith('@'):
        mention = user_identifier
    else:
        mention = f"<a href='tg://user?id={user_identifier}'>Напоминание</a>"
    await bot.send_message(CHAT_ID, f"{mention}: {text}", 
                          parse_mode="HTML")

scheduler = CleaningScheduler(db, notify_about_cleaning)

@dp.message(Command("done_room"))
async def cmd_done_room(message: types.Message):
    user_identifier = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    if await db.mark_cleaning_completed('room', user_identifier):
        await message.reply("Отлично! Уборка в комнате отмечена как выполненная! 👍")
    else:
        await message.reply("Не найдена активная уборка для вас! Проверьте расписание командой /schedule")

@dp.message(Command("done_block"))
async def cmd_done_block(message: types.Message):
    user_identifier = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    if await db.mark_cleaning_completed('block', user_identifier):
        await message.reply("Отлично! Уборка в блоке отмечена как выполненная! 👍")
    else:
        await message.reply("Не найдена активная уборка для вас! Проверьте расписание командой /schedule")

@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message):
    room_schedule = await db.get_upcoming_schedule('room')
    block_schedule = await db.get_upcoming_schedule('block')
    
    response = "📅 Ближайшие дежурства:\n\n"
    
    response += "🏠 Уборка комнаты:\n"
    for user_id, date in room_schedule:
        date_str = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')
        response += f"- {date_str}: {user_id}\n"
    
    response += "\n🏢 Уборка блока:\n"
    for user_id, date in block_schedule:
        date_str = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')
        response += f"- {date_str}: {user_id}\n"
    
    await message.reply(response)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    room_stats = await db.get_user_stats('room')
    block_stats = await db.get_user_stats('block')
    
    response = "📊 Статистика уборок:\n\n"
    
    response += "🏠 Комната:\n"
    for user_id, on_time, delayed in room_stats:
        response += f"{user_id}: ✅{on_time} ⏰{delayed}\n"
    
    response += "\n🏢 Блок:\n"
    for user_id, on_time, delayed in block_stats:
        response += f"{user_id}: ✅{on_time} ⏰{delayed}\n"
    
    await message.reply(response)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
Доступные команды:
/done_room - отметить уборку в комнате как выполненную
/done_block - отметить уборку в блоке как выполненную
/schedule - показать ближайшие 3 дежурства
/stats - показать статистику уборок
/help - показать это сообщение
/my_id - показать ID текущего чата
    """
    await message.reply(help_text)

@dp.message(Command("my_id"))
async def cmd_my_id(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    await message.reply(f"ID этого чата: {chat_id}\nВаш ID: {user_id}")

async def main():
    await db.init()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

