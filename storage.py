import os
from datetime import datetime
import shutil
import json

POINTS_FILE = "points.json"
DATA_FOLDER = "user_data"
REMINDERS_FILE = "reminders.json"
TIMEZONE_FILE = "user_timezones.json"
HIDDEN_MARKER = "\u2063"  # невидимый символ
os.makedirs(DATA_FOLDER, exist_ok=True)

def get_user_data(user_id: int) -> dict:
    """
    Загружает данные пользователя из JSON-файла.
    Если файла нет — возвращает пустой словарь.
    """
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    filepath = os.path.join(DATA_FOLDER, f"{user_id}.json")
    
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_missed_entry(user_id, reason):
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        time_str = "🕗 Утро"
    elif hour < 18:
        time_str = "🕛 День"
    else:
        time_str = "🌙 Вечер"
    with open(get_user_file(user_id), "a", encoding="utf-8") as f:
        f.write(f"\n\n{time_str} — {now.strftime('%Y-%m-%d %H:%M')}\n⛔ {HIDDEN_MARKER}Пропуск записи. Причина - {reason}\n\n")
    #reason
    
def load_reminder_settings():
    if os.path.exists("reminders.json"):
        with open("reminders.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_reminder_settings(user_id: int, times: list[str]):
    settings = load_reminder_settings()
    settings[str(user_id)] = times 
    with open("reminders.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def get_or_create_user_points(user_id: int) -> list:
    filepath = get_user_points_path(user_id)

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Если индивидуального файла нет — читаем общие пункты из points.json
        with open("points.json", "r", encoding="utf-8") as f:
            default_points = json.load(f)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_points, f, ensure_ascii=False, indent=2)
        return default_points

def get_user_points_path(user_id: int) -> str:
    return os.path.join(DATA_FOLDER, f"{user_id}_points.json")

def save_points(user_id: int, points: list):
    path = get_user_points_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=2)

def get_user_file(user_id: int) -> str:
    directory = "diaries"
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{user_id}.txt")

def save_entry(user_id, entry_text, point_text):
    filepath = get_user_file(user_id)
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        time_period = "🕗 Утро"
    elif hour < 18:
        time_period = "🕛 День"
    else:
        time_period = "🌙 Вечер"
    # ✅ Создание файла при необходимости
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{HIDDEN_MARKER}📓 Мой Дневник 📓\n")
    # 📝 Формирование заголовка и записи
    header = f"\n\n{time_period} — {now.strftime('%Y-%m-%d %H:%M')}\n"
    point_line = f"📍 Пункт: {point_text.strip()}" if point_text.strip() else ""

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(header)
        if point_line:
            f.write(point_line + "\n")
        f.write(entry_text.strip() + "\n")

def clear_user_diary_with_backup(user_id):
    filepath = get_user_file(user_id)
    if os.path.exists(filepath):
        backup_path = f"{filepath}.backup"
        shutil.move(filepath, backup_path)  # создаём бэкап
    # Создаем новый пустой файл (или с заглушкой)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"{HIDDEN_MARKER}📓 Мой Дневник 📓\n")


def delete_last_entry(user_id):
    path = get_user_file(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            # Удаляем последнюю запись (до предыдущего \n\n)
            while lines and lines[-1].strip() == "":
                lines.pop()
            while lines and lines[-1].strip() != "":
                lines.pop()
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)

def get_user_reminders(user_id: int) -> list[str]:
    """
    Возвращает список напоминаний пользователя в формате HH:MM.
    Если напоминаний нет — возвращает пустой список.
    """
    settings = load_reminder_settings()
    return settings.get(str(user_id), [])

def get_all_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return {}
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_data(user_id: int, data: dict):
    filepath = os.path.join(DATA_FOLDER, f"{user_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_timezone(user_id: int) -> str:
    user_data = get_user_data(user_id)
    return user_data.get("timezone", "Asia/Yekaterinburg")

def set_user_timezone(user_id: int, tz: str):
    """
    Сохраняет временную зону пользователя.
    """
    if os.path.exists(TIMEZONE_FILE):
        with open(TIMEZONE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data[str(user_id)] = tz
    with open(TIMEZONE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)