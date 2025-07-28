from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

examples = {
    "0": ["🌞 Сегодня я гулял и наслаждался погодой.", "📚 Прочитал интересную статью."],
    "1": ["😞 Опоздал на встречу.", "💤 Чувствовал себя уставшим весь день."],
    "2": ["📌 Закончить отчёт.", "🧹 Убраться в комнате."]
}

def get_point_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text = p)] for p in points],
        resize_keyboard=True
    )

def get_example_button(q_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Пример", callback_data=f"example:{q_type}")]
        ]
    )

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Главное меню примеров
examples_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Мои примеры")],
        [KeyboardButton(text="✏ Изменить примеры")],
        [KeyboardButton(text="🔙 Вернуться в меню")],
    ],
    resize_keyboard=True
)

# Выбор раздела
examples_section_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Плюсы"), KeyboardButton(text="➖ Минусы")],
        [KeyboardButton(text="✅ Сделано")],
        [KeyboardButton(text="🔙 Назад")],
    ],
    resize_keyboard=True
)

# Редактирование конкретного раздела
examples_edit_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить пример")],
        [KeyboardButton(text="♻ Заменить примеры")],
        [KeyboardButton(text="🔙 Назад")],
    ],
    resize_keyboard=True
)

# Кнопки выбора количества напоминаний
reminder_count_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔕 Выключить напоминания")],
        [KeyboardButton(text="1 раз в день")],
        [KeyboardButton(text="2 раза в день")],
        [KeyboardButton(text="3 раза в день")],
        [KeyboardButton(text="4 раза в день")],
        [KeyboardButton(text="5 раз в день")],
        [KeyboardButton(text="6 раз в день")],
        [KeyboardButton(text="7 раз в день")],
        [KeyboardButton(text="8 раз в день")],
        [KeyboardButton(text="🔙 Вернуться в меню")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

points_options_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✏ Изменить все пункты")],
        [KeyboardButton(text="➕ Добавить новые пункты")],
        [KeyboardButton(text="🔙 Вернуться в меню")],
    ],
    resize_keyboard=True
)

start_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📄 Отправить дневник")],
        [KeyboardButton(text="ℹ О боте")],
        [KeyboardButton(text="⚙ Изменить напоминания")],
        [KeyboardButton(text="🕒 Мои напоминания")] ,
        [KeyboardButton(text="🧩 Изменить пункты предложений")],
        [KeyboardButton(text="📖 Мои пункты")],
        [KeyboardButton(text="🧠 Примеры")],
        [KeyboardButton(text="📍 Местоположение")]
    ],
    resize_keyboard=True
)

reminder_kb = lambda show_examples=False: ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Буду записывать")],
        [KeyboardButton(text="🚫 Отказаться от напоминания")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

fix_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔁 Исправить запись")],
        [KeyboardButton(text="✅ Оставить как есть")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

location_request_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="❌ Не отправлять")],
        [KeyboardButton(text="🔙 Вернуться в меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

location_choice_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="❌ Не отправлять")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

remove_kb = ReplyKeyboardRemove()