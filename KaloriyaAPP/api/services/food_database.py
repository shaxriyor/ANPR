"""
База данных продуктов с КБЖУ на 100г
Используется вместо LLM для расчёта калорий
"""

import json
import os
from typing import Optional, Dict, List
from difflib import SequenceMatcher


# Путь к файлу кеша
CACHE_FILE = os.path.join(os.path.dirname(__file__), "food_cache.json")


# === Встроенная база продуктов (на 100г) ===

FOOD_DATABASE: Dict[str, Dict] = {
    # === МЯСО И ПТИЦА ===
    "chicken breast": {"name_ru": "Куриная грудка", "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
    "chicken thigh": {"name_ru": "Куриное бедро", "calories": 209, "protein": 26, "carbs": 0, "fat": 10.9},
    "chicken leg": {"name_ru": "Куриная ножка", "calories": 184, "protein": 26, "carbs": 0, "fat": 8},
    "chicken wings": {"name_ru": "Куриные крылышки", "calories": 203, "protein": 30, "carbs": 0, "fat": 8},
    "beef": {"name_ru": "Говядина", "calories": 250, "protein": 26, "carbs": 0, "fat": 15},
    "beef steak": {"name_ru": "Стейк из говядины", "calories": 271, "protein": 26, "carbs": 0, "fat": 18},
    "ground beef": {"name_ru": "Говяжий фарш", "calories": 254, "protein": 17, "carbs": 0, "fat": 20},
    "pork": {"name_ru": "Свинина", "calories": 242, "protein": 27, "carbs": 0, "fat": 14},
    "pork chop": {"name_ru": "Свиная отбивная", "calories": 231, "protein": 25, "carbs": 0, "fat": 14},
    "lamb": {"name_ru": "Баранина", "calories": 294, "protein": 25, "carbs": 0, "fat": 21},
    "turkey breast": {"name_ru": "Грудка индейки", "calories": 135, "protein": 30, "carbs": 0, "fat": 1},
    "duck": {"name_ru": "Утка", "calories": 337, "protein": 19, "carbs": 0, "fat": 28},

    # === РЫБА И МОРЕПРОДУКТЫ ===
    "salmon": {"name_ru": "Лосось", "calories": 208, "protein": 20, "carbs": 0, "fat": 13},
    "tuna": {"name_ru": "Тунец", "calories": 132, "protein": 28, "carbs": 0, "fat": 1},
    "cod": {"name_ru": "Треска", "calories": 82, "protein": 18, "carbs": 0, "fat": 0.7},
    "shrimp": {"name_ru": "Креветки", "calories": 99, "protein": 24, "carbs": 0.2, "fat": 0.3},
    "fish": {"name_ru": "Рыба", "calories": 120, "protein": 22, "carbs": 0, "fat": 3},
    "herring": {"name_ru": "Сельдь", "calories": 158, "protein": 18, "carbs": 0, "fat": 9},
    "mackerel": {"name_ru": "Скумбрия", "calories": 262, "protein": 19, "carbs": 0, "fat": 18},

    # === КРУПЫ И ГАРНИРЫ ===
    "rice": {"name_ru": "Рис (варёный)", "calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
    "rice white": {"name_ru": "Белый рис", "calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
    "rice brown": {"name_ru": "Бурый рис", "calories": 111, "protein": 2.6, "carbs": 23, "fat": 0.9},
    "buckwheat": {"name_ru": "Гречка (варёная)", "calories": 110, "protein": 4.2, "carbs": 21, "fat": 1.1},
    "pasta": {"name_ru": "Макароны (варёные)", "calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
    "spaghetti": {"name_ru": "Спагетти", "calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
    "oatmeal": {"name_ru": "Овсянка (варёная)", "calories": 68, "protein": 2.4, "carbs": 12, "fat": 1.4},
    "mashed potatoes": {"name_ru": "Пюре картофельное", "calories": 83, "protein": 2, "carbs": 16, "fat": 1.2},
    "potatoes": {"name_ru": "Картофель (варёный)", "calories": 82, "protein": 2, "carbs": 17, "fat": 0.1},
    "french fries": {"name_ru": "Картофель фри", "calories": 312, "protein": 3.4, "carbs": 41, "fat": 15},
    "bread": {"name_ru": "Хлеб белый", "calories": 265, "protein": 9, "carbs": 49, "fat": 3.2},
    "bread black": {"name_ru": "Хлеб чёрный", "calories": 201, "protein": 6.6, "carbs": 40, "fat": 1.2},

    # === ГОТОВЫЕ БЛЮДА ===
    "pilaf": {"name_ru": "Плов", "calories": 150, "protein": 6, "carbs": 22, "fat": 5},
    "plov": {"name_ru": "Плов", "calories": 150, "protein": 6, "carbs": 22, "fat": 5},
    "borscht": {"name_ru": "Борщ", "calories": 49, "protein": 2.8, "carbs": 5.4, "fat": 1.3},
    "soup": {"name_ru": "Суп", "calories": 45, "protein": 2.5, "carbs": 5, "fat": 1.5},
    "chicken soup": {"name_ru": "Куриный суп", "calories": 53, "protein": 3.5, "carbs": 4, "fat": 2.5},
    "salad caesar": {"name_ru": "Салат Цезарь", "calories": 127, "protein": 7, "carbs": 7, "fat": 8},
    "salad greek": {"name_ru": "Греческий салат", "calories": 87, "protein": 4, "carbs": 5, "fat": 6},
    "salad vegetable": {"name_ru": "Овощной салат", "calories": 35, "protein": 1, "carbs": 5, "fat": 1},
    "pizza": {"name_ru": "Пицца", "calories": 266, "protein": 11, "carbs": 33, "fat": 10},
    "burger": {"name_ru": "Бургер", "calories": 295, "protein": 17, "carbs": 24, "fat": 14},
    "hamburger": {"name_ru": "Гамбургер", "calories": 295, "protein": 17, "carbs": 24, "fat": 14},
    "sandwich": {"name_ru": "Сэндвич", "calories": 250, "protein": 12, "carbs": 28, "fat": 10},
    "pancakes": {"name_ru": "Блины", "calories": 227, "protein": 6, "carbs": 28, "fat": 10},
    "omelette": {"name_ru": "Омлет", "calories": 154, "protein": 11, "carbs": 0.7, "fat": 12},
    "fried eggs": {"name_ru": "Яичница", "calories": 196, "protein": 14, "carbs": 1, "fat": 15},
    "scrambled eggs": {"name_ru": "Яичница-болтунья", "calories": 166, "protein": 11, "carbs": 2, "fat": 12},
    "dumplings": {"name_ru": "Пельмени", "calories": 275, "protein": 12, "carbs": 29, "fat": 12},
    "sushi": {"name_ru": "Суши", "calories": 143, "protein": 6, "carbs": 21, "fat": 4},
    "sushi roll": {"name_ru": "Ролл", "calories": 150, "protein": 5, "carbs": 23, "fat": 4},
    "shawarma": {"name_ru": "Шаурма", "calories": 215, "protein": 10, "carbs": 18, "fat": 11},
    "kebab": {"name_ru": "Шашлык", "calories": 250, "protein": 26, "carbs": 0, "fat": 16},
    "manti": {"name_ru": "Манты", "calories": 180, "protein": 10, "carbs": 20, "fat": 7},
    "lagman": {"name_ru": "Лагман", "calories": 110, "protein": 5, "carbs": 15, "fat": 3},
    "shurpa": {"name_ru": "Шурпа", "calories": 65, "protein": 4, "carbs": 5, "fat": 3},
    "samsa": {"name_ru": "Самса", "calories": 280, "protein": 10, "carbs": 25, "fat": 15},

    # === МОЛОЧНЫЕ ПРОДУКТЫ ===
    "milk": {"name_ru": "Молоко 3.2%", "calories": 60, "protein": 3, "carbs": 4.7, "fat": 3.2},
    "yogurt": {"name_ru": "Йогурт", "calories": 63, "protein": 5, "carbs": 7, "fat": 1.5},
    "greek yogurt": {"name_ru": "Греческий йогурт", "calories": 97, "protein": 9, "carbs": 4, "fat": 5},
    "cottage cheese": {"name_ru": "Творог 5%", "calories": 121, "protein": 17, "carbs": 1.8, "fat": 5},
    "cheese": {"name_ru": "Сыр", "calories": 350, "protein": 25, "carbs": 0, "fat": 28},
    "butter": {"name_ru": "Сливочное масло", "calories": 717, "protein": 0.5, "carbs": 0.1, "fat": 81},
    "sour cream": {"name_ru": "Сметана 15%", "calories": 158, "protein": 2.6, "carbs": 3.6, "fat": 15},
    "kefir": {"name_ru": "Кефир", "calories": 41, "protein": 3.4, "carbs": 4, "fat": 1},

    # === ЯЙЦА ===
    "egg": {"name_ru": "Яйцо куриное (1 шт = 50г)", "calories": 155, "protein": 13, "carbs": 1.1, "fat": 11},
    "egg white": {"name_ru": "Яичный белок", "calories": 52, "protein": 11, "carbs": 0.7, "fat": 0.2},
    "egg yolk": {"name_ru": "Яичный желток", "calories": 322, "protein": 16, "carbs": 1, "fat": 27},

    # === ОВОЩИ ===
    "tomato": {"name_ru": "Помидор", "calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2},
    "cucumber": {"name_ru": "Огурец", "calories": 15, "protein": 0.7, "carbs": 3.6, "fat": 0.1},
    "carrot": {"name_ru": "Морковь", "calories": 35, "protein": 0.9, "carbs": 7, "fat": 0.2},
    "cabbage": {"name_ru": "Капуста", "calories": 25, "protein": 1.3, "carbs": 6, "fat": 0.1},
    "broccoli": {"name_ru": "Брокколи", "calories": 34, "protein": 2.8, "carbs": 7, "fat": 0.4},
    "onion": {"name_ru": "Лук", "calories": 40, "protein": 1.1, "carbs": 9, "fat": 0.1},
    "pepper": {"name_ru": "Перец болгарский", "calories": 27, "protein": 1, "carbs": 5.3, "fat": 0.1},
    "eggplant": {"name_ru": "Баклажан", "calories": 24, "protein": 1.2, "carbs": 4.5, "fat": 0.1},
    "zucchini": {"name_ru": "Кабачок", "calories": 24, "protein": 0.6, "carbs": 4.6, "fat": 0.3},

    # === ФРУКТЫ ===
    "apple": {"name_ru": "Яблоко", "calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2},
    "banana": {"name_ru": "Банан", "calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3},
    "orange": {"name_ru": "Апельсин", "calories": 43, "protein": 0.9, "carbs": 9, "fat": 0.1},
    "grapes": {"name_ru": "Виноград", "calories": 69, "protein": 0.7, "carbs": 18, "fat": 0.2},
    "watermelon": {"name_ru": "Арбуз", "calories": 30, "protein": 0.6, "carbs": 8, "fat": 0.1},
    "melon": {"name_ru": "Дыня", "calories": 34, "protein": 0.8, "carbs": 8, "fat": 0.2},
    "strawberry": {"name_ru": "Клубника", "calories": 32, "protein": 0.7, "carbs": 8, "fat": 0.3},
    "peach": {"name_ru": "Персик", "calories": 39, "protein": 0.9, "carbs": 10, "fat": 0.3},

    # === ОРЕХИ ===
    "nuts": {"name_ru": "Орехи (смесь)", "calories": 607, "protein": 20, "carbs": 20, "fat": 54},
    "almonds": {"name_ru": "Миндаль", "calories": 579, "protein": 21, "carbs": 22, "fat": 50},
    "walnuts": {"name_ru": "Грецкий орех", "calories": 654, "protein": 15, "carbs": 14, "fat": 65},
    "peanuts": {"name_ru": "Арахис", "calories": 567, "protein": 26, "carbs": 16, "fat": 49},

    # === НАПИТКИ ===
    "coffee": {"name_ru": "Кофе чёрный", "calories": 2, "protein": 0.1, "carbs": 0, "fat": 0},
    "coffee with milk": {"name_ru": "Кофе с молоком", "calories": 30, "protein": 1.5, "carbs": 2, "fat": 1.5},
    "latte": {"name_ru": "Латте", "calories": 67, "protein": 3, "carbs": 5, "fat": 4},
    "cappuccino": {"name_ru": "Капучино", "calories": 45, "protein": 2.5, "carbs": 4, "fat": 2},
    "tea": {"name_ru": "Чай без сахара", "calories": 1, "protein": 0, "carbs": 0.3, "fat": 0},
    "juice orange": {"name_ru": "Апельсиновый сок", "calories": 45, "protein": 0.7, "carbs": 10, "fat": 0.2},
    "juice apple": {"name_ru": "Яблочный сок", "calories": 46, "protein": 0.1, "carbs": 11, "fat": 0.1},
    "cola": {"name_ru": "Кола", "calories": 42, "protein": 0, "carbs": 11, "fat": 0},
    "beer": {"name_ru": "Пиво", "calories": 43, "protein": 0.5, "carbs": 3.6, "fat": 0},

    # === СЛАДОСТИ ===
    "chocolate": {"name_ru": "Шоколад", "calories": 546, "protein": 5, "carbs": 59, "fat": 31},
    "cake": {"name_ru": "Торт", "calories": 350, "protein": 4, "carbs": 50, "fat": 15},
    "ice cream": {"name_ru": "Мороженое", "calories": 207, "protein": 3.5, "carbs": 24, "fat": 11},
    "cookies": {"name_ru": "Печенье", "calories": 450, "protein": 6, "carbs": 65, "fat": 18},
    "candy": {"name_ru": "Конфеты", "calories": 380, "protein": 2, "carbs": 75, "fat": 8},

    # === ФАСТФУД ===
    "mcdonalds big mac": {"name_ru": "Биг Мак", "calories": 257, "protein": 13, "carbs": 20, "fat": 14},
    "kfc chicken": {"name_ru": "KFC курица", "calories": 260, "protein": 16, "carbs": 11, "fat": 16},
    "hot dog": {"name_ru": "Хот-дог", "calories": 290, "protein": 10, "carbs": 24, "fat": 17},
}


# === Алиасы для поиска ===
ALIASES: Dict[str, str] = {
    "курица": "chicken breast",
    "куриная грудка": "chicken breast",
    "куриное бедро": "chicken thigh",
    "курочка": "chicken breast",
    "говядина": "beef",
    "свинина": "pork",
    "рис": "rice",
    "гречка": "buckwheat",
    "макароны": "pasta",
    "спагетти": "spaghetti",
    "картошка": "potatoes",
    "пюре": "mashed potatoes",
    "плов": "pilaf",
    "борщ": "borscht",
    "суп": "soup",
    "салат": "salad vegetable",
    "цезарь": "salad caesar",
    "пицца": "pizza",
    "бургер": "burger",
    "шаурма": "shawarma",
    "шашлык": "kebab",
    "пельмени": "dumplings",
    "манты": "manti",
    "лагман": "lagman",
    "самса": "samsa",
    "яйцо": "egg",
    "яичница": "fried eggs",
    "омлет": "omelette",
    "блины": "pancakes",
    "творог": "cottage cheese",
    "сыр": "cheese",
    "молоко": "milk",
    "йогурт": "yogurt",
    "кефир": "kefir",
    "яблоко": "apple",
    "банан": "banana",
    "апельсин": "orange",
    "кофе": "coffee",
    "чай": "tea",
    "сок": "juice orange",
    "шоколад": "chocolate",
    "мороженое": "ice cream",
    "торт": "cake",
    "лосось": "salmon",
    "рыба": "fish",
    "креветки": "shrimp",
    "хлеб": "bread",
    "овсянка": "oatmeal",
}


class FoodCache:
    """Кеш для распознанных блюд"""

    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Загрузить кеш из файла"""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
        except Exception:
            self.cache = {}

    def _save_cache(self):
        """Сохранить кеш в файл"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key: str) -> Optional[Dict]:
        """Получить из кеша"""
        return self.cache.get(key.lower())

    def set(self, key: str, value: Dict):
        """Сохранить в кеш"""
        self.cache[key.lower()] = value
        self._save_cache()

    def get_by_hash(self, image_hash: str) -> Optional[Dict]:
        """Получить по хешу изображения"""
        return self.cache.get(f"img_{image_hash}")

    def set_by_hash(self, image_hash: str, value: Dict):
        """Сохранить по хешу изображения"""
        self.cache[f"img_{image_hash}"] = value
        self._save_cache()


# Глобальный экземпляр кеша
food_cache = FoodCache()


def find_food_in_database(food_name: str) -> Optional[Dict]:
    """
    Найти продукт в базе данных

    Args:
        food_name: название на английском или русском

    Returns:
        Словарь с КБЖУ или None
    """
    name_lower = food_name.lower().strip()

    # Проверяем алиасы
    if name_lower in ALIASES:
        name_lower = ALIASES[name_lower]

    # Прямой поиск
    if name_lower in FOOD_DATABASE:
        return FOOD_DATABASE[name_lower]

    # Поиск по частичному совпадению
    for key, value in FOOD_DATABASE.items():
        if name_lower in key or key in name_lower:
            return value

    # Поиск по русскому названию
    for key, value in FOOD_DATABASE.items():
        if value.get("name_ru", "").lower() == name_lower:
            return value

    # Fuzzy matching
    best_match = None
    best_ratio = 0

    for key, value in FOOD_DATABASE.items():
        ratio = SequenceMatcher(None, name_lower, key).ratio()
        if ratio > best_ratio and ratio > 0.6:
            best_ratio = ratio
            best_match = value

        # Также проверяем русское название
        ru_name = value.get("name_ru", "").lower()
        ratio_ru = SequenceMatcher(None, name_lower, ru_name).ratio()
        if ratio_ru > best_ratio and ratio_ru > 0.6:
            best_ratio = ratio_ru
            best_match = value

    return best_match


def calculate_nutrition_for_portion(
    base_nutrition: Dict,
    portion_grams: float
) -> Dict:
    """
    Пересчитать КБЖУ на порцию

    Args:
        base_nutrition: КБЖУ на 100г
        portion_grams: размер порции в граммах

    Returns:
        КБЖУ для порции
    """
    multiplier = portion_grams / 100

    return {
        "name_ru": base_nutrition.get("name_ru", ""),
        "calories": int(base_nutrition["calories"] * multiplier),
        "protein": round(base_nutrition["protein"] * multiplier, 1),
        "carbs": round(base_nutrition["carbs"] * multiplier, 1),
        "fat": round(base_nutrition["fat"] * multiplier, 1),
        "portion_size": portion_grams
    }


def search_foods(query: str, limit: int = 10) -> List[Dict]:
    """
    Поиск продуктов по запросу

    Args:
        query: поисковый запрос
        limit: максимум результатов

    Returns:
        Список найденных продуктов
    """
    query_lower = query.lower().strip()
    results = []

    for key, value in FOOD_DATABASE.items():
        name_ru = value.get("name_ru", "").lower()

        if query_lower in key or query_lower in name_ru:
            results.append({
                "name": key,
                "name_ru": value["name_ru"],
                "calories": value["calories"],
                "protein": value["protein"],
                "carbs": value["carbs"],
                "fat": value["fat"]
            })

            if len(results) >= limit:
                break

    return results
