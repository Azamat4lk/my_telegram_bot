import asyncio
import logging
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from edit_diary import router as edit_diary_router
from handlers import router as main_router
from scheduler import scheduler, load_all_reminders, start_scheduler, reminder_loop, set_reminder_queue
from config import bot

# logging.basicConfig(level=logging.INFO)

dp = Dispatcher(storage=MemoryStorage())

# Подключаем оба router-а
dp.include_router(edit_diary_router)
dp.include_router(main_router)

async def main():
    # Создаём очередь в текущем event loop
    reminder_queue = asyncio.Queue()
    set_reminder_queue(reminder_queue)  # Передаём в scheduler
    # Стартуем APScheduler
    start_scheduler()
    # Загружаем напоминания
    await load_all_reminders()
    # Запускаем reminder_loop с этой очередью
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())