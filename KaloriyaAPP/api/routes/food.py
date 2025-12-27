from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import async_session
from database.crud import (
    get_user_by_telegram_id,
    create_food_entry,
    get_user_food_entries_by_date,
    delete_food_entry
)
from api.services.gemini import analyze_food_image, get_food_suggestions

router = APIRouter(prefix="/food", tags=["food"])


# === Pydantic Models ===

class AnalyzeRequest(BaseModel):
    image_base64: str
    telegram_id: int


class AnalyzeResponse(BaseModel):
    food_name: str
    food_name_ru: Optional[str]
    calories: int
    protein: float
    carbs: float
    fat: float
    portion_size: float
    portion_description: str
    ingredients: List[str]
    confidence: float
    health_notes: str


class AddFoodRequest(BaseModel):
    telegram_id: int
    food_name: str
    food_name_ru: Optional[str] = None
    calories: int
    protein: float
    carbs: float
    fat: float
    portion_size: float = 100
    portion_description: Optional[str] = None
    meal_type: Optional[str] = None
    photo_url: Optional[str] = None


class FoodEntryResponse(BaseModel):
    id: int
    food_name: str
    food_name_ru: Optional[str]
    calories: int
    protein: float
    carbs: float
    fat: float
    portion_description: Optional[str]
    meal_type: Optional[str]
    logged_at: str


class SearchRequest(BaseModel):
    query: str


# === Endpoints ===

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_food(request: AnalyzeRequest):
    """
    Анализ фото еды через Gemini Vision
    """
    try:
        result = await analyze_food_image(request.image_base64)
        return AnalyzeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_food_entry(request: AddFoodRequest):
    """
    Добавить запись о еде
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, request.telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        entry = await create_food_entry(
            db=db,
            user_id=user.id,
            food_name=request.food_name,
            food_name_ru=request.food_name_ru,
            calories=request.calories,
            protein=request.protein,
            carbs=request.carbs,
            fat=request.fat,
            portion_size=request.portion_size,
            portion_description=request.portion_description,
            meal_type=request.meal_type,
            photo_url=request.photo_url
        )

        return {
            "success": True,
            "entry_id": entry.id,
            "message": "Food entry added"
        }


@router.get("/today/{telegram_id}", response_model=List[FoodEntryResponse])
async def get_today_entries(telegram_id: int):
    """
    Получить записи о еде за сегодня
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        entries = await get_user_food_entries_by_date(db, user.id, date.today())

        return [
            FoodEntryResponse(
                id=e.id,
                food_name=e.food_name,
                food_name_ru=e.food_name_ru,
                calories=e.calories,
                protein=e.protein,
                carbs=e.carbs,
                fat=e.fat,
                portion_description=e.portion_description,
                meal_type=e.meal_type,
                logged_at=e.logged_at.isoformat()
            )
            for e in entries
        ]


@router.get("/history/{telegram_id}")
async def get_food_history(telegram_id: int, days: int = 7):
    """
    Получить историю еды за N дней
    """
    from datetime import timedelta

    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        history = {}
        for i in range(days):
            entry_date = date.today() - timedelta(days=i)
            entries = await get_user_food_entries_by_date(db, user.id, entry_date)
            if entries:
                history[entry_date.isoformat()] = [
                    {
                        "id": e.id,
                        "food_name": e.food_name_ru or e.food_name,
                        "calories": e.calories,
                        "meal_type": e.meal_type,
                        "logged_at": e.logged_at.strftime("%H:%M")
                    }
                    for e in entries
                ]

        return history


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int, telegram_id: int):
    """
    Удалить запись о еде
    """
    async with async_session() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        success = await delete_food_entry(db, entry_id, user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found")

        return {"success": True, "message": "Entry deleted"}


@router.post("/search")
async def search_food(request: SearchRequest):
    """
    Поиск еды по названию (через AI)
    """
    try:
        suggestions = await get_food_suggestions(request.query)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
