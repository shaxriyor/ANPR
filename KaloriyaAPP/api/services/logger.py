"""
Централизованное логирование для KaloriyaBot
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


# Директория для логов
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Создать логгер с выводом в файл и консоль

    Args:
        name: имя логгера
        level: уровень логирования

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый хендлер с ротацией (макс 5MB, 5 файлов)
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, f"{name}.log"),
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Добавляем хендлеры если их ещё нет
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# === Готовые логгеры ===

# Основной логгер приложения
app_logger = setup_logger("kaloriya_app")

# Логгер для API запросов
api_logger = setup_logger("kaloriya_api")

# Логгер для Gemini AI
ai_logger = setup_logger("kaloriya_ai")

# Логгер для базы данных
db_logger = setup_logger("kaloriya_db")

# Логгер для бота
bot_logger = setup_logger("kaloriya_bot")


def log_api_request(
    endpoint: str,
    method: str,
    telegram_id: int = None,
    data: dict = None,
    response_status: int = None,
    duration_ms: float = None
):
    """Логировать API запрос"""
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "telegram_id": telegram_id,
        "status": response_status,
        "duration_ms": duration_ms
    }
    api_logger.info(f"API Request: {log_data}")


def log_food_recognition(
    telegram_id: int,
    food_name: str,
    calories: int,
    confidence: float,
    cached: bool = False,
    duration_ms: float = None
):
    """Логировать распознавание еды"""
    ai_logger.info(
        f"Food Recognition | user={telegram_id} | food={food_name} | "
        f"cal={calories} | conf={confidence:.2f} | cached={cached} | "
        f"duration={duration_ms:.0f}ms" if duration_ms else ""
    )


def log_user_action(
    telegram_id: int,
    action: str,
    details: str = None
):
    """Логировать действие пользователя"""
    bot_logger.info(
        f"User Action | user={telegram_id} | action={action} | details={details}"
    )


def log_db_operation(
    operation: str,
    table: str,
    user_id: int = None,
    success: bool = True,
    error: str = None
):
    """Логировать операцию с БД"""
    if success:
        db_logger.info(f"DB {operation} | table={table} | user_id={user_id}")
    else:
        db_logger.error(f"DB {operation} FAILED | table={table} | user_id={user_id} | error={error}")


def log_error(
    component: str,
    error: Exception,
    context: dict = None
):
    """Логировать ошибку"""
    app_logger.error(
        f"ERROR in {component} | type={type(error).__name__} | "
        f"message={str(error)} | context={context}"
    )


def log_cache_event(
    action: str,  # hit, miss, set
    key: str,
    details: str = None
):
    """Логировать события кеша"""
    if action == "hit":
        ai_logger.debug(f"Cache HIT | key={key}")
    elif action == "miss":
        ai_logger.debug(f"Cache MISS | key={key}")
    elif action == "set":
        ai_logger.debug(f"Cache SET | key={key} | {details}")
