import logging
import asyncio
from datetime import datetime
import config
import pytz
from config import pending_reminders, bot
from aiogram import Bot
from keyboards import reminder_kb
from storage import (load_reminder_settings, save_missed_entry, 
get_all_reminders, save_reminder_settings, get_user_timezone)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz
from storage import get_user_timezone

scheduler = AsyncIOScheduler()
user_jobs = {}  # user_id -> list of jobs
reminder_queue = None

def set_reminder_queue(queue):
    global reminder_queue
    reminder_queue = queue

async def send_reminder(user_id: int, run_time_str: str, bot: Bot):
    if config.is_waiting_for_entry.get(user_id, False):
        return

    user_tz = pytz.timezone(get_user_timezone(user_id))
    now = datetime.now(user_tz)

    config.is_waiting_for_entry[user_id] = True
    pending_reminders[user_id] = {
        "time": run_time_str,
        "sent_at": now
    }

    text = f"⏰ Напоминание {run_time_str}: Пора записать дневник!\n\n"
    await bot.send_message(user_id, text, reply_markup=reminder_kb(show_examples=True))

async def reminder_loop():
    while True:
        user_id, time_str = await reminder_queue.get()
        user_tz = pytz.timezone(get_user_timezone(user_id))
        now = datetime.now(user_tz)

        info = pending_reminders.get(user_id)

        if info and info.get("time") == time_str:
            continue

        if config.is_waiting_for_entry.get(user_id, False):
            if info and "sent_at" in info:
                sent_at = info["sent_at"]
                if (now - sent_at).total_seconds() >= 60:
                    save_missed_entry(user_id, info["time"])
                    await bot.send_message(
                        user_id,
                        f"⚠ Пропущено напоминание {info['time']}, записано как ❌ пропуск."
                    )
            pending_reminders.pop(user_id, None)
            config.is_waiting_for_entry[user_id] = False

        await send_reminder(user_id, time_str, bot)

async def load_all_reminders():
    reminder_settings = load_reminder_settings()
    for user_id_str, times in reminder_settings.items():
        try:
            user_id = int(user_id_str)
            restart_reminders_for_user(user_id, times)
        except Exception as e:
            logging.error(f"Не удалось запустить напоминания для {user_id_str}: {e}")

def start_scheduler():
    scheduler.start()

def restart_reminders_for_user(user_id: int, times: list[str]):
    # 🧹 1. Сброс состояния, чтобы старые напоминания не сработали
    pending_reminders.pop(user_id, None)
    config.is_waiting_for_entry[user_id] = False

    # 💾 2. Сохраняем новые настройки сразу (до запуска новых задач)
    save_reminder_settings(user_id, times)

    # Получаем часовую зону пользователя
    user_tz_name = get_user_timezone(user_id)
    user_tz = pytz.timezone(user_tz_name)

    # ❌ 3. Удаляем старые задания из планировщика
    old_jobs = user_jobs.get(user_id, [])
    for job in old_jobs:
        try:
            scheduler.remove_job(job.id)
        except Exception as e:
            logging.warning(f"Не удалось удалить задачу {job.id}: {e}")
    user_jobs[user_id] = []

    # ⏰ 4. Добавляем новые задания с учётом временной зоны пользователя
    new_jobs = []
    for t in times:
        hour, minute = map(int, t.split(":"))
        job = scheduler.add_job(
            lambda uid=user_id, time_str=t: reminder_queue.put_nowait((uid, time_str)),
            CronTrigger(hour=hour, minute=minute, timezone=user_tz),
            id=f"{user_id}_{t}",
            misfire_grace_time=60
        )
        new_jobs.append(job)
    user_jobs[user_id] = new_jobs

from datetime import datetime
import pytz

def get_now(user_id: int):
    tz = config.user_timezones.get(user_id)
    if tz:
        return datetime.now(pytz.timezone(tz))
    return datetime.now()