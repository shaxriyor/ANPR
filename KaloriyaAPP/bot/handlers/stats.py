from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import date, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import get_settings
from database.connection import async_session
from database.crud import (
    get_user_by_telegram_id,
    get_weekly_stats,
    log_water,
    get_or_create_daily_stats
)
from bot.keyboards.inline import get_webapp_button, get_water_keyboard

router = Router()
settings = get_settings()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Показать краткую статистику за неделю"""
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)

        if not user or not user.is_registered:
            await message.answer("❗ Сначала заполни профиль! Нажми /start")
            return

        weekly = await get_weekly_stats(db, user.id)

    if not weekly:
        await message.answer(
            "📊 У тебя пока нет записей.\n"
            "Добавь первый приём пищи!",
            reply_markup=get_webapp_button(
                "📸 Добавить еду",
                settings.WEBAPP_URL,
                "/camera"
            )
        )
        return

    # Считаем средние значения
    total_days = len(weekly)
    avg_calories = sum(s.total_calories for s in weekly) / total_days
    avg_protein = sum(s.total_protein for s in weekly) / total_days
    avg_carbs = sum(s.total_carbs for s in weekly) / total_days
    avg_fat = sum(s.total_fat for s in weekly) / total_days

    # Прогресс за неделю (текстовый график)
    cal_chart = create_week_chart(weekly, user.daily_calories)

    stats_text = (
        f"📊 **Статистика за неделю**\n\n"
        f"📅 Дней с записями: {total_days}\n\n"
        f"**Среднее в день:**\n"
        f"🔥 Калории: {avg_calories:.0f} / {user.daily_calories} ккал\n"
        f"🥩 Белки: {avg_protein:.0f}г\n"
        f"🍞 Углеводы: {avg_carbs:.0f}г\n"
        f"🧈 Жиры: {avg_fat:.0f}г\n\n"
        f"**Калории по дням:**\n"
        f"{cal_chart}\n\n"
        "👇 Подробнее в Web App"
    )

    await message.answer(
        stats_text,
        reply_markup=get_webapp_button(
            "📈 Подробная статистика",
            settings.WEBAPP_URL,
            "/stats"
        ),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "add_water")
async def handle_add_water(callback: CallbackQuery):
    """Показать кнопки добавления воды"""
    await callback.message.answer(
        "💧 Сколько воды выпил?",
        reply_markup=get_water_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("water_"))
async def handle_water_amount(callback: CallbackQuery):
    """Добавить воду"""
    ml = int(callback.data.replace("water_", ""))

    async with async_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        stats = await log_water(db, user.id, ml)

    await callback.message.edit_text(
        f"💧 Добавлено {ml} мл воды!\n"
        f"📊 Всего сегодня: {stats.water_ml} мл"
    )
    await callback.answer("💧 Добавлено!")


def create_week_chart(stats: list, target: int) -> str:
    """Создать текстовый график калорий за неделю"""
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    today = date.today()

    # Создаём словарь по датам
    stats_dict = {s.stats_date: s.total_calories for s in stats}

    lines = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_name = days[day.weekday()]
        calories = stats_dict.get(day, 0)

        # Прогресс-бар (максимум 8 символов)
        if target > 0:
            percent = min(100, int((calories / target) * 100))
            filled = int(8 * percent / 100)
        else:
            filled = 0

        bar = "▓" * filled + "░" * (8 - filled)
        lines.append(f"`{day_name}` {bar} {calories}")

    return "\n".join(lines)


def get_water_keyboard():
    """Импортируем из keyboards"""
    from bot.keyboards.inline import get_water_keyboard as _get_water_keyboard
    return _get_water_keyboard()
