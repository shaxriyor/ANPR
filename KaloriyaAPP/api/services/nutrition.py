"""
Сервис расчёта нутриентов и распределения калорий по приёмам пищи
"""


def calculate_macros(
    weight: float,
    height: float,
    age: int,
    gender: str,
    goal: str,
    activity_level: str
) -> dict:
    """
    Расчёт КБЖУ по формуле Mifflin-St Jeor

    Returns:
        dict с calories, protein, carbs, fat
    """
    # Базовый метаболизм (BMR)
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Коэффициент активности
    activity_multipliers = {
        "sedentary": 1.2,      # Сидячий образ жизни
        "light": 1.375,        # Лёгкая активность 1-3 раза/неделю
        "moderate": 1.55,      # Умеренная 3-5 раз/неделю
        "active": 1.725,       # Высокая 6-7 раз/неделю
        "very_active": 1.9     # Очень высокая (спортсмены)
    }
    multiplier = activity_multipliers.get(activity_level, 1.55)

    # TDEE (Total Daily Energy Expenditure)
    tdee = bmr * multiplier

    # Корректировка по цели
    if goal == "lose":
        # Дефицит 20% (безопасное похудение)
        calories = int(tdee * 0.8)
    elif goal == "gain":
        # Профицит 10-15% (качественный набор)
        calories = int(tdee * 1.15)
    else:
        calories = int(tdee)

    # Макронутриенты
    # Белок: 1.6-2.2г на кг (больше для активных и при дефиците)
    if goal == "lose" or activity_level in ["active", "very_active"]:
        protein_per_kg = 2.0
    else:
        protein_per_kg = 1.6

    protein = int(weight * protein_per_kg)

    # Жиры: 0.8-1г на кг (минимум для гормонов)
    fat_per_kg = 0.9
    fat = int(weight * fat_per_kg)

    # Углеводы: остаток калорий
    protein_cals = protein * 4
    fat_cals = fat * 9
    remaining_cals = calories - protein_cals - fat_cals
    carbs = max(50, int(remaining_cals / 4))  # Минимум 50г углеводов

    return {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "bmr": int(bmr),
        "tdee": int(tdee)
    }


def distribute_meals(daily_calories: int, meals_count: int = 4) -> dict:
    """
    Распределение калорий по приёмам пищи

    Args:
        daily_calories: общее количество калорий
        meals_count: количество приёмов (3 или 4)

    Returns:
        dict с калориями для каждого приёма
    """
    if meals_count == 3:
        # Завтрак 25%, Обед 40%, Ужин 35%
        return {
            "breakfast": int(daily_calories * 0.25),
            "lunch": int(daily_calories * 0.40),
            "dinner": int(daily_calories * 0.35),
            "snack": 0
        }
    else:
        # Завтрак 25%, Обед 35%, Перекус 15%, Ужин 25%
        return {
            "breakfast": int(daily_calories * 0.25),
            "lunch": int(daily_calories * 0.35),
            "snack": int(daily_calories * 0.15),
            "dinner": int(daily_calories * 0.25)
        }


def calculate_remaining(
    eaten: dict,
    target: dict
) -> dict:
    """
    Рассчитать сколько осталось съесть

    Args:
        eaten: {"calories": X, "protein": X, "carbs": X, "fat": X}
        target: {"calories": X, "protein": X, "carbs": X, "fat": X}
    """
    return {
        "calories": max(0, target["calories"] - eaten["calories"]),
        "protein": max(0, target["protein"] - eaten["protein"]),
        "carbs": max(0, target["carbs"] - eaten["carbs"]),
        "fat": max(0, target["fat"] - eaten["fat"]),
        "calories_percent": min(100, int(eaten["calories"] / target["calories"] * 100)) if target["calories"] > 0 else 0,
        "protein_percent": min(100, int(eaten["protein"] / target["protein"] * 100)) if target["protein"] > 0 else 0,
        "carbs_percent": min(100, int(eaten["carbs"] / target["carbs"] * 100)) if target["carbs"] > 0 else 0,
        "fat_percent": min(100, int(eaten["fat"] / target["fat"] * 100)) if target["fat"] > 0 else 0,
    }


def suggest_meal(remaining_calories: int, meal_type: str) -> list:
    """
    Предложить варианты еды на оставшиеся калории
    """
    suggestions = {
        "low": [  # < 300 ккал
            {"name": "Греческий йогурт с ягодами", "calories": 150},
            {"name": "Яблоко + орехи", "calories": 200},
            {"name": "Овощной салат", "calories": 100},
            {"name": "Творог 5%", "calories": 120},
        ],
        "medium": [  # 300-600 ккал
            {"name": "Куриная грудка с овощами", "calories": 400},
            {"name": "Омлет из 3 яиц", "calories": 350},
            {"name": "Рыба на пару с рисом", "calories": 450},
            {"name": "Гречка с курицей", "calories": 500},
        ],
        "high": [  # > 600 ккал
            {"name": "Полноценный обед: суп + второе", "calories": 700},
            {"name": "Паста с мясным соусом", "calories": 650},
            {"name": "Бургер домашний", "calories": 600},
        ]
    }

    if remaining_calories < 300:
        return suggestions["low"]
    elif remaining_calories < 600:
        return suggestions["medium"]
    else:
        return suggestions["high"]
