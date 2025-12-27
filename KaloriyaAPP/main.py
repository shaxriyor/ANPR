"""
KaloriyaBot - Telegram бот для подсчёта калорий с AI распознаванием еды

Запуск:
    python main.py           # Только бот
    python run.py            # Бот + API сервер

Требуется .env файл с:
    TELEGRAM_BOT_TOKEN
    GOOGLE_API_KEY
    DATABASE_URL
    WEBAPP_URL
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
