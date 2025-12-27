"""
KaloriyaBot - Telegram бот для подсчёта калорий

Защита:
- Rate limiting (10 фото/мин, 60 команд/мин)
- Anti-flood (защита от дубликатов)
- Error handling (graceful degradation)
- Logging (все действия логируются)
"""

import asyncio
import logging
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from config import get_settings
from database.connection import init_db
from bot.handlers import start_router, food_router, profile_router, stats_router
from bot.middlewares.security import (
    RateLimitMiddleware,
    AntiFloodMiddleware,
    LoggingMiddleware,
    ErrorHandlerMiddleware
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Уменьшаем логи от библиотек
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Bot starting up...")

    # Устанавливаем команды бота
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="🚀 Начать"),
        BotCommand(command="menu", description="📱 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands set")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot shutting down...")
    await bot.session.close()


async def main():
    settings = get_settings()

    # Инициализация базы данных
    logger.info("Initializing database...")
    try:
        await init_db()
        logger.info("Database initialized!")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return

    # Создаём сессию с таймаутами
    session = AiohttpSession(
        timeout=60  # 60 секунд таймаут
    )

    # Создаём бота
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    # Хранилище состояний (FSM)
    storage = MemoryStorage()

    # Создаём диспетчер
    dp = Dispatcher(storage=storage)

    # === Регистрируем middleware (порядок важен!) ===

    # 1. Обработка ошибок (внешний слой)
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())

    # 2. Логирование
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # 3. Anti-flood
    dp.message.middleware(AntiFloodMiddleware(threshold=0.3))

    # 4. Rate limiting
    dp.message.middleware(RateLimitMiddleware(
        default_limit=60,   # 60 команд/мин
        photo_limit=10,     # 10 фото/мин
        cooldown_seconds=60
    ))
    dp.callback_query.middleware(RateLimitMiddleware(
        default_limit=120,  # Callback'и чаще
        photo_limit=10,
        cooldown_seconds=60
    ))

    # === Регистрируем роутеры ===
    dp.include_router(start_router)
    dp.include_router(food_router)
    dp.include_router(profile_router)
    dp.include_router(stats_router)

    # === Регистрируем startup/shutdown ===
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Удаляем вебхук и старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Bot started!")
    print("=" * 50)
    print("🤖 KaloriyaBot запущен!")
    print("=" * 50)
    print("Лимиты:")
    print("  • 60 команд/мин на пользователя")
    print("  • 10 фото/мин на пользователя")
    print("=" * 50)
    print("Нажми Ctrl+C для остановки")

    try:
        # Polling с параметрами надёжности
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            polling_timeout=30,  # Таймаут long polling
        )
    except asyncio.CancelledError:
        logger.info("Polling cancelled")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
