from .agent import router as agent_router
from .auth import router as auth_router
from .billing import router as billing_router
from .blog import router as blog_router
from .github_link import router as github_link_router
from .health import router as health_router
from .internal import router as internal_router
from .master_data import router as master_data_router
from .notifications import router as notifications_router
from .resumes import router as resumes_router

__all__ = [
    "agent_router",
    "auth_router",
    "billing_router",
    "blog_router",
    "github_link_router",
    "health_router",
    "internal_router",
    "master_data_router",
    "notifications_router",
    "resumes_router",
]
