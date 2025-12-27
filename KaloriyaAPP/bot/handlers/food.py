from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
import base64
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import get_settings
from database.connection import async_session
from database.crud import get_user_by_telegram_id, create_food_entry
from bot.keyboards.inline import get_meal_type_keyboard, get_confirm_food_keyboard

router = Router()
settings = get_settings()


class FoodStates(StatesGroup):
    waiting_for_meal_type = State()
    waiting_for_confirmation = State()


@router.message(F.photo)
async def handle_food_photo(message: Message, state: FSMContext):
    """Обработка фото еды отправленного напрямую в чат"""
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, message.from_user.id)

        if not user or not user.is_registered:
            await message.answer(
                "❗ Сначала заполни профиль!\n"
                "Нажми /start чтобы начать."
            )
            return

    # Показываем что обрабатываем
    processing_msg = await message.answer("🔍 Анализирую фото...")

    try:
        # Получаем файл фото (берём самое большое разрешение)
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_path = file.file_path

        # Скачиваем фото
        file_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                else:
                    await processing_msg.edit_text("❌ Не удалось загрузить фото")
                    return

        # Отправляем на анализ в наш API
        api_url = f"{settings.WEBAPP_URL}/api/food/analyze"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json={
                    "image_base64": image_base64,
                    "telegram_id": message.from_user.id
                }
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                else:
                    error_text = await resp.text()
                    await processing_msg.edit_text(
                        f"❌ Ошибка анализа: {error_text[:100]}"
                    )
                    return

        # Сохраняем результат в состояние
        await state.update_data(
            food_data=result,
            photo_file_id=photo.file_id
        )

        # Формируем ответ
        food_text = format_food_result(result)
        await processing_msg.edit_text(
            food_text + "\n\nВыбери тип приёма пищи:",
            reply_markup=get_meal_type_keyboard(),
            parse_mode="Markdown"
        )

        await state.set_state(FoodStates.waiting_for_meal_type)

    except Exception as e:
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("meal_"))
async def handle_meal_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа приёма пищи"""
    meal_type = callback.data.replace("meal_", "")
    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }

    data = await state.get_data()
    food_data = data.get("food_data")

    if not food_data:
        await callback.answer("❌ Данные устарели, отправь фото ещё раз")
        await state.clear()
        return

    async with async_session() as db:
        user = await get_user_by_telegram_id(db, callback.from_user.id)

        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Создаём запись о еде
        entry = await create_food_entry(
            db=db,
            user_id=user.id,
            food_name=food_data.get("food_name", "Неизвестно"),
            food_name_ru=food_data.get("food_name_ru"),
            calories=food_data.get("calories", 0),
            protein=food_data.get("protein", 0),
            carbs=food_data.get("carbs", 0),
            fat=food_data.get("fat", 0),
            portion_size=food_data.get("portion_size", 100),
            portion_description=food_data.get("portion_description"),
            meal_type=meal_type
        )

    await state.clear()

    success_text = (
        f"✅ **{meal_names.get(meal_type, meal_type)}** добавлен!\n\n"
        f"🍽 {food_data.get('food_name_ru') or food_data.get('food_name')}\n"
        f"🔥 {food_data.get('calories', 0)} ккал\n\n"
        "Нажми /menu чтобы увидеть обновлённую статистику"
    )

    await callback.message.edit_text(success_text, parse_mode="Markdown")
    await callback.answer("✅ Добавлено!")


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()


def format_food_result(result: dict) -> str:
    """Форматирование результата анализа еды"""
    food_name = result.get("food_name_ru") or result.get("food_name", "Неизвестно")
    calories = result.get("calories", 0)
    protein = result.get("protein", 0)
    carbs = result.get("carbs", 0)
    fat = result.get("fat", 0)
    portion = result.get("portion_description", "~100г")

    return (
        f"🍽 **{food_name}**\n"
        f"📏 Порция: {portion}\n\n"
        f"🔥 Калории: **{calories}** ккал\n"
        f"🥩 Белки: {protein}г\n"
        f"🍞 Углеводы: {carbs}г\n"
        f"🧈 Жиры: {fat}г"
    )
