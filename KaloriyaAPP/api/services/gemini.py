"""
Интеграция с Google Gemini Vision для распознавания еды
LLM используется ТОЛЬКО для распознавания, КБЖУ берётся из базы данных

Используется новый SDK: google-genai
Документация: https://ai.google.dev/gemini-api/docs
"""

from google import genai
from google.genai import types
import json
import base64
import hashlib
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import get_settings
from api.services.food_database import (
    food_cache,
    find_food_in_database,
    calculate_nutrition_for_portion,
    search_foods,
    FOOD_DATABASE
)
from api.services.logger import (
    ai_logger,
    log_food_recognition,
    log_cache_event,
    log_error
)

settings = get_settings()

# Инициализация клиента Gemini
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

# Модель для распознавания изображений (бесплатная/дешёвая)
VISION_MODEL = "gemini-2.5-flash"
TEXT_MODEL = "gemini-2.5-flash"


def get_image_hash(image_base64: str) -> str:
    """Получить хеш изображения для кеширования"""
    return hashlib.md5(image_base64.encode()).hexdigest()[:16]


async def analyze_food_image(image_base64: str) -> dict:
    """
    Анализ фото еды с помощью Google Gemini Vision

    1. Проверяем кеш по хешу изображения
    2. LLM распознаёт название блюда и оценивает порцию
    3. КБЖУ берём из базы данных, НЕ от LLM

    Returns:
        dict с названием, калориями, БЖУ, размером порции
    """
    start_time = time.time()

    # === 1. Проверяем кеш ===
    image_hash = get_image_hash(image_base64)
    cached_result = food_cache.get_by_hash(image_hash)

    if cached_result:
        log_cache_event("hit", f"img_{image_hash}")
        duration = (time.time() - start_time) * 1000
        log_food_recognition(
            telegram_id=0,
            food_name=cached_result.get("food_name", "Unknown"),
            calories=cached_result.get("calories", 0),
            confidence=cached_result.get("confidence", 1.0),
            cached=True,
            duration_ms=duration
        )
        return cached_result

    log_cache_event("miss", f"img_{image_hash}")

    try:
        # === 2. LLM распознаёт блюдо ===
        # Декодируем base64 в bytes
        image_bytes = base64.b64decode(image_base64)

        # Промпт только для распознавания, БЕЗ расчёта калорий
        prompt = """Analyze this food image.

IMPORTANT: Respond ONLY with valid JSON, no markdown, no explanations.

You need to identify:
1. What food/dish is shown
2. Estimate the portion size in grams

JSON format:
{
    "food_name": "English name (lowercase, e.g. 'pilaf', 'chicken breast', 'pasta')",
    "food_name_ru": "Название блюда на русском языке",
    "portion_size": <float - estimated portion in grams, be realistic: plate=200-400g, snack=50-150g>,
    "portion_description": "описание порции (например: 1 тарелка, 200г, 2 куска)",
    "ingredients": ["main ingredient 1", "main ingredient 2"],
    "confidence": <float 0-1 - how confident you are in identification>
}

Examples of portion sizes:
- Plate of rice/pasta: 200-300g
- Plate of soup: 300-400g
- Piece of meat: 100-200g
- Salad: 150-250g
- Sandwich: 150-200g
- Apple: 150-200g

DO NOT include calorie or nutrition values - just identify the food and portion."""

        ai_logger.info(f"Sending image to Gemini (hash={image_hash})")

        # Используем новый SDK: google-genai
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                ),
                prompt
            ]
        )

        # Парсим ответ
        response_text = response.text.strip()
        ai_logger.debug(f"Gemini raw response: {response_text[:200]}...")

        # Убираем markdown если есть
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        llm_result = json.loads(response_text.strip())

        food_name = llm_result.get("food_name", "unknown").lower()
        food_name_ru = llm_result.get("food_name_ru", "Неизвестное блюдо")
        portion_size = float(llm_result.get("portion_size", 200))
        portion_desc = llm_result.get("portion_description", f"~{int(portion_size)}г")
        ingredients = llm_result.get("ingredients", [])
        confidence = float(llm_result.get("confidence", 0.5))

        ai_logger.info(f"LLM identified: {food_name} ({food_name_ru}), portion={portion_size}g, conf={confidence}")

        # === 3. Получаем КБЖУ из базы данных ===
        nutrition = find_food_in_database(food_name)

        if not nutrition:
            # Пробуем по русскому названию
            nutrition = find_food_in_database(food_name_ru)

        if not nutrition:
            # Пробуем по ингредиентам
            for ingredient in ingredients:
                nutrition = find_food_in_database(ingredient)
                if nutrition:
                    ai_logger.info(f"Found by ingredient: {ingredient}")
                    break

        if nutrition:
            # Пересчитываем на порцию
            portion_nutrition = calculate_nutrition_for_portion(nutrition, portion_size)

            result = {
                "food_name": food_name,
                "food_name_ru": nutrition.get("name_ru", food_name_ru),
                "calories": portion_nutrition["calories"],
                "protein": portion_nutrition["protein"],
                "carbs": portion_nutrition["carbs"],
                "fat": portion_nutrition["fat"],
                "portion_size": portion_size,
                "portion_description": portion_desc,
                "ingredients": ingredients,
                "confidence": confidence,
                "health_notes": "",
                "from_database": True
            }

            ai_logger.info(f"Nutrition from DB: {result['calories']} kcal for {portion_size}g")

        else:
            # Продукт не найден в базе - используем средние значения
            ai_logger.warning(f"Food '{food_name}' not found in database, using estimates")

            # Примерные средние значения на 100г
            avg_calories_per_100g = 150
            avg_protein_per_100g = 8
            avg_carbs_per_100g = 20
            avg_fat_per_100g = 5

            multiplier = portion_size / 100

            result = {
                "food_name": food_name,
                "food_name_ru": food_name_ru,
                "calories": int(avg_calories_per_100g * multiplier),
                "protein": round(avg_protein_per_100g * multiplier, 1),
                "carbs": round(avg_carbs_per_100g * multiplier, 1),
                "fat": round(avg_fat_per_100g * multiplier, 1),
                "portion_size": portion_size,
                "portion_description": portion_desc,
                "ingredients": ingredients,
                "confidence": confidence * 0.5,  # Снижаем уверенность
                "health_notes": "⚠️ Продукт не найден в базе, значения приблизительные",
                "from_database": False
            }

        # === 4. Сохраняем в кеш ===
        food_cache.set_by_hash(image_hash, result)
        log_cache_event("set", f"img_{image_hash}", f"food={food_name}")

        # Также кешируем по названию для будущих запросов
        food_cache.set(food_name, result)

        duration = (time.time() - start_time) * 1000
        log_food_recognition(
            telegram_id=0,
            food_name=result["food_name"],
            calories=result["calories"],
            confidence=result["confidence"],
            cached=False,
            duration_ms=duration
        )

        return result

    except json.JSONDecodeError as e:
        log_error("gemini_parse", e, {"response": response_text[:200] if 'response_text' in locals() else "no response"})
        return {
            "food_name": "unknown",
            "food_name_ru": "Не удалось распознать",
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "portion_size": 100,
            "portion_description": "неизвестно",
            "ingredients": [],
            "confidence": 0,
            "health_notes": "Не удалось проанализировать фото. Попробуйте сделать более чёткий снимок.",
            "from_database": False
        }

    except Exception as e:
        log_error("gemini_api", e, {"image_hash": image_hash})
        raise Exception(f"Gemini API error: {str(e)}")


