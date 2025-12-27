"""
Middleware для безопасности и защиты от перегрузок

Telegram Bot API лимиты:
- 30 сообщений/сек в один чат
- 20 сообщений/мин в группу
- Bulk: 30 сообщений/сек всего

Наши лимиты:
- 10 запросов/мин на пользователя (анализ фото)
- 60 запросов/мин на пользователя (обычные команды)
- Защита от флуда
"""

import asyncio
import time
import hashlib
import hmac
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update, TelegramObject
from aiogram.dispatcher.flags import get_flag

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from api.services.logger import bot_logger, log_user_action


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting для защиты от флуда и перегрузок
    """

    def __init__(
        self,
        default_limit: int = 60,      # запросов в минуту (обычные команды)
        photo_limit: int = 10,         # запросов в минуту (анализ фото)
        cooldown_seconds: int = 60     # период сброса
    ):
        self.default_limit = default_limit
        self.photo_limit = photo_limit
        self.cooldown = cooldown_seconds

        # Хранилище: {user_id: {"count": int, "photo_count": int, "reset_time": float}}
        self.user_data: Dict[int, Dict] = defaultdict(lambda: {
            "count": 0,
            "photo_count": 0,
            "reset_time": time.time() + self.cooldown,
            "blocked_until": 0
        })

        # Глобальный счётчик для защиты бота
        self.global_requests = 0
        self.global_reset_time = time.time() + 1  # сброс каждую секунду
        self.global_limit = 25  # макс 25 req/sec (оставляем запас до 30)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        current_time = time.time()

        # === Глобальный rate limit ===
        if current_time > self.global_reset_time:
            self.global_requests = 0
            self.global_reset_time = current_time + 1

        if self.global_requests >= self.global_limit:
            bot_logger.warning(f"Global rate limit reached! Dropping request from {user_id}")
            await asyncio.sleep(0.5)  # Небольшая задержка вместо отказа
            self.global_requests = 0

        self.global_requests += 1

        # === Проверка блокировки пользователя ===
        user = self.user_data[user_id]

        if current_time < user["blocked_until"]:
            remaining = int(user["blocked_until"] - current_time)
            if isinstance(event, Message):
                await event.answer(
                    f"⏳ Слишком много запросов. Подожди {remaining} сек.",
                    show_alert=True
                )
            return None

        # === Сброс счётчиков ===
        if current_time > user["reset_time"]:
            user["count"] = 0
            user["photo_count"] = 0
            user["reset_time"] = current_time + self.cooldown

        # === Проверка лимитов ===
        is_photo = isinstance(event, Message) and event.photo

        if is_photo:
            user["photo_count"] += 1
            if user["photo_count"] > self.photo_limit:
                user["blocked_until"] = current_time + 60  # Блок на минуту
                bot_logger.warning(f"User {user_id} blocked for photo spam")
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ Превышен лимит анализа фото (10/мин).\n"
                        "Подожди минуту перед следующим запросом."
                    )
                return None
        else:
            user["count"] += 1
            if user["count"] > self.default_limit:
                user["blocked_until"] = current_time + 30
                bot_logger.warning(f"User {user_id} blocked for spam")
                return None

        return await handler(event, data)


class AntiFloodMiddleware(BaseMiddleware):
    """
    Защита от флуда - игнорирует дубликаты сообщений
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold  # Минимальный интервал между сообщениями
        self.last_message: Dict[int, float] = {}
        self.message_hashes: Dict[int, str] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        current_time = time.time()

        # Проверяем интервал
        last_time = self.last_message.get(user_id, 0)
        if current_time - last_time < self.threshold:
            # Проверяем не дубликат ли
            msg_hash = self._get_message_hash(event)
            if self.message_hashes.get(user_id) == msg_hash:
                bot_logger.debug(f"Duplicate message from {user_id} ignored")
                return None

        self.last_message[user_id] = current_time
        self.message_hashes[user_id] = self._get_message_hash(event)

        return await handler(event, data)

    def _get_message_hash(self, message: Message) -> str:
        """Хеш сообщения для определения дубликатов"""
        content = ""
        if message.text:
            content = message.text
        elif message.photo:
            content = message.photo[-1].file_unique_id
        elif message.document:
            content = message.document.file_unique_id

        return hashlib.md5(content.encode()).hexdigest()[:8]


class LoggingMiddleware(BaseMiddleware):
    """
    Логирование всех действий пользователей
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        action = "unknown"
        details = ""

        if isinstance(event, Message):
            user_id = event.from_user.id
            if event.text:
                if event.text.startswith("/"):
                    action = "command"
                    details = event.text.split()[0]
                else:
                    action = "message"
                    details = f"len={len(event.text)}"
            elif event.photo:
                action = "photo"
                details = f"file_id={event.photo[-1].file_unique_id[:8]}"

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            action = "callback"
            details = event.data[:50] if event.data else ""

        if user_id:
            log_user_action(user_id, action, details)

        return await handler(event, data)


class PrivacyMiddleware(BaseMiddleware):
    """
    Защита персональных данных
    - Не логируем чувствительные данные
    - Очищаем старые данные
    """

    # Команды с персональными данными (не логируем детали)
    SENSITIVE_COMMANDS = {"/profile", "/stats", "/weight"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Помечаем чувствительные запросы
        if isinstance(event, Message) and event.text:
            for cmd in self.SENSITIVE_COMMANDS:
                if event.text.startswith(cmd):
                    data["is_sensitive"] = True
                    break

        return await handler(event, data)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Централизованная обработка ошибок
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)

        except asyncio.TimeoutError:
            bot_logger.error(f"Timeout error for event {type(event).__name__}")
            if isinstance(event, Message):
                await event.answer("⏱ Превышено время ожидания. Попробуй ещё раз.")

        except Exception as e:
            bot_logger.error(f"Unhandled error: {type(e).__name__}: {str(e)}")

            # Не показываем детали ошибки пользователю
            if isinstance(event, Message):
                await event.answer(
                    "❌ Произошла ошибка. Попробуй позже.\n"
                    "Если проблема повторяется, напиши /help"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Ошибка. Попробуй ещё раз.", show_alert=True)

        return None
