"""
Запуск KaloriyaBot
Одновременный запуск Telegram бота и FastAPI сервера
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main as run_bot
from api.main import app
import uvicorn


async def run_api():
    """Запуск FastAPI сервера"""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Запуск бота и API параллельно"""
    print("🚀 Запуск KaloriyaBot...")
    print("=" * 50)

    # Запускаем бота и API параллельно
    await asyncio.gather(
        run_bot(),
        run_api()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 KaloriyaBot остановлен")
