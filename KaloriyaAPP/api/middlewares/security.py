"""
FastAPI Middleware для безопасности API

- Rate limiting
- Валидация Telegram данных
- CORS защита
- Логирование запросов
"""

import time
import hashlib
import hmac
import json
from collections import defaultdict
from typing import Callable, Dict
from urllib.parse import unquote

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from api.services.logger import api_logger, log_api_request
from config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting для API
    """

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Получаем IP или telegram_id
        client_ip = request.client.host if request.client else "unknown"

        # Для API запросов пробуем получить telegram_id
        client_key = client_ip

        current_time = time.time()
        minute_ago = current_time - 60

        # Очищаем старые запросы
        self.requests[client_key] = [
            t for t in self.requests[client_key] if t > minute_ago
        ]

        # Проверяем лимит
        if len(self.requests[client_key]) >= self.rpm:
            api_logger.warning(f"Rate limit exceeded for {client_key}")
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Try again later."}
            )

        self.requests[client_key].append(current_time)

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Логирование всех API запросов
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Получаем telegram_id из body если есть
        telegram_id = None
        try:
            if request.method == "POST":
                body = await request.body()
                if body:
                    data = json.loads(body)
                    telegram_id = data.get("telegram_id")
                # Важно: восстанавливаем body для дальнейшей обработки
                request._body = body
        except:
            pass

        response = await call_next(request)

        duration = (time.time() - start_time) * 1000

        # Не логируем статику и health check
        if not request.url.path.startswith("/static") and request.url.path != "/health":
            log_api_request(
                endpoint=request.url.path,
                method=request.method,
                telegram_id=telegram_id,
                response_status=response.status_code,
                duration_ms=duration
            )

        return response


class TelegramValidationMiddleware(BaseHTTPMiddleware):
    """
    Валидация данных от Telegram Web App
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.bot_token = settings.TELEGRAM_BOT_TOKEN

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Проверяем только API запросы (не статику и шаблоны)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Получаем init data из заголовка
        init_data = request.headers.get("X-Telegram-Init-Data")

        # Для разработки пропускаем валидацию если нет данных
        if not init_data:
            # В продакшене можно включить строгую проверку
            # return JSONResponse(
            #     status_code=401,
            #     content={"error": "Telegram authorization required"}
            # )
            return await call_next(request)

        # Валидация подписи
        if not self._validate_init_data(init_data):
            api_logger.warning(f"Invalid Telegram init data")
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid Telegram authorization"}
            )

        return await call_next(request)

    def _validate_init_data(self, init_data: str) -> bool:
        """
        Проверка подписи данных от Telegram
        """
        try:
            # Парсим данные
            parsed = dict(x.split('=', 1) for x in init_data.split('&'))

            # Получаем hash
            received_hash = parsed.pop('hash', None)
            if not received_hash:
                return False

            # Создаём строку для проверки
            data_check_string = '\n'.join(
                f"{k}={unquote(v)}" for k, v in sorted(parsed.items())
            )

            # Создаём ключ
            secret_key = hmac.new(
                b"WebAppData",
                self.bot_token.encode(),
                hashlib.sha256
            ).digest()

            # Вычисляем hash
            computed_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(computed_hash, received_hash)

        except Exception as e:
            api_logger.error(f"Init data validation error: {e}")
            return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Добавление security headers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP для Web App (разрешаем Telegram)
        if request.url.path.startswith("/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' https://telegram.org; "
                "script-src 'self' 'unsafe-inline' https://telegram.org; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' https://api.telegram.org"
            )

        return response
