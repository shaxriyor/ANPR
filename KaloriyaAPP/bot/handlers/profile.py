from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import get_settings
from database.connection import async_session
from database.crud import get_user_by_telegram_id
from bot.keyboards.inline import get_webapp_button

router = Router()
settings = get_settings()


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Показать профиль пользователя"""
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)

        if not user or not user.is_registered:
            await message.answer(
                "❗ Профиль не заполнен!\n"
                "Нажми кнопку ниже чтобы настроить свой профиль.",
                reply_markup=get_webapp_button(
                    "📝 Заполнить профиль",
                    settings.WEBAPP_URL,
                    "/profile/setup"
                )
            )
            return

        # Формируем текст профиля
        goal_names = {
            "lose": "🏃 Похудение",
            "maintain": "⚖️ Поддержание веса",
            "gain": "💪 Набор массы"
        }

        activity_names = {
            "sedentary": "🪑 Сидячий",
            "light": "🚶 Лёгкая активность",
            "moderate": "🏃 Умеренная активность",
            "active": "🏋️ Высокая активность",
            "very_active": "⚡ Очень высокая активность"
        }

        gender_names = {
            "male": "👨 Мужской",
            "female": "👩 Женский"
        }

        profile_text = (
            f"👤 **Мой профиль**\n\n"
            f"📊 **Физические данные:**\n"
            f"• Вес: {user.weight} кг\n"
            f"• Рост: {user.height} см\n"
            f"• Возраст: {user.age} лет\n"
            f"• Пол: {gender_names.get(user.gender.value, user.gender.value)}\n\n"
            f"🎯 **Цель:** {goal_names.get(user.goal.value, user.goal.value)}\n"
            f"🏃 **Активность:** {activity_names.get(user.activity_level.value, user.activity_level.value)}\n"
        )

        if user.target_weight:
            profile_text += f"🎯 **Целевой вес:** {user.target_weight} кг\n"

        profile_text += (
            f"\n📈 **Дневные нормы (КБЖУ):**\n"
            f"🔥 Калории: {user.daily_calories} ккал\n"
            f"🥩 Белки: {user.daily_protein}г\n"
            f"🍞 Углеводы: {user.daily_carbs}г\n"
            f"🧈 Жиры: {user.daily_fat}г"
        )

        await message.answer(
            profile_text,
            reply_markup=get_webapp_button(
                "✏️ Редактировать профиль",
                settings.WEBAPP_URL,
                "/profile/edit"
            ),
            parse_mode="Markdown"
        )