async def get_food_suggestions(query: str) -> list:
    """
    Получить предложения еды по текстовому запросу
    Сначала ищем в базе, потом в LLM
    """
    ai_logger.info(f"Food search: '{query}'")

    # Сначала ищем в локальной базе
    local_results = search_foods(query, limit=5)

    if local_results:
        ai_logger.info(f"Found {len(local_results)} results in local DB")
        return [
            {
                "name": r["name"],
                "name_ru": r["name_ru"],
                "calories_per_100g": r["calories"],
                "protein_per_100g": r["protein"],
                "carbs_per_100g": r["carbs"],
                "fat_per_100g": r["fat"]
            }
            for r in local_results
        ]

    # Если в базе нет - спрашиваем LLM
    ai_logger.info("No local results, asking LLM")

    try:
        prompt = f"""User is searching for food: "{query}"

Suggest 5 common foods/dishes that match this query.
Respond ONLY with valid JSON array:
[
    {{
        "name": "English name",
        "name_ru": "Название на русском",
        "calories_per_100g": <int>,
        "protein_per_100g": <float>,
        "carbs_per_100g": <float>,
        "fat_per_100g": <float>
    }}
]"""

        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt
        )
        response_text = response.text.strip()

        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return json.loads(response_text.strip())

    except Exception as e:
        log_error("food_suggestions", e, {"query": query})
        return []


async def get_ai_motivation(user_stats: dict) -> str:
    """
    Получить мотивационное сообщение от AI
    """
    ai_logger.info(f"Generating motivation for user stats: {user_stats}")

    try:
        prompt = f"""You are a friendly nutrition coach.

User stats:
- Goal: {user_stats.get('goal', 'maintain')}
- Days tracked: {user_stats.get('days_tracked', 0)}
- Average calories: {user_stats.get('avg_calories', 0)} / {user_stats.get('target_calories', 2000)}
- Weight change: {user_stats.get('weight_change', 0)} kg over {user_stats.get('weight_days', 7)} days
- Streak: {user_stats.get('streak', 0)} days

Give a SHORT (2-3 sentences) motivational message in Russian.
Be encouraging but realistic. If they're doing well, praise them.
If they're struggling, give gentle advice."""

        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt
        )
        message = response.text.strip()
        ai_logger.info(f"Generated motivation: {message[:100]}...")
        return message

    except Exception as e:
        log_error("motivation", e, {"stats": user_stats})
        return "Продолжай в том же духе! Каждый день приближает тебя к цели. 💪"
