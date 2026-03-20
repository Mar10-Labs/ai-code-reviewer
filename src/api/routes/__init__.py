from .health import router as health_router
from .agent import router as agent_router

# Aquí registraremos todos los routers de la aplicación
__all__ = ["health_router", "agent_router"]