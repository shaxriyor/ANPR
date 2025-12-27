"""
🧠 Recommendation Engine
Адаптивная система рекомендаций на основе прогресса пользователя
"""

from datetime import date, timedelta
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class RecommendationType(Enum):
    INCREASE_CALORIES = "increase_calories"
    DECREASE_CALORIES = "decrease_calories"
    MAINTAIN = "maintain"
    INCREASE_PROTEIN = "increase_protein"
    DRINK_WATER = "drink_water"
    LOG_WEIGHT = "log_weight"
    KEEP_STREAK = "keep_streak"
    MOTIVATION = "motivation"


@dataclass
class Recommendation:
    type: RecommendationType
    title: str
    message: str
    priority: int  # 1-5, 5 = highest
    action_text: Optional[str] = None
    adjustment_value: Optional[int] = None  # калории для корректировки


class RecommendationEngine:
    """
    Движок рекомендаций, анализирующий прогресс пользователя
    """

    def __init__(
        self,
        user_goal: str,  # lose, maintain, gain
        target_calories: int,
        target_weight: Optional[float] = None,
        current_weight: Optional[float] = None
    ):
        self.goal = user_goal
        self.target_calories = target_calories
        self.target_weight = target_weight
        self.current_weight = current_weight

    def analyze_weight_trend(
        self,
        weight_history: List[Tuple[date, float]],  # [(date, weight), ...]
        days: int = 14
    ) -> dict:
        """
        Анализ тренда веса за последние N дней

        Returns:
            {
                "trend": "up" | "down" | "stable",
                "change_kg": float,
                "change_per_week": float,
                "days_analyzed": int
            }
        """
        if len(weight_history) < 2:
            return {
                "trend": "unknown",
                "change_kg": 0,
                "change_per_week": 0,
                "days_analyzed": 0
            }

        # Сортируем по дате
        sorted_history = sorted(weight_history, key=lambda x: x[0])

        # Берём последние N дней
        cutoff = date.today() - timedelta(days=days)
        recent = [(d, w) for d, w in sorted_history if d >= cutoff]

        if len(recent) < 2:
            return {
                "trend": "unknown",
                "change_kg": 0,
                "change_per_week": 0,
                "days_analyzed": len(recent)
            }

        first_weight = recent[0][1]
        last_weight = recent[-1][1]
        days_between = (recent[-1][0] - recent[0][0]).days or 1

        change_kg = last_weight - first_weight
        change_per_week = (change_kg / days_between) * 7

        if abs(change_per_week) < 0.2:  # Менее 200г в неделю = стабильно
            trend = "stable"
        elif change_kg > 0:
            trend = "up"
        else:
            trend = "down"

        return {
            "trend": trend,
            "change_kg": round(change_kg, 2),
            "change_per_week": round(change_per_week, 2),
            "days_analyzed": len(recent)
        }

    def analyze_calorie_adherence(
        self,
        daily_calories: List[Tuple[date, int]],  # [(date, calories), ...]
        days: int = 7
    ) -> dict:
        """
        Анализ соблюдения калорийности

        Returns:
            {
                "avg_calories": int,
                "deviation_percent": float,
                "over_days": int,  # дни с превышением
                "under_days": int,  # дни с недобором
                "streak": int  # дней подряд с записями
            }
        """
        if not daily_calories:
            return {
                "avg_calories": 0,
                "deviation_percent": 0,
                "over_days": 0,
                "under_days": 0,
                "streak": 0
            }

        cutoff = date.today() - timedelta(days=days)
        recent = [(d, c) for d, c in daily_calories if d >= cutoff]

        if not recent:
            return {
                "avg_calories": 0,
                "deviation_percent": 0,
                "over_days": 0,
                "under_days": 0,
                "streak": 0
            }

        avg = sum(c for _, c in recent) / len(recent)
        deviation = ((avg - self.target_calories) / self.target_calories) * 100

        over_days = sum(1 for _, c in recent if c > self.target_calories * 1.1)
        under_days = sum(1 for _, c in recent if c < self.target_calories * 0.7)

        # Считаем streak (дни подряд)
        streak = 0
        check_date = date.today()
        dates_set = {d for d, _ in daily_calories}
        while check_date in dates_set:
            streak += 1
            check_date -= timedelta(days=1)

        return {
            "avg_calories": int(avg),
            "deviation_percent": round(deviation, 1),
            "over_days": over_days,
            "under_days": under_days,
            "streak": streak
        }

    def get_recommendations(
        self,
        weight_history: List[Tuple[date, float]],
        calorie_history: List[Tuple[date, int]],
        water_today: int = 0
    ) -> List[Recommendation]:
        """
        Получить список рекомендаций на основе данных

        Returns:
            Список рекомендаций, отсортированных по приоритету
        """
        recommendations = []

        weight_analysis = self.analyze_weight_trend(weight_history)
        calorie_analysis = self.analyze_calorie_adherence(calorie_history)

        # === Рекомендации по весу ===

        if self.goal == "lose":
            # Цель - похудение
            if weight_analysis["trend"] == "stable" and weight_analysis["days_analyzed"] >= 10:
                # Вес стоит на месте 10+ дней
                recommendations.append(Recommendation(
                    type=RecommendationType.DECREASE_CALORIES,
                    title="⚡ Плато веса",
                    message=(
                        f"Вес стабилен уже {weight_analysis['days_analyzed']} дней. "
                        "Рекомендую снизить калории на 100-150 ккал или добавить активности."
                    ),
                    priority=5,
                    action_text="Снизить норму",
                    adjustment_value=-100
                ))
            elif weight_analysis["trend"] == "down" and weight_analysis["change_per_week"] < -1.0:
                # Слишком быстрое похудение (> 1 кг/неделю)
                recommendations.append(Recommendation(
                    type=RecommendationType.INCREASE_CALORIES,
                    title="⚠️ Слишком быстро",
                    message=(
                        f"Ты теряешь {abs(weight_analysis['change_per_week'])} кг в неделю. "
                        "Это может привести к потере мышц. Добавь 150-200 ккал."
                    ),
                    priority=4,
                    action_text="Увеличить норму",
                    adjustment_value=150
                ))
            elif weight_analysis["trend"] == "down" and -0.3 <= weight_analysis["change_per_week"] <= -0.8:
                # Идеальный темп похудения
                recommendations.append(Recommendation(
                    type=RecommendationType.MOTIVATION,
                    title="🎯 Отличный прогресс!",
                    message=(
                        f"Ты теряешь {abs(weight_analysis['change_per_week'])} кг в неделю - "
                        "это здоровый темп! Продолжай в том же духе."
                    ),
                    priority=2
                ))

        elif self.goal == "gain":
            # Цель - набор массы
            if weight_analysis["trend"] == "stable" and weight_analysis["days_analyzed"] >= 10:
                # Вес не растёт
                recommendations.append(Recommendation(
                    type=RecommendationType.INCREASE_CALORIES,
                    title="📈 Нужно больше калорий",
                    message=(
                        f"Вес стабилен {weight_analysis['days_analyzed']} дней. "
                        "Добавь 200-250 ккал для набора массы."
                    ),
                    priority=5,
                    action_text="Увеличить норму",
                    adjustment_value=200
                ))
            elif weight_analysis["trend"] == "up" and weight_analysis["change_per_week"] > 0.5:
                # Слишком быстрый набор
                recommendations.append(Recommendation(
                    type=RecommendationType.DECREASE_CALORIES,
                    title="⚠️ Набираешь жир",
                    message=(
                        f"+{weight_analysis['change_per_week']} кг/неделю - слишком быстро. "
                        "Снизь калории на 150 ккал, чтобы набирать качественно."
                    ),
                    priority=4,
                    action_text="Снизить норму",
                    adjustment_value=-150
                ))

        # === Рекомендации по калориям ===

        if calorie_analysis["under_days"] >= 3:
            recommendations.append(Recommendation(
                type=RecommendationType.MOTIVATION,
                title="🍽 Ешь больше!",
                message=(
                    f"За последнюю неделю {calorie_analysis['under_days']} дней с недобором. "
                    "Хронический дефицит замедляет метаболизм."
                ),
                priority=3
            ))

        if calorie_analysis["over_days"] >= 3 and self.goal == "lose":
            recommendations.append(Recommendation(
                type=RecommendationType.MOTIVATION,
                title="📊 Перебор калорий",
                message=(
                    f"{calorie_analysis['over_days']} дней с превышением нормы. "
                    "Попробуй более сытные низкокалорийные продукты."
                ),
                priority=3
            ))

        # === Напоминание о воде ===
        if water_today < 1500:
            recommendations.append(Recommendation(
                type=RecommendationType.DRINK_WATER,
                title="💧 Пей воду",
                message=f"Сегодня выпито только {water_today} мл. Цель - минимум 2 литра!",
                priority=2,
                action_text="Добавить воду"
            ))

        # === Streak и мотивация ===
        if calorie_analysis["streak"] >= 7:
            recommendations.append(Recommendation(
                type=RecommendationType.KEEP_STREAK,
                title="🔥 Серия!",
                message=f"Ты записываешь еду {calorie_analysis['streak']} дней подряд! Не сбивайся!",
                priority=1
            ))
        elif calorie_analysis["streak"] == 0:
            recommendations.append(Recommendation(
                type=RecommendationType.MOTIVATION,
                title="📝 Начни сегодня",
                message="Запиши первый приём пищи и начни новую серию!",
                priority=3
            ))

        # === Напоминание взвеситься ===
        if weight_history:
            last_weight_date = max(d for d, _ in weight_history)
            days_since_weight = (date.today() - last_weight_date).days
            if days_since_weight >= 7:
                recommendations.append(Recommendation(
                    type=RecommendationType.LOG_WEIGHT,
                    title="⚖️ Взвесься",
                    message=f"Прошло {days_since_weight} дней с последнего взвешивания.",
                    priority=2,
                    action_text="Записать вес"
                ))

        # Сортируем по приоритету
        recommendations.sort(key=lambda r: -r.priority)

        return recommendations

    def calculate_adjusted_calories(
        self,
        weight_history: List[Tuple[date, float]],
        adjustment_type: RecommendationType
    ) -> int:
        """
        Рассчитать новую норму калорий
        """
        weight_analysis = self.analyze_weight_trend(weight_history)

        if adjustment_type == RecommendationType.INCREASE_CALORIES:
            # Адаптивное увеличение
            if self.goal == "gain" and weight_analysis["trend"] == "stable":
                return self.target_calories + 200
            else:
                return self.target_calories + 100

        elif adjustment_type == RecommendationType.DECREASE_CALORIES:
            if self.goal == "lose" and weight_analysis["trend"] == "stable":
                return self.target_calories - 100
            else:
                return self.target_calories - 50

        return self.target_calories


