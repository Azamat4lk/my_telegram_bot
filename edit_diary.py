import os
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards import start_kb, ReplyKeyboardRemove, fix_kb, remove_kb
from handlers import (block_during_entry, pending_reminders, 
user_states, user_indexes, get_example_button)
from storage import (save_entry, get_or_create_user_points,
save_missed_entry, delete_last_entry)
from datetime import datetime
from config import bot
import config

router = Router()

DIARY_FOLDER = "diaries"

QUESTIONS = [
    "➕ Что за неделю было хорошего?",
    "➖ Что за неделю не очень?",
    "📌 Что нужно сделать?"
]

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
    await message.answer("Отлично, теперь будут следующие напоминания 📌")
    await message.answer("🔎 Введите дату (например, 2025-07-24) или ключевое слово для поиска \nЗавершить - /cancel:", reply_markup=start_kb)

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
    await message.answer("Хорошо, напоминание отменено. 📭")
    await message.answer("🔎 Введите дату (например, 2025-07-24) или ключевое слово для поиска \nЗавершить - /cancel:", reply_markup=start_kb)

@router.message(lambda message: config.is_waiting_for_entry.get(message.from_user.id, False))
async def process_message(message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state:
        await message.answer("Пожалуйста, напишите /start, чтобы начать.")
        return
    step = state.get('step', 0)
    answers = state.get('answers', [])
    answers.append(message.text)
    state['answers'] = answers
    state['step'] = step + 1  # ✅ здесь увеличиваем шаг
    await ask_next_point(user_id)

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
@block_during_entry
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=start_kb)

@router.message(EditDiaryStates.waiting_for_search_query)
@block_during_entry
async def process_search_query(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    query = message.text.strip().lower()
    diary = load_diary(user_id)
    if not diary:
        await message.answer("📭 Ваш дневник пока пуст.")
        await state.clear()
        return
    skip_words = ["пропуск", "пропущено", "отложено", "отложить"]
    filtered_entries = []
    for idx, entry in enumerate(diary):
        entry_lower = entry.lower()
        if any(word in entry_lower for word in skip_words):
            continue
        if "📓 мой дневник 📓" in entry_lower:
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
        text += f"{i})\n" + "\n".join([p for p in parts if p]) + "\n\n"
    await message.answer(text.strip())
    await message.answer("Введите номер записи, которую хотите изменить:")
    await state.set_state(EditDiaryStates.waiting_for_record_number)

@router.message(EditDiaryStates.waiting_for_record_number)
@block_during_entry
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
@block_during_entry
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
@block_during_entry
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

@block_during_entry
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
@block_during_entry
async def cmd_search_start(message: Message, state: FSMContext):
    await message.answer("🔎 Введите дату (например, 2025-07-24) или ключевое слово для поиска \nЗавершить - /cancel:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditDiaryStates.waiting_for_search_query)