from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import date, datetime, timedelta
from typing import Optional, List

from .models import User, FoodEntry, DailyStats, Goal, ActivityLevel, Gender


# ============== USER CRUD ==============

async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_profile(
    db: AsyncSession,
    telegram_id: int,
    weight: float,
    height: float,
    age: int,
    gender: str,
    goal: str,
    activity_level: str,
    target_weight: Optional[float] = None
) -> User:
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise ValueError("User not found")

    user.weight = weight
    user.height = height
    user.age = age
    user.gender = Gender(gender)
    user.goal = Goal(goal)
    user.activity_level = ActivityLevel(activity_level)
    user.target_weight = target_weight
    user.is_registered = 1

    # Рассчитываем КБЖУ
    calories, protein, carbs, fat = calculate_macros(
        weight=weight,
        height=height,
        age=age,
        gender=gender,
        goal=goal,
        activity_level=activity_level
    )

    user.daily_calories = calories
    user.daily_protein = protein
    user.daily_carbs = carbs
    user.daily_fat = fat

    await db.commit()
    await db.refresh(user)
    return user


def calculate_macros(
    weight: float,
    height: float,
    age: int,
    gender: str,
    goal: str,
    activity_level: str
) -> tuple:
    """
    Расчёт КБЖУ по формуле Mifflin-St Jeor
    """
    # Базовый метаболизм (BMR)
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Коэффициент активности
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    multiplier = activity_multipliers.get(activity_level, 1.55)

    # TDEE (Total Daily Energy Expenditure)
    tdee = bmr * multiplier

    # Корректировка по цели
    if goal == "lose":
        calories = int(tdee - 500)  # Дефицит 500 ккал
    elif goal == "gain":
        calories = int(tdee + 300)  # Профицит 300 ккал
    else:
        calories = int(tdee)

    # Макронутриенты (стандартное соотношение)
    # Белок: 2г на кг веса для активных, 1.6г для остальных
    if activity_level in ["active", "very_active"]:
        protein = int(weight * 2)
    else:
        protein = int(weight * 1.6)

    # Жиры: 25% от калорий
    fat = int((calories * 0.25) / 9)

    # Углеводы: остаток
    carbs = int((calories - protein * 4 - fat * 9) / 4)

    return calories, protein, carbs, fat


# ============== FOOD ENTRY CRUD ==============

async def create_food_entry(
    db: AsyncSession,
    user_id: int,
    food_name: str,
    calories: int,
    protein: float,
    carbs: float,
    fat: float,
    food_name_ru: Optional[str] = None,
    photo_url: Optional[str] = None,
    portion_size: float = 100,
    portion_description: Optional[str] = None,
    meal_type: Optional[str] = None
) -> FoodEntry:
    entry = FoodEntry(
        user_id=user_id,
        food_name=food_name,
        food_name_ru=food_name_ru,
        photo_url=photo_url,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        portion_size=portion_size,
        portion_description=portion_description,
        meal_type=meal_type,
        entry_date=date.today()
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Обновляем дневную статистику
    await update_daily_stats(db, user_id, date.today())

    return entry


async def get_user_food_entries_by_date(
    db: AsyncSession,
    user_id: int,
    entry_date: date
) -> List[FoodEntry]:
    result = await db.execute(
        select(FoodEntry)
        .where(and_(
            FoodEntry.user_id == user_id,
            FoodEntry.entry_date == entry_date
        ))
        .order_by(FoodEntry.logged_at.desc())
    )
    return result.scalars().all()


async def delete_food_entry(db: AsyncSession, entry_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(FoodEntry).where(and_(
            FoodEntry.id == entry_id,
            FoodEntry.user_id == user_id
        ))
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry_date = entry.entry_date
        await db.delete(entry)
        await db.commit()
        await update_daily_stats(db, user_id, entry_date)
        return True
    return False


# ============== DAILY STATS CRUD ==============

async def get_or_create_daily_stats(
    db: AsyncSession,
    user_id: int,
    stats_date: date
) -> DailyStats:
    result = await db.execute(
        select(DailyStats).where(and_(
            DailyStats.user_id == user_id,
            DailyStats.stats_date == stats_date
        ))
    )
    stats = result.scalar_one_or_none()

    if not stats:
        stats = DailyStats(user_id=user_id, stats_date=stats_date)
        db.add(stats)
        await db.commit()
        await db.refresh(stats)

    return stats


async def update_daily_stats(db: AsyncSession, user_id: int, stats_date: date):
    """Пересчитать статистику за день на основе записей еды"""
    entries = await get_user_food_entries_by_date(db, user_id, stats_date)

    total_calories = sum(e.calories for e in entries)
    total_protein = sum(e.protein for e in entries)
    total_carbs = sum(e.carbs for e in entries)
    total_fat = sum(e.fat for e in entries)

    stats = await get_or_create_daily_stats(db, user_id, stats_date)
    stats.total_calories = total_calories
    stats.total_protein = total_protein
    stats.total_carbs = total_carbs
    stats.total_fat = total_fat

    await db.commit()


async def get_weekly_stats(
    db: AsyncSession,
    user_id: int
) -> List[DailyStats]:
    week_ago = date.today() - timedelta(days=7)
    result = await db.execute(
        select(DailyStats)
        .where(and_(
            DailyStats.user_id == user_id,
            DailyStats.stats_date >= week_ago
        ))
        .order_by(DailyStats.stats_date)
    )
    return result.scalars().all()


async def log_water(db: AsyncSession, user_id: int, ml: int) -> DailyStats:
    stats = await get_or_create_daily_stats(db, user_id, date.today())
    stats.water_ml += ml
    await db.commit()
    await db.refresh(stats)
    return stats


async def log_weight(db: AsyncSession, user_id: int, weight: float) -> DailyStats:
    stats = await get_or_create_daily_stats(db, user_id, date.today())
    stats.weight_log = weight
    await db.commit()
    await db.refresh(stats)
    return stats
