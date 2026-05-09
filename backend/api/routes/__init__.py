from .dashboard import router as dashboard_router
from .styles import router as styles_router
from .upload import router as upload_router

__all__ = ["dashboard_router", "styles_router", "upload_router"]
