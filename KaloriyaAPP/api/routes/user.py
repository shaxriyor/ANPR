from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import async_session
from database.crud import (
    get_user_by_telegram_id,
    create_user,
    update_user_profile
)
from api.services.nutrition import calculate_macros

router = APIRouter(prefix="/user", tags=["user"])


# === Pydantic Models ===

class ProfileSetupRequest(BaseModel):
    telegram_id: int
    weight: float
    height: float
    age: int
    gender: str  # "male" or "female"
    goal: str  # "lose", "maintain", "gain"
    activity_level: str  # "sedentary", "light", "moderate", "active", "very_active"
    target_weight: Optional[float] = None


class ProfileResponse(BaseModel):
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    weight: Optional[float]
    height: Optional[float]
    age: Optional[int]
    gender: Optional[str]
    goal: Optional[str]
    activity_level: Optional[str]
    target_weight: Optional[float]
    daily_calories: Optional[int]
    daily_protein: Optional[int]
    daily_carbs: Optional[int]
    daily_fat: Optional[int]
    is_registered: bool


class MacrosCalculateRequest(BaseModel):
    weight: float
    height: float
    age: int
    gender: str
    goal: str
    activity_level: str


class MacrosResponse(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int
    bmr: int
    tdee: int


# === Endpoints ===

@router.get("/{telegram_id}", response_model=ProfileResponse)
async def get_profile(telegram_id: int):
    """
    Получить профиль пользователя
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return ProfileResponse(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            weight=user.weight,
            height=user.height,
            age=user.age,
            gender=user.gender.value if user.gender else None,
            goal=user.goal.value if user.goal else None,
            activity_level=user.activity_level.value if user.activity_level else None,
            target_weight=user.target_weight,
            daily_calories=user.daily_calories,
            daily_protein=user.daily_protein,
            daily_carbs=user.daily_carbs,
            daily_fat=user.daily_fat,
            is_registered=bool(user.is_registered)
        )


@router.post("/setup")
async def setup_profile(request: ProfileSetupRequest):
    """
    Настроить профиль пользователя (первичная регистрация или обновление)
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, request.telegram_id)

        if not user:
            # Создаём нового пользователя если не существует
            user = await create_user(db, request.telegram_id)

        # Обновляем профиль
        user = await update_user_profile(
            db=db,
            telegram_id=request.telegram_id,
            weight=request.weight,
            height=request.height,
            age=request.age,
            gender=request.gender,
            goal=request.goal,
            activity_level=request.activity_level,
            target_weight=request.target_weight
        )

        return {
            "success": True,
            "message": "Profile updated",
            "daily_calories": user.daily_calories,
            "daily_protein": user.daily_protein,
            "daily_carbs": user.daily_carbs,
            "daily_fat": user.daily_fat
        }


@router.post("/calculate-macros", response_model=MacrosResponse)
async def calculate_user_macros(request: MacrosCalculateRequest):
    """
    Рассчитать КБЖУ без сохранения (для предпросмотра)
    """
    result = calculate_macros(
        weight=request.weight,
        height=request.height,
        age=request.age,
        gender=request.gender,
        goal=request.goal,
        activity_level=request.activity_level
    )

    return MacrosResponse(**result)


@router.put("/{telegram_id}/calories")
async def update_calories_target(telegram_id: int, new_calories: int):
    """
    Обновить целевые калории (ручная корректировка или по рекомендации)
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Пересчитываем макросы пропорционально
        old_calories = user.daily_calories or 2000
        ratio = new_calories / old_calories

        user.daily_calories = new_calories
        user.daily_protein = int(user.daily_protein * ratio) if user.daily_protein else int(new_calories * 0.3 / 4)
        user.daily_carbs = int(user.daily_carbs * ratio) if user.daily_carbs else int(new_calories * 0.4 / 4)
        user.daily_fat = int(user.daily_fat * ratio) if user.daily_fat else int(new_calories * 0.3 / 9)

        await db.commit()

        return {
            "success": True,
            "daily_calories": user.daily_calories,
            "daily_protein": user.daily_protein,
            "daily_carbs": user.daily_carbs,
            "daily_fat": user.daily_fat
        }


@router.get("/{telegram_id}/check")
async def check_user(telegram_id: int):
    """
    Проверить существует ли пользователь и зарегистрирован ли
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)

        return {
            "exists": user is not None,
            "is_registered": bool(user.is_registered) if user else False
        }
