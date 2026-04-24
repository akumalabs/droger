from .auth import router as auth_router
from .tokens import router as tokens_router
from .do_proxy import router as do_proxy_router
from .windows import router as windows_router
from .wizard import router as wizard_router
from .templates import router as templates_router

__all__ = [
    "auth_router",
    "tokens_router",
    "do_proxy_router",
    "windows_router",
    "wizard_router",
    "templates_router",
]
