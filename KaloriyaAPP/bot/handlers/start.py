from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from datetime import date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import get_settings
from database.connection import async_session
from database.crud import (
    get_user_by_telegram_id,
    create_user,
    get_or_create_daily_stats,
    get_user_food_entries_by_date
)
from bot.keyboards.inline import get_main_menu_keyboard, get_webapp_button

router = Router()
settings = get_settings()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)

        if not user:
            # Новый пользователь
            user = await create_user(
                db,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )

        if not user.is_registered:
            # Пользователь не завершил регистрацию
            welcome_text = (
                f"👋 Привет, {message.from_user.first_name or 'друг'}!\n\n"
                "Я — **KaloriyaBot** 🍎\n"
                "Твой персональный помощник в подсчёте калорий!\n\n"
                "📸 Просто сфотографируй еду — и я определю калории\n"
                "📊 Отслеживай прогресс и достигай целей\n"
                "🎯 Помогу похудеть или набрать массу\n\n"
                "Для начала заполни свой профиль 👇"
            )

            keyboard = get_webapp_button(
                "📝 Заполнить профиль",
                settings.WEBAPP_URL,
                "/profile/setup"
            )

            await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Зарегистрированный пользователь
            await show_main_menu(message, user)


async def show_main_menu(message: Message, user):
    """Показать главное меню с дневной статистикой"""
    async with async_session() as db:
        stats = await get_or_create_daily_stats(db, user.id, date.today())
        entries = await get_user_food_entries_by_date(db, user.id, date.today())

    # Расчёт прогресса
    cal_percent = min(100, int((stats.total_calories / user.daily_calories) * 100)) if user.daily_calories else 0
    cal_bar = create_progress_bar(cal_percent)

    remaining_cal = max(0, user.daily_calories - stats.total_calories) if user.daily_calories else 0

    menu_text = (
        f"🍽 **Сегодня** ({date.today().strftime('%d.%m.%Y')})\n\n"
        f"🔥 Калории: {stats.total_calories} / {user.daily_calories} ккал\n"
        f"{cal_bar} {cal_percent}%\n\n"
        f"🥩 Белки: {stats.total_protein:.0f}г / {user.daily_protein}г\n"
        f"🍞 Углеводы: {stats.total_carbs:.0f}г / {user.daily_carbs}г\n"
        f"🧈 Жиры: {stats.total_fat:.0f}г / {user.daily_fat}г\n\n"
        f"💧 Вода: {stats.water_ml} мл\n\n"
    )

    if remaining_cal > 0:
        menu_text += f"📍 Осталось: **{remaining_cal} ккал**\n\n"
    else:
        menu_text += "✅ Дневная норма выполнена!\n\n"

    menu_text += f"📝 Записей сегодня: {len(entries)}"

    await message.answer(
        menu_text,
        reply_markup=get_main_menu_keyboard(settings.WEBAPP_URL),
        parse_mode="Markdown"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню"""
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)
        if user and user.is_registered:
            await show_main_menu(message, user)
        else:
            await cmd_start(message)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам"""
    help_text = (
        "📚 **Как пользоваться ботом:**\n\n"
        "1️⃣ **Добавить еду** — сфотографируй или отправь фото еды\n"
        "2️⃣ **Дневник** — посмотри все записи за день\n"
        "3️⃣ **Статистика** — графики за неделю/месяц\n"
        "4️⃣ **Профиль** — настрой свои данные и цели\n\n"
        "📸 Можешь просто отправить фото еды прямо сюда!\n\n"
        "**Команды:**\n"
        "/start — начать\n"
        "/menu — главное меню\n"
        "/profile — мой профиль\n"
        "/stats — статистика\n"
        "/help — эта справка"
    )
    await message.answer(help_text, parse_mode="Markdown")


def create_progress_bar(percent: int, length: int = 10) -> str:
    """Создать текстовый прогресс-бар"""
    filled = int(length * percent / 100)
    empty = length - filled
    return "▓" * filled + "░" * empty
