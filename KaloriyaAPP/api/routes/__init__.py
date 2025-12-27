from .food import router as food_router
from .user import router as user_router
from .stats import router as stats_router

__all__ = ["food_router", "user_router", "stats_router"]
