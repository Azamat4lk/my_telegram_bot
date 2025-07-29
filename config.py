import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties  # ✅ нужно добавить
from aiogram.enums import ParseMode  # ✅ нужно добавить

load_dotenv()

is_waiting_for_entry = {}
pending_reminders = {}
user_timezones = {}

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Токен не найден в .env!")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # ✅ новый способ решения
)