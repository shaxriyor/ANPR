from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, timedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import async_session
from database.crud import (
    get_user_by_telegram_id,
    get_or_create_daily_stats,
    get_weekly_stats,
    log_water,
    log_weight,
    get_user_food_entries_by_date
)
from api.services.recommendations import (
    RecommendationEngine,
    get_meal_reminders
)
from api.services.gemini import get_ai_motivation
from api.services.nutrition import distribute_meals, calculate_remaining

router = APIRouter(prefix="/stats", tags=["stats"])


# === Pydantic Models ===

class DailyStatsResponse(BaseModel):
    date: str
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fat: float
    water_ml: int
    weight_log: Optional[float]
    target_calories: int
    target_protein: int
    target_carbs: int
    target_fat: int
    remaining_calories: int
    calories_percent: int


class WeeklyStatsResponse(BaseModel):
    days: List[DailyStatsResponse]
    avg_calories: int
    avg_protein: float
    avg_carbs: float
    avg_fat: float
    streak: int


class RecommendationResponse(BaseModel):
    type: str
    title: str
    message: str
    priority: int
    action_text: Optional[str] = None
    adjustment_value: Optional[int] = None


class LogWaterRequest(BaseModel):
    telegram_id: int
    ml: int


class LogWeightRequest(BaseModel):
    telegram_id: int
    weight: float


# === Endpoints ===

@router.get("/today/{telegram_id}", response_model=DailyStatsResponse)
async def get_today_stats(telegram_id: int):
    """
    Получить статистику за сегодня
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        stats = await get_or_create_daily_stats(db, user.id, date.today())

        remaining = max(0, (user.daily_calories or 0) - stats.total_calories)
        percent = min(100, int((stats.total_calories / (user.daily_calories or 1)) * 100))

        return DailyStatsResponse(
            date=date.today().isoformat(),
            total_calories=stats.total_calories,
            total_protein=stats.total_protein,
            total_carbs=stats.total_carbs,
            total_fat=stats.total_fat,
            water_ml=stats.water_ml,
            weight_log=stats.weight_log,
            target_calories=user.daily_calories or 0,
            target_protein=user.daily_protein or 0,
            target_carbs=user.daily_carbs or 0,
            target_fat=user.daily_fat or 0,
            remaining_calories=remaining,
            calories_percent=percent
        )


@router.get("/weekly/{telegram_id}", response_model=WeeklyStatsResponse)
async def get_weekly_statistics(telegram_id: int):
    """
    Получить статистику за неделю
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        weekly = await get_weekly_stats(db, user.id)

        days = []
        for s in weekly:
            remaining = max(0, (user.daily_calories or 0) - s.total_calories)
            percent = min(100, int((s.total_calories / (user.daily_calories or 1)) * 100))
            days.append(DailyStatsResponse(
                date=s.stats_date.isoformat(),
                total_calories=s.total_calories,
                total_protein=s.total_protein,
                total_carbs=s.total_carbs,
                total_fat=s.total_fat,
                water_ml=s.water_ml,
                weight_log=s.weight_log,
                target_calories=user.daily_calories or 0,
                target_protein=user.daily_protein or 0,
                target_carbs=user.daily_carbs or 0,
                target_fat=user.daily_fat or 0,
                remaining_calories=remaining,
                calories_percent=percent
            ))

        # Считаем средние
        if weekly:
            avg_cal = sum(s.total_calories for s in weekly) / len(weekly)
            avg_prot = sum(s.total_protein for s in weekly) / len(weekly)
            avg_carb = sum(s.total_carbs for s in weekly) / len(weekly)
            avg_fat = sum(s.total_fat for s in weekly) / len(weekly)
        else:
            avg_cal = avg_prot = avg_carb = avg_fat = 0

        # Считаем streak
        streak = 0
        check_date = date.today()
        dates_set = {s.stats_date for s in weekly}
        while check_date in dates_set:
            streak += 1
            check_date -= timedelta(days=1)

        return WeeklyStatsResponse(
            days=days,
            avg_calories=int(avg_cal),
            avg_protein=avg_prot,
            avg_carbs=avg_carb,
            avg_fat=avg_fat,
            streak=streak
        )


@router.get("/recommendations/{telegram_id}", response_model=List[RecommendationResponse])
async def get_recommendations(telegram_id: int):
    """
    Получить персональные рекомендации
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Собираем историю веса
        weekly = await get_weekly_stats(db, user.id)
        weight_history = [
            (s.stats_date, s.weight_log)
            for s in weekly if s.weight_log
        ]

        # История калорий
        calorie_history = [
            (s.stats_date, s.total_calories)
            for s in weekly
        ]

        # Вода сегодня
        today_stats = await get_or_create_daily_stats(db, user.id, date.today())
        water_today = today_stats.water_ml

        # Создаём движок рекомендаций
        engine = RecommendationEngine(
            user_goal=user.goal.value if user.goal else "maintain",
            target_calories=user.daily_calories or 2000,
            target_weight=user.target_weight,
            current_weight=user.weight
        )

        recommendations = engine.get_recommendations(
            weight_history=weight_history,
            calorie_history=calorie_history,
            water_today=water_today
        )

        return [
            RecommendationResponse(
                type=r.type.value,
                title=r.title,
                message=r.message,
                priority=r.priority,
                action_text=r.action_text,
                adjustment_value=r.adjustment_value
            )
            for r in recommendations[:5]  # Максимум 5 рекомендаций
        ]


@router.post("/water")
async def add_water(request: LogWaterRequest):
    """
    Добавить воду
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, request.telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        stats = await log_water(db, user.id, request.ml)

        return {
            "success": True,
            "total_water": stats.water_ml
        }


@router.post("/weight")
async def add_weight(request: LogWeightRequest):
    """
    Записать вес
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, request.telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        stats = await log_weight(db, user.id, request.weight)

        # Также обновляем текущий вес пользователя
        user.weight = request.weight
        await db.commit()

        return {
            "success": True,
            "weight": stats.weight_log
        }


@router.get("/meal-plan/{telegram_id}")
async def get_meal_plan(telegram_id: int):
    """
    Получить распределение калорий по приёмам пищи на сегодня
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        daily_calories = user.daily_calories or 2000

        # Распределение по приёмам
        meal_plan = distribute_meals(daily_calories, meals_count=4)

        # Что уже съедено по типам
        entries = await get_user_food_entries_by_date(db, user.id, date.today())

        eaten_by_meal = {
            "breakfast": 0,
            "lunch": 0,
            "dinner": 0,
            "snack": 0
        }

        for e in entries:
            if e.meal_type in eaten_by_meal:
                eaten_by_meal[e.meal_type] += e.calories

        # Формируем результат
        result = {}
        meal_names = {
            "breakfast": "🌅 Завтрак",
            "lunch": "☀️ Обед",
            "snack": "🍎 Перекус",
            "dinner": "🌆 Ужин"
        }

        for meal, target in meal_plan.items():
            eaten = eaten_by_meal.get(meal, 0)
            result[meal] = {
                "name": meal_names.get(meal, meal),
                "target": target,
                "eaten": eaten,
                "remaining": max(0, target - eaten),
                "percent": min(100, int((eaten / target) * 100)) if target > 0 else 0
            }

        return result


@router.get("/reminder/{telegram_id}")
async def get_meal_reminder(telegram_id: int):
    """
    Получить напоминание о приёме пищи (если есть)
    """
    from datetime import datetime

    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        stats = await get_or_create_daily_stats(db, user.id, date.today())

        current_hour = datetime.now().hour

        reminder = get_meal_reminders(
            daily_calories=user.daily_calories or 2000,
            eaten_calories=stats.total_calories,
            current_hour=current_hour
        )

        return {
            "has_reminder": reminder is not None,
            "message": reminder
        }


@router.get("/motivation/{telegram_id}")
async def get_motivation_message(telegram_id: int):
    """
    Получить мотивационное сообщение от AI
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        weekly = await get_weekly_stats(db, user.id)

        # Собираем статистику для AI
        user_stats = {
            "goal": user.goal.value if user.goal else "maintain",
            "days_tracked": len(weekly),
            "avg_calories": sum(s.total_calories for s in weekly) / len(weekly) if weekly else 0,
            "target_calories": user.daily_calories or 2000,
            "weight_change": 0,
            "weight_days": 7,
            "streak": 0
        }

        # Считаем изменение веса
        weights = [(s.stats_date, s.weight_log) for s in weekly if s.weight_log]
        if len(weights) >= 2:
            weights.sort(key=lambda x: x[0])
            user_stats["weight_change"] = weights[-1][1] - weights[0][1]
            user_stats["weight_days"] = (weights[-1][0] - weights[0][0]).days or 1

        # Считаем streak
        check_date = date.today()
        dates_set = {s.stats_date for s in weekly}
        while check_date in dates_set:
            user_stats["streak"] += 1
            check_date -= timedelta(days=1)

        message = await get_ai_motivation(user_stats)

        return {"message": message}


@router.get("/weight-history/{telegram_id}")
async def get_weight_history(telegram_id: int, days: int = 30):
    """
    История веса за N дней
    """
    from sqlalchemy import select, and_

    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        from database.models import DailyStats

        cutoff = date.today() - timedelta(days=days)

        result = await db.execute(
            select(DailyStats)
            .where(and_(
                DailyStats.user_id == user.id,
                DailyStats.stats_date >= cutoff,
                DailyStats.weight_log.isnot(None)
            ))
            .order_by(DailyStats.stats_date)
        )
        stats = result.scalars().all()

        return [
            {
                "date": s.stats_date.isoformat(),
                "weight": s.weight_log
            }
            for s in stats
        ]
