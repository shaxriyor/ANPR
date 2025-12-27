from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    """Главное меню бота с Web App кнопками"""
    builder = InlineKeyboardBuilder()

    # Кнопка добавления еды (открывает камеру в Web App)
    builder.row(
        InlineKeyboardButton(
            text="📸 Добавить еду",
            web_app=WebAppInfo(url=f"{webapp_url}/camera")
        )
    )

    # Дневник и статистика
    builder.row(
        InlineKeyboardButton(
            text="📖 Дневник",
            web_app=WebAppInfo(url=f"{webapp_url}/diary")
        ),
        InlineKeyboardButton(
            text="📊 Статистика",
            web_app=WebAppInfo(url=f"{webapp_url}/stats")
        )
    )

    # Профиль и вода
    builder.row(
        InlineKeyboardButton(
            text="👤 Профиль",
            web_app=WebAppInfo(url=f"{webapp_url}/profile")
        ),
        InlineKeyboardButton(
            text="💧 Вода",
            callback_data="add_water"
        )
    )

    return builder.as_markup()


def get_webapp_button(text: str, webapp_url: str, path: str) -> InlineKeyboardMarkup:
    """Создать одну кнопку Web App"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=text,
            web_app=WebAppInfo(url=f"{webapp_url}{path}")
        )
    )
    return builder.as_markup()


def get_meal_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа приёма пищи"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌅 Завтрак", callback_data="meal_breakfast"),
        InlineKeyboardButton(text="☀️ Обед", callback_data="meal_lunch")
    )
    builder.row(
        InlineKeyboardButton(text="🌆 Ужин", callback_data="meal_dinner"),
        InlineKeyboardButton(text="🍪 Перекус", callback_data="meal_snack")
    )
    return builder.as_markup()


def get_water_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для добавления воды"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🥛 200 мл", callback_data="water_200"),
        InlineKeyboardButton(text="🫗 300 мл", callback_data="water_300")
    )
    builder.row(
        InlineKeyboardButton(text="🍶 500 мл", callback_data="water_500"),
        InlineKeyboardButton(text="🧴 1 л", callback_data="water_1000")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def get_confirm_food_keyboard(food_id: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения добавления еды"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Добавить", callback_data=f"confirm_food_{food_id}"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_food_{food_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()
