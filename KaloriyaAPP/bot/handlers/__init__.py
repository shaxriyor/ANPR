from .start import router as start_router
from .food import router as food_router
from .profile import router as profile_router
from .stats import router as stats_router

__all__ = ["start_router", "food_router", "profile_router", "stats_router"]
