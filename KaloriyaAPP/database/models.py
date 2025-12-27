from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Enum, BigInteger
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, date
import enum


class Base(DeclarativeBase):
    pass


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"


class Goal(enum.Enum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class ActivityLevel(enum.Enum):
    SEDENTARY = "sedentary"          # Сидячий образ жизни
    LIGHT = "light"                   # Лёгкая активность 1-3 раза в неделю
    MODERATE = "moderate"             # Умеренная активность 3-5 раз в неделю
    ACTIVE = "active"                 # Высокая активность 6-7 раз в неделю
    VERY_ACTIVE = "very_active"       # Очень высокая активность


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)

    # Физические данные
    weight = Column(Float, nullable=True)  # кг
    height = Column(Float, nullable=True)  # см
    age = Column(Integer, nullable=True)
    gender = Column(Enum(Gender), nullable=True)

    # Цели
    goal = Column(Enum(Goal), default=Goal.MAINTAIN)
    activity_level = Column(Enum(ActivityLevel), default=ActivityLevel.MODERATE)
    target_weight = Column(Float, nullable=True)

    # Рассчитанные значения КБЖУ
    daily_calories = Column(Integer, nullable=True)
    daily_protein = Column(Integer, nullable=True)   # граммы
    daily_carbs = Column(Integer, nullable=True)     # граммы
    daily_fat = Column(Integer, nullable=True)       # граммы

    # Мета
    is_registered = Column(Integer, default=0)  # 0 - не завершил регистрацию
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    food_entries = relationship("FoodEntry", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")


class FoodEntry(Base):
    __tablename__ = "food_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Информация о еде
    food_name = Column(String(500), nullable=False)
    food_name_ru = Column(String(500), nullable=True)  # Название на русском
    photo_url = Column(String(1000), nullable=True)

    # Нутриенты
    calories = Column(Integer, nullable=False)
    protein = Column(Float, nullable=False)   # граммы
    carbs = Column(Float, nullable=False)     # граммы
    fat = Column(Float, nullable=False)       # граммы

    # Порция
    portion_size = Column(Float, default=100)  # граммы
    portion_description = Column(String(255), nullable=True)  # "1 тарелка", "200г"

    # Время
    meal_type = Column(String(50), nullable=True)  # breakfast, lunch, dinner, snack
    logged_at = Column(DateTime, default=datetime.utcnow)
    entry_date = Column(Date, default=date.today)

    # Связь
    user = relationship("User", back_populates="food_entries")


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stats_date = Column(Date, nullable=False, default=date.today)

    # Итоги за день
    total_calories = Column(Integer, default=0)
    total_protein = Column(Float, default=0)
    total_carbs = Column(Float, default=0)
    total_fat = Column(Float, default=0)

    # Вода
    water_ml = Column(Integer, default=0)

    # Вес (если пользователь записал)
    weight_log = Column(Float, nullable=True)

    # Связь
    user = relationship("User", back_populates="daily_stats")

    class Meta:
        unique_together = ("user_id", "stats_date")
