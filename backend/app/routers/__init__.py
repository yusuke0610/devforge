from .auth import router as auth_router
from .blog import router as blog_router
from .career_analysis import router as career_analysis_router
from .health import router as health_router
from .intelligence import router as intelligence_router
from .internal import router as internal_router
from .master_data import router as master_data_router
from .notifications import router as notifications_router
from .resumes import router as resumes_router

__all__ = [
    "auth_router",
    "career_analysis_router",
    "blog_router",
    "health_router",
    "intelligence_router",
    "internal_router",
    "master_data_router",
    "notifications_router",
    "resumes_router",
]