def get_meal_reminders(
    daily_calories: int,
    eaten_calories: int,
    current_hour: int
) -> Optional[str]:
    """
    Получить напоминание о приёме пищи

    Args:
        daily_calories: дневная норма
        eaten_calories: уже съедено
        current_hour: текущий час (0-23)
    """
    remaining = daily_calories - eaten_calories

    if remaining <= 0:
        return None

    # Утро (7-10)
    if 7 <= current_hour < 10:
        if eaten_calories == 0:
            breakfast_cal = int(daily_calories * 0.25)
            return f"🌅 Доброе утро! Время завтрака. Рекомендую ~{breakfast_cal} ккал."

    # Обед (12-14)
    elif 12 <= current_hour < 14:
        if eaten_calories < daily_calories * 0.3:
            lunch_cal = int(daily_calories * 0.35)
            return f"☀️ Время обеда! Осталось {remaining} ккал. Обед ~{lunch_cal} ккал."

    # Полдник (16-17)
    elif 16 <= current_hour < 17:
        if daily_calories * 0.3 < eaten_calories < daily_calories * 0.7:
            snack_cal = int(daily_calories * 0.15)
            return f"🍎 Время перекуса! ~{snack_cal} ккал поможет дотянуть до ужина."

    # Ужин (18-20)
    elif 18 <= current_hour < 20:
        if remaining > daily_calories * 0.2:
            return f"🌆 Время ужина! Осталось {remaining} ккал на сегодня."

    # Вечер (после 21)
    elif current_hour >= 21:
        if remaining > 300:
            return f"🌙 Не забудь поужинать! Осталось {remaining} ккал."

    return None
