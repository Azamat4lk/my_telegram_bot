from scheduler import restart_reminders_for_user, user_jobs, scheduler # импортируем функцию
from datetime import datetime, timedelta
from aiogram import types, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import (Message, FSInputFile,
Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import config
from config import pending_reminders, bot
from keyboards import (reminder_kb, remove_kb, start_kb, 
fix_kb, get_point_keyboard, points_options_kb, 
reminder_count_kb, get_example_button, examples, 
ReplyKeyboardRemove, examples_menu_kb, 
examples_section_kb, examples_edit_kb, examples as default_examples)
from storage import (save_entry, 
get_user_file, save_reminder_settings, 
clear_user_diary_with_backup, delete_last_entry, save_points, 
load_reminder_settings, get_or_create_user_points,
save_missed_entry, get_user_data, save_user_data, HIDDEN_MARKER)
from functools import wraps
import logging
import os
import re

router = Router()
user_indexes = {} 


QUESTIONS = [
    "➕ Что за неделю было хорошего?",
    "➖ Что за неделю не очень?",
    "📌 Что нужно сделать?"
]

info_text = (
    "🌟 Добро пожаловать в ваш личный Telegram-бот — умный и простой дневник настроения и дел! 🌟\n\n"
    "📝 Что это?\n"
    "Это бот, который помогает вам вести дневник в формате трёх важных пунктов:\n"
    "➕ Плюс — что сегодня было хорошо, что порадовало?\n"
    "➖ Минус — что вызвало трудности или расстроило?\n"
    "🔜 Сделать — какие задачи или планы нужно выполнить завтра?\n\n"
    "💡 Для чего нужен?\n"
    "- Помогает структурировать мысли и чувства каждый день\n"
    "- Позволяет видеть, что важно, а что — повод для улучшений\n"
    "- Напоминает о том, чтобы не забывать о планах и целях\n"
    "- Сохраняет записи, чтобы вы могли вернуться к ним и проанализировать изменения\n\n"
    "⏰ Удобство и автоматизация\n"
    "- Бот сам напомнит, когда пора записать дневник\n"
    "- Всё хранится в одном месте, доступно в любое время\n"
    "- Можно исправить ошибку или изменить запись — никаких проблем!\n\n"
    "🌈 Почему это важно?\n"
    "Ведение дневника помогает лучше понимать себя, повышает продуктивность и улучшает эмоциональное состояние. "
    "А наш бот делает это просто и с удовольствием! 🎉\n\n"
    "📲 Начните уже сегодня и сделайте шаг к осознанной жизни с помощью вашего нового помощника!\n\n"
     "👋 Привет! Этот бот создан 👨‍💻 Сафаровым Азаматом с помощью нейросети 🤖 ChatGPT"
    "[ChatGPT от OpenAI](https://chat.openai.com).\n\n"
    "Ты тоже можешь использовать ChatGPT (приложение есть) для своих задач — заходи и знакомься!"
)

# сохранить выбранный раздел во временном состоянии
SECTION_MAP = {
    "➕ Плюсы": "0",
    "➖ Минусы": "1",
    "✅ Сделано": "2"
}

# FSM-состояния
class ReminderStates(StatesGroup):
    choosing_count = State()
    typing_times = State()
class PointsSettings(StatesGroup):
    choosing_action = State()
    editing_points = State()
    adding_points = State()
class ExampleStates(StatesGroup):
    choosing_action = State()
    choosing_section = State()
    choosing_edit = State()
    adding_example = State()
    replacing_examples = State()

# Хранилище состояния диалога: user_id -> {step: int, answers: list}
user_states = {}

@router.message(F.text == "🔁 Исправить запись")
async def fix_last_entry(message: Message):
    user_id = message.from_user.id
    config.is_waiting_for_entry[user_id] = True
    pending_reminders[user_id] = datetime.now().strftime("%H:%M")
    delete_last_entry(user_id)
    user_states[user_id] = {"step": 0, "answers": [], "mode": "entry"}
    await message.answer("Окей, запись удалена. Давай начнём заново.\n" + QUESTIONS[0], reply_markup=remove_kb)

@router.message(F.text == "✅ Оставить как есть")
async def keep_entry(message: Message):
    user_id = message.from_user.id
    pending_reminders.pop(user_id, None)
    state = user_states.get(user_id)
    if not state or "answers" not in state:
        await message.answer("Нет записей для сохранения.")
        return
    index = user_indexes.get(user_id, 0)
    points = get_or_create_user_points(user_id)
    point_text = points[index % len(points)]
    entry = "\n".join(f"{QUESTIONS[i]} {state['answers'][i]}" for i in range(len(QUESTIONS)))
    save_entry(user_id, entry, point_text)
    user_indexes[user_id] = index + 1  # ✅ увеличиваем здесь
    user_states.pop(user_id)
    config.is_waiting_for_entry[user_id] = False
    await message.answer("📔 Запись сохранена. Спасибо!")
    await message.answer("Отлично, теперь будут следующие напоминания 📌", reply_markup=start_kb)

@router.message(F.text == "📝 Буду записывать")
async def record_entry(message: Message):
    user_id = message.from_user.id
    config.is_waiting_for_entry[user_id] = True
    pending_reminders[user_id] = datetime.now().strftime("%H:%M")
    user_points = get_or_create_user_points(user_id)
    index = user_indexes.get(user_id, 0)
    if not user_points:
        await message.answer("У тебя пока нет пунктов. Добавь их через 📖 Мои пункты.")
        return
    point_number = (index % len(user_points)) + 1
    point_text = user_points[index % len(user_points)]
    user_states[user_id] = {
        "step": 0,
        "answers": [],
        "mode": "entry",
        "point": point_text
    }
    await message.answer(f"<b>🧠 Пункт №{point_number}:</b>\n\n{point_text}")
    await message.answer(QUESTIONS[0], reply_markup=get_example_button("0"))

@router.message(F.text == "🚫 Отказаться от напоминания")
async def refuse(message: Message):
    user_id = message.chat.id
    config.is_waiting_for_entry[user_id] = False
    pending_reminders.pop(user_id, None)
    # Можно также логировать отказ
    save_missed_entry(user_id, "отказ")
    await message.answer("Хорошо, напоминание отменено. 📭", reply_markup=start_kb)

@router.callback_query(F.data.startswith("example:"))
async def send_example_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    question_type = callback.data.split(":")[1]
    user_data = get_user_data(user_id)
    user_examples = user_data.get("examples", {})
    # Сначала пытаемся взять пользовательские примеры
    examples_list = user_examples.get(question_type)
    # Если их нет — берём стандартные
    if not examples_list:
        examples_list = default_examples.get(question_type, [])
    # Если вообще ничего нет
    if not examples_list:
        await callback.message.answer("😔 Примеров пока нет.")
    else:
        section_titles = {"0": "Плюсы", "1": "Минусы", "2": "Сделанное"}
        section = section_titles.get(question_type, "раздел")
        text = f"<b>Примеры для {section}:</b>\n" + "\n".join(f"• {ex}" for ex in examples_list)
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

async def ask_next_point(user_id: int):
    state = user_states.get(user_id)
    if not state:
        return
    answers = state.get("answers", [])
    step = len(answers)
    if step >= len(QUESTIONS):
        # Когда все вопросы пройдены — показать итоговую запись
        preview = "\n".join(f"{QUESTIONS[i]} {answers[i]}" for i in range(len(QUESTIONS)))
        await bot.send_message(
            user_id,
            f"📋 Вот ваша запись:\n\n{preview}\n\nВы хотите сохранить запись или исправить?",
            reply_markup=fix_kb
        )
        return
    # Следующий вопрос
    question = QUESTIONS[step]
    markup = get_example_button(str(step))  # ✅ Показываем кнопку всегда
    await bot.send_message(user_id, question, reply_markup=markup)

"""
def block_during_entry(handler):
    @wraps(handler)
    async def wrapper(message: Message, *args, **kwargs):
        user_id = message.from_user.id
        if config.is_waiting_for_entry.get(user_id):
            logging.info(f"[BLOCKED] Пользователь {user_id} попытался вызвать команду во время записи.")
            await message.answer("⛔ Эта команда недоступна во время записи дневника.")
            return
        logging.info(f"[ALLOWED] Пользователь {user_id} использует команду.")
        return await handler(message, *args, **kwargs)
    return wrapper
"""

# 
# 
@router.message(F.text == "🧠 Примеры")
#@block_during_entry
async def examples_menu(msg: types.Message, state: FSMContext):
    await msg.answer("✏ Что вы хотите сделать с примерами?", reply_markup=examples_menu_kb)
    await state.set_state(ExampleStates.choosing_action)

@router.message(F.text == "📋 Мои примеры")
#@block_during_entry
async def show_user_examples(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    user_data = get_user_data(user_id)
    # Пытаемся взять примеры пользователя
    user_examples = user_data.get("examples", {})
    # Объединяем: если у пользователя чего-то нет — берём из глобальных
    result = ""
    for section, label in [("0", "➕ Плюсы"), ("1", "➖ Минусы"), ("2", "✅ Сделано")]:
        examples_list = user_examples.get(section)
        if examples_list is None:
            examples_list = default_examples.get(section, [])
        if examples_list:
            result += f"<b>{label}:</b>\n" + "\n".join(f"• {ex}" for ex in examples_list) + "\n\n"
    if not result:
        result = "😔 У вас пока нет примеров."
    await msg.answer(result.strip(), reply_markup=examples_menu_kb, parse_mode="HTML")

@router.message(ExampleStates.choosing_action, F.text == "✏ Изменить примеры")
#@block_during_entry
async def choose_section_to_edit(msg: types.Message, state: FSMContext):
    await msg.answer("Выберите, к какому разделу хотите изменить примеры:", reply_markup=examples_section_kb)
    await state.set_state(ExampleStates.choosing_section)

@router.message(ExampleStates.choosing_section, F.text.in_(SECTION_MAP.keys()))
#@block_during_entry
async def choose_edit_action(msg: types.Message, state: FSMContext):
    await state.update_data(section=SECTION_MAP[msg.text])
    await msg.answer(f"Что вы хотите сделать с примерами для раздела {msg.text}?", reply_markup=examples_edit_kb)
    await state.set_state(ExampleStates.choosing_edit)

@router.message(ExampleStates.choosing_edit, F.text == "➕ Добавить пример")
#@block_during_entry
async def start_adding_example(msg: types.Message, state: FSMContext):
    await msg.answer("✍ Напишите новый пример для добавления:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ExampleStates.adding_example)

@router.message(ExampleStates.adding_example)
#@block_during_entry
async def save_added_example(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    user_data = get_user_data(user_id)
    data = await state.get_data()
    section = data.get("section")
    example = msg.text.strip()
    if not example:
        await msg.answer("⚠ Пример не может быть пустым.")
        return
    # Достаём или создаём список примеров
    if "examples" not in user_data:
        user_data["examples"] = {}
    if section not in user_data["examples"]:
        user_data["examples"][section] = []
    # Добавляем, если такого примера ещё нет
    if example not in user_data["examples"][section]:
        user_data["examples"][section].append(example)

    # Сохраняем
    save_user_data(user_id, user_data)
    # Показываем
    result = "\n".join(f"• {ex}" for ex in user_data["examples"][section])
    await msg.answer(
        f"✅ Пример успешно добавлен!\n📋 Обновлённый список:\n{result}",
        reply_markup=examples_menu_kb
    )
    await state.set_state(ExampleStates.choosing_action)

@router.message(ExampleStates.choosing_edit, F.text == "♻ Заменить примеры")
#@block_during_entry
async def start_replacing_examples(msg: types.Message, state: FSMContext):
    await msg.answer(
        "🗑 Все старые примеры будут удалены.\n"
        "✍ Отправьте все новые примеры *по одному сообщению*. Когда закончите, напишите Готово.", reply_markup=ReplyKeyboardRemove())
    await state.update_data(new_examples=[])
    await state.set_state(ExampleStates.replacing_examples)

@router.message(ExampleStates.replacing_examples, F.text.casefold() == "готово")
#@block_during_entry
async def finish_replacing(msg: types.Message, state: FSMContext):
    user_data = get_user_data(msg.from_user.id)
    data = await state.get_data()
    section = data.get("section")
    new_examples = data.get("new_examples", [])
    if new_examples:
        user_data.setdefault("examples", {})[section] = new_examples
        save_user_data(msg.from_user.id, user_data)
        result = "\n".join(f"• {ex}" for ex in new_examples)
        await msg.answer(f"✅ Примеры успешно обновлены!\n📋 Новый список:\n{result}", reply_markup=examples_menu_kb)
    else:
        await msg.answer("⚠ Вы не отправили ни одного нового примера. Старые остались без изменений.", reply_markup=examples_menu_kb)
    await state.set_state(ExampleStates.choosing_action)

@router.message(ExampleStates.replacing_examples)
#@block_during_entry
async def collect_example(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    if not text:
        await msg.answer("⚠ Пример не может быть пустым.")
        return

    data = await state.get_data()
    new_examples = data.get("new_examples", [])
    new_examples.append(text)
    await state.update_data(new_examples=new_examples)

@router.message(F.text == "🔙 Назад")
#@block_during_entry
async def go_back(msg: types.Message, state: FSMContext):
    await state.clear()
    await examples_menu(msg, state)
# 
# 
# 

@router.message(F.text == "🔙 Вернуться в меню")
#@block_during_entry
async def back_from_count(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в главное меню 👇", reply_markup=start_kb)

@router.message(F.text == "⚙ Изменить напоминания")
#@block_during_entry
async def start_reminder_change(message: Message, state: FSMContext):
    await message.answer("Сколько раз в день вы хотите получать напоминания?", reply_markup=reminder_count_kb)
    await state.set_state(ReminderStates.choosing_count)

@router.message(ReminderStates.choosing_count, F.text == "🔕 Выключить напоминания")
#@block_during_entry
async def turn_off_reminders(message: Message, state: FSMContext):
    user_id = message.from_user.id
    jobs = user_jobs.get(user_id, [])
    for job in jobs:
        scheduler.remove_job(job.id)
    user_jobs[user_id] = []
    save_reminder_settings(user_id, [])
    await message.answer("🔕 Все напоминания отключены. Вы всегда можете включить их снова через '⏰ Изменить напоминания'.", reply_markup=start_kb)
    await state.clear()


@router.message(ReminderStates.choosing_count)
#@block_during_entry
async def get_reminder_count(message: Message, state: FSMContext):
    match = re.match(r"(\d+) раз", message.text)
    if not match:
        await message.answer("Пожалуйста, выберите из предложенных вариантов.", reply_markup=reminder_count_kb)
        return
    count = int(match.group(1))
    await state.update_data(count=count)
    await state.set_state(ReminderStates.typing_times)
    await message.answer(f"Введите {count} времени в формате 08:00, 14:00, 20:00:")

@router.message(ReminderStates.typing_times)
#@block_during_entry
async def get_reminder_times(message: Message, state: FSMContext):
    data = await state.get_data()
    count = data.get("count")
    times = [t.strip() for t in message.text.split(",") if t.strip()]
    time_pattern = re.compile(r"^(2[0-3]|[01]?[0-9]):[0-5][0-9]$")
    # 🔁 Проверка на количество
    if len(times) != count:
        await message.answer(f"Вы выбрали {count} раз в день. Пожалуйста, введите ровно {count} времени.")
        return
    # 🕒 Проверка формата
    if not all(time_pattern.match(t) for t in times):
        await message.answer("Неверный формат. Пример: 08:00, 14:30, 20:00")
        return
    # 🚫 Проверка на дубликаты
    if len(set(times)) != len(times):
        await message.answer("⚠ Нельзя вводить одинаковые времена. Попробуйте снова.")
        return
    # ✅ Всё в порядке — сохраняем и запускаем напоминания
    user_id = message.from_user.id
    # 🧹 Очистка старого ожидания, если было
    if config.is_waiting_for_entry.get(user_id, False):
        config.is_waiting_for_entry[user_id] = False
        pending_reminders.pop(user_id, None)
    # Сохраняем новые настройки
    save_reminder_settings(user_id, times)
    restart_reminders_for_user(user_id, times)
    await message.answer(f"Хорошо! Напоминания будут в: {', '.join(times)}", reply_markup=start_kb)
    await state.clear()

@router.message(F.text == "🕒 Мои напоминания")
#@block_during_entry
async def show_my_reminders(message: Message):
    user_id = str(message.from_user.id)
    settings = load_reminder_settings()
    times = settings.get(user_id, [])
    if not times:
        await message.answer("❗У вас пока нет активных напоминаний.")
    else:
        formatted = '\n'.join([f"🔹 {t}" for t in times])
        await message.answer(f"📅 Ваши текущие напоминания:\n{formatted}")
        
@router.message(F.text == "📖 Мои пункты")
#@block_during_entry
async def show_points(message: Message):
    user_id = message.from_user.id
    user_points = get_or_create_user_points(user_id)
    if not user_points:
        await message.answer("Пункты пока не заданы.")
        return
    text = "<b>📖 Твои текущие пункты:</b>\n\n" + "\n".join(user_points)
    await message.answer(text)


@router.message(F.text == "📄 Отправить дневник")
#@block_during_entry
async def send_diary_file(message: Message):
    user_id = message.from_user.id
    file_path = get_user_file(user_id)
    if not os.path.exists(file_path):
        await message.answer("У вас ещё нет записей.")
        return
    diary_file = FSInputFile(file_path)
    await message.answer_document(document=diary_file, caption="Вот ваш дневник 📔")


@router.message(F.text == "🧩 Изменить пункты предложений")
#@block_during_entry
async def change_points(message: Message, state: FSMContext):
    await state.set_state(PointsSettings.choosing_action)
    await message.answer(
        "Что вы хотите сделать с пунктами?",
        reply_markup=points_options_kb
    )

@router.message(PointsSettings.choosing_action)
#@block_during_entry
async def process_points_action(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "✏ Изменить все пункты":
        await state.set_state(PointsSettings.editing_points)
        await message.answer(
            "Отправьте новые пункты, каждый с новой строки:\n\n"
            "<code>1. Первый пункт\n2. Второй пункт\n3. ...</code>",
            reply_markup=remove_kb
        )
    elif text == "➕ Добавить новые пункты":
        await state.set_state(PointsSettings.adding_points)
        await message.answer(
            "Отправьте новые пункты, каждый с новой строки, я добавлю их в конец.",
            reply_markup=remove_kb
        )
    elif text == "🔙 Вернуться в меню":
        await message.answer("Вы вернулись в главное меню 👇", reply_markup=start_kb)
        await state.clear()
    else:
        await message.answer("Пожалуйста, выберите вариант с кнопки.")

@router.message(F.text == "ℹ О боте")
#@block_during_entry
async def shpw_about_info(message: Message):
    await message.answer(info_text)

@router.message(PointsSettings.editing_points)
#@block_during_entry
async def save_new_points(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    new_points = [line.strip() for line in text.splitlines() if line.strip()]
    if not new_points:
        await message.answer("Пункты не распознаны. Отправьте хотя бы один пункт.")
        return
    save_points(user_id, new_points)
    await message.answer(
        f"✅ Пункты успешно заменены.\nВсего: {len(new_points)}",
        reply_markup=start_kb
    )
    await state.clear()

@router.message(PointsSettings.adding_points)
#@block_during_entry
async def add_more_points(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    new_points = [line.strip() for line in text.splitlines() if line.strip()]
    if not new_points:
        await message.answer("Пункты не распознаны. Отправьте хотя бы один пункт.")
        return
    existing_points = get_or_create_user_points(user_id)
    new_points = existing_points + new_points
    save_points(user_id, new_points)
    await message.answer(f"✅ Добавлено: {len(new_points)} пункт(ов).\nВсего теперь: {len(new_points)}", reply_markup=start_kb)
    await state.clear()

@router.message(lambda message: config.is_waiting_for_entry.get(message.from_user.id, False))
async def process_message(message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state:
        await message.answer("Пожалуйста, выбирайте кнопки 🔽")
        return
    step = state.get('step', 0)
    answers = state.get('answers', [])
    answers.append(message.text)
    state['answers'] = answers
    state['step'] = step + 1  # ✅ здесь увеличиваем шаг
    await ask_next_point(user_id)

@router.message(Command("start"))
#@block_during_entry
async def cmd_start(message: Message):
    user_id = message.from_user.id
    get_or_create_user_points(user_id)
    await message.answer(
        f"👋 Привет, {message.chat.first_name}! Я твой бот-дневник.\n\n"
        "Каждый день я буду напоминать тебе 3 раза:\n"
        "➕ Что хорошего произошло\n"
        "➖ Что было не так\n"
        "📌 Что ты хочешь сделать\n\n"
        "🔽 Выбери, что хочешь сделать:",
        reply_markup=start_kb
    )
    await message.answer(
    "💡 Команды:\n"
    "/help - Посмотр команды бота\n"
    "/clear — Очистить дневник\n"
    "Или используй кнопки ниже 👇"
)

@router.message(Command("help"))
#@block_during_entry
async def help_command(message: Message):
    await message.answer(
        "📋 <b>Доступные команды</b>:\n"
        "/start — начать заново\n"
        "/clear — очистить дневник\n"
        "/search — поиск редактирование записей дневника\n\n"
        "Также доступны кнопки:\n"
        "📝 Буду записывать — начать запись\n"
        "🔁 Исправить запись — удалить и переписать последнюю\n"
        "⚙ Изменить напоминания — настроить время и частоту\n"
        "🧩 Изменить пункты — изменить или добавить правила\n"
        "ℹ О боте — подробнее о работе\n", 
        reply_markup=start_kb
    )

@router.message(Command("clear"))
#@block_during_entry
async def clear_diary(message: Message):
    user_id = message.chat.id
    clear_user_diary_with_backup(user_id)
    filepath = get_user_file(user_id)
    document = FSInputFile(filepath)
    await message.answer_document(document=document, reply_markup=start_kb, caption="🧹 Ваш дневник очищен. Новый файл создан.")

# edit_diary.py
DIARY_FOLDER = "diaries"

QUESTIONS = [
    "➕ Что за неделю было хорошего?",
    "➖ Что за неделю не очень?",
    "📌 Что нужно сделать?"
]

if not os.path.exists(DIARY_FOLDER):
    os.makedirs(DIARY_FOLDER)

class EditDiaryStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_record_number = State()
    waiting_for_edit_choice = State()
    waiting_for_new_text = State()
    waiting_for_continue_or_finish = State()

def get_user_file(user_id: int) -> str:
    return os.path.join(DIARY_FOLDER, f"{user_id}.txt")

def load_diary(user_id: int) -> list[str]:
    filepath = get_user_file(user_id)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        entries = [e.strip() for e in content.strip().split("\n\n") if e.strip()]
        if entries and entries[0].startswith("Мой дневник"):
            entries.pop(0)
        return entries

def save_diary(user_id: int, records: list[str]):
    filename = get_user_file(user_id)
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n\n".join(records))

@router.message(Command("cancel"), StateFilter("*"))
#@block_during_entry
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=start_kb)

@router.message(EditDiaryStates.waiting_for_search_query)
#@block_during_entry
async def process_search_query(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    query = message.text.strip().lower()
    diary = load_diary(user_id)
    if not diary:
        await message.answer("📭 Ваш дневник пока пуст.")
        await state.clear()
        return
    skip_words = [f"{HIDDEN_MARKER}пропуск"]
    filtered_entries = []
    for idx, entry in enumerate(diary):
        entry_lower = entry.lower()
        if any(word in entry_lower for word in skip_words):
            continue
        if f"{HIDDEN_MARKER}📓 мой дневник 📓" in entry_lower:
            continue  # ❌ Пропускаем такие записи
        if query in entry_lower:
            filtered_entries.append((idx, entry))
    if not filtered_entries:
        await message.answer("❌ Не найдено записей по вашему запросу.")
        return
    await state.update_data(found_records=filtered_entries)
    text = "✅ Найдено записей:\n\n"
    for i, (_, record) in enumerate(filtered_entries, start=1):
        lines = record.strip().splitlines()
        points = [line for line in lines if line.startswith("📍")]
        header = lines[0] if lines else "..."
        plus = next((line for line in lines if line.startswith("➕")), "")
        minus = next((line for line in lines if line.startswith("➖")), "")
        todo = next((line for line in lines if line.startswith("📌")), "")
        parts = [header]
        parts.extend(points)
        parts.extend([plus, minus, todo])
        text += f"Номер: {i}\n" + "\n".join([p for p in parts if p]) + "\n\n"
    await message.answer(text.strip())
    await message.answer("Введите номер записи, которую хотите изменить:")
    await state.set_state(EditDiaryStates.waiting_for_record_number)

@router.message(EditDiaryStates.waiting_for_record_number)
#@block_during_entry
async def process_record_number(message: Message, state: FSMContext):
    data = await state.get_data()
    found = data.get("found_records", [])
    try:
        num = int(message.text.strip())
        if not (1 <= num <= len(found)):
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите корректный номер из списка\nЗавершить - /cancel.")
        return
    selected_idx, selected_record = found[num - 1]
    await state.update_data(selected_idx=selected_idx)
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Плюс", callback_data="edit_plus")],
        [InlineKeyboardButton(text="➖ Минус", callback_data="edit_minus")],
        [InlineKeyboardButton(text="📌 Сделать", callback_data="edit_todo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")]
    ])
    await message.answer(f"📝 Выбрана запись:\n\n{selected_record}\n\nЧто вы хотите изменить?", reply_markup=buttons)
    await state.set_state(EditDiaryStates.waiting_for_edit_choice)

@router.callback_query(F.data.in_({"edit_plus", "edit_minus", "edit_todo", "edit_cancel"}))
#@block_during_entry
async def process_edit_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    if choice == "edit_cancel":
        await callback.message.answer("❌ Редактирование отменено.", reply_markup=start_kb)
        await state.clear()
        await callback.answer()
        return
    part_map = {
        "edit_plus": ("➕", 1),
        "edit_minus": ("➖", 2),
        "edit_todo": ("📌", 3)
    }
    symbol, line_idx = part_map.get(choice, (None, None))
    if symbol is None:
        await callback.answer("🚫 Неизвестный выбор.")
        return
    await state.update_data(edit_symbol=symbol, line_idx=line_idx)
    await callback.message.answer(f"✏ Введите новый текст для пункта {symbol}:")
    await state.set_state(EditDiaryStates.waiting_for_new_text)
    await callback.answer()

@router.message(EditDiaryStates.waiting_for_new_text)
#@block_during_entry
async def process_new_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    selected_idx = data.get("selected_idx")
    edit_symbol = data.get("edit_symbol")
    new_text = message.text.strip()
    if selected_idx is None or edit_symbol is None:
        await message.answer("⚠ Ошибка состояния. Попробуйте сначала.\nЗавершить - /cancel")
        await state.clear()
        return
    if not new_text:
        await message.answer("❗ Текст не может быть пустым. Введите новый текст:\nЗавершить - /cancel")
        return
    diary = load_diary(user_id)
    if selected_idx >= len(diary):
        await message.answer("⚠ Запись не найдена. Попробуйте сначала.\nЗавершить - /cancel")
        await state.clear()
        return
    lines = diary[selected_idx].splitlines()
    prefix_map = {
        "➕": "➕",
        "➖": "➖",
        "📌": "📌"
    }
    prefix = prefix_map.get(edit_symbol)
    if not prefix:
        await message.answer("⚠ Не удалось определить, что нужно изменить.\nЗавершить - /cancel")
        await state.clear()
        return
    # Заменяем строку с нужным символом
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix} {new_text}"
            updated = True
            break
    if not updated:
        await message.answer("⚠ Не удалось найти нужный элемент для редактирования.\nЗавершить - /cancel")
        await state.clear()
        return
    diary[selected_idx] = "\n".join(lines)
    save_diary(user_id, diary)
    await message.answer(f"✅ Запись обновлена:\n\n{diary[selected_idx]}")
        # Предлагаем продолжить редактирование или завершить
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏ Продолжить редактирование", callback_data="edit_continue")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data="edit_finish")]
    ])
    await message.answer("Хотите отредактировать ещё что-нибудь в этой записи?", reply_markup=buttons)
    await state.set_state(EditDiaryStates.waiting_for_continue_or_finish)

#@block_during_entry
@router.callback_query(EditDiaryStates.waiting_for_continue_or_finish, F.data.in_({"edit_continue", "edit_finish"}))
async def process_continue_or_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data == "edit_continue":
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Плюс", callback_data="edit_plus")],
            [InlineKeyboardButton(text="➖ Минус", callback_data="edit_minus")],
            [InlineKeyboardButton(text="📌 Сделать", callback_data="edit_todo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")]
        ])
        await callback.message.answer("Что хотите изменить?", reply_markup=buttons)
        await state.set_state(EditDiaryStates.waiting_for_edit_choice)
    else:
        await callback.message.answer("✅ Редактирование завершено. Можете снова использовать /search или другие команды.", reply_markup=start_kb)
        await state.clear()

async def ask_next_point(user_id: int):
    state = user_states.get(user_id)
    if not state:
        return
    answers = state.get("answers", [])
    step = len(answers)
    if step >= len(QUESTIONS):
        # Когда все вопросы пройдены — показать итоговую запись
        preview = "\n".join(f"{QUESTIONS[i]} {answers[i]}" for i in range(len(QUESTIONS)))
        await bot.send_message(
            user_id,
            f"📋 Вот ваша запись:\n\n{preview}\n\nВы хотите сохранить запись или исправить?",
            reply_markup=fix_kb
        )
        return
    # Следующий вопрос
    question = QUESTIONS[step]
    markup = get_example_button(str(step))  # ✅ Показываем кнопку всегда
    await bot.send_message(user_id, question, reply_markup=markup)

@router.message(Command("search"))
#@block_during_entry
async def cmd_search_start(message: Message, state: FSMContext):
    await message.answer("🔎 Введите дату (например, 2025-07-24) или ключевое слово для поиска \nЗавершить - /cancel:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditDiaryStates.waiting_for_search_query)

@router.message()
async def catch_unexpected_text(message: Message):
    user_id = message.from_user.id
    # Если не в режиме записи дневника
    if not config.is_waiting_for_entry.get(user_id, False):
        # Игнорируем команды, чтобы они работали нормально
        if message.text.startswith("/start") or message.text.startswith("/clear") or message.text.startswith("/help") or message.text.startswith("/serach") or message.text.startswith("/cancel"):
            return
        # Отправляем предупреждение
        await message.answer("⚠ Пожалуйста, используйте кнопки меню или напишите /start для начала.")