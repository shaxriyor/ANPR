from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import init_db
from api.routes import food_router, user_router, stats_router
from api.middlewares.security import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    TelegramValidationMiddleware
)
from api.services.logger import api_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    api_logger.info("Starting KaloriyaBot API...")
    await init_db()
    api_logger.info("Database initialized")
    yield
    # Shutdown
    api_logger.info("Shutting down...")


app = FastAPI(
    title="KaloriyaBot API",
    description="API для Telegram бота подсчёта калорий",
    version="1.0.0",
    lifespan=lifespan
)

# === Security Middleware (порядок важен!) ===

# 1. Security Headers - добавляет защитные заголовки
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request Logging - логирует все запросы
app.add_middleware(RequestLoggingMiddleware)

# 3. Rate Limiting - ограничение запросов (100/мин на IP)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# 4. Telegram Validation - проверка подписи от Telegram
app.add_middleware(TelegramValidationMiddleware)

# 5. CORS для Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы
webapp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
static_dir = os.path.join(webapp_dir, "static")
templates_dir = os.path.join(webapp_dir, "templates")

# Создаём директории если не существуют
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)

# API роуты
app.include_router(food_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(stats_router, prefix="/api")


# === Web App страницы ===

@app.get("/")
async def index(request: Request):
    """Главная страница Web App"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/camera")
async def camera_page(request: Request):
    """Страница камеры для фото еды"""
    return templates.TemplateResponse("camera.html", {"request": request})


@app.get("/profile/setup")
async def profile_setup_page(request: Request):
    """Страница настройки профиля"""
    return templates.TemplateResponse("profile_setup.html", {"request": request})


@app.get("/profile/edit")
async def profile_edit_page(request: Request):
    """Страница редактирования профиля"""
    return templates.TemplateResponse("profile_edit.html", {"request": request})


@app.get("/profile")
async def profile_page(request: Request):
    """Страница просмотра профиля"""
    return templates.TemplateResponse("profile.html", {"request": request})


@app.get("/diary")
async def diary_page(request: Request):
    """Страница дневника питания"""
    return templates.TemplateResponse("diary.html", {"request": request})


@app.get("/stats")
async def stats_page(request: Request):
    """Страница статистики"""
    return templates.TemplateResponse("stats.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "KaloriyaBot API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
