import logging
import asyncio
from datetime import datetime
import config
from config import pending_reminders, bot
from aiogram import Bot
from keyboards import reminder_kb
from storage import (load_reminder_settings, save_missed_entry, 
get_all_reminders, save_reminder_settings)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

scheduler = AsyncIOScheduler()
user_jobs = {}  # user_id -> list of jobs
reminder_queue = None

def set_reminder_queue(queue):
    global reminder_queue
    reminder_queue = queue

async def send_reminder(user_id: int, run_time_str: str, bot: Bot):
    if config.is_waiting_for_entry.get(user_id, False):
        return
    # FLAG = False
    config.is_waiting_for_entry[user_id] = True
    pending_reminders[user_id] = {
        "time": run_time_str,
        "sent_at": datetime.now()
    }
    text = f"⏰ Напоминание {run_time_str}: Пора записать дневник!\n\n"
    await bot.send_message(
        user_id,
        text,
        reply_markup=reminder_kb(show_examples=True)
    )

async def reminder_loop():
    while True:
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        for user_id, times in get_all_reminders().items():
            if now_str in times:
                info = pending_reminders.get(user_id)
                # ⛔ Пропускаем, если это уже напоминание, отправленное в эту минуту
                if info and info.get("time") == now_str:
                    continue
                # ❌ Если прошлое напоминание всё ещё "ждёт" — записываем как пропущенное
                if config.is_waiting_for_entry.get(user_id, False):
                    if info and "sent_at" in info:
                        sent_at = info["sent_at"]
                        if (now - sent_at).total_seconds() >= 60:
                            save_missed_entry(user_id, info["time"])
                            await bot.send_message(
                                user_id,
                                f"⚠ Пропущено напоминание {info['time']}, записано как ❌ пропуск."
                            )
                    # Сброс флага и памяти
                    pending_reminders.pop(user_id, None)
                    config.is_waiting_for_entry[user_id] = False
                # ✅ Отправляем новое напоминание
                await send_reminder(user_id, now_str, bot)
        await asyncio.sleep(5)

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
    # ❌ 3. Удаляем старые задания из планировщика
    old_jobs = user_jobs.get(user_id, [])
    for job in old_jobs:
        try:
            scheduler.remove_job(job.id)
        except Exception as e:
            logging.warning(f"Не удалось удалить задачу {job.id}: {e}")
    user_jobs[user_id] = []
    # ⏰ 4. Добавляем новые задания
    new_jobs = []
    for t in times:
        hour, minute = map(int, t.split(":"))
        job = scheduler.add_job(
            lambda uid=user_id, time_str=t: reminder_queue.put_nowait((uid, time_str)),
            CronTrigger(hour=hour, minute=minute),
            id=f"{user_id}_{t}",
            misfire_grace_time=60
        )
        new_jobs.append(job)
    user_jobs[user_id] = new_jobs