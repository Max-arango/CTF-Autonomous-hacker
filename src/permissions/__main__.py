"""Permission Manager Main Entry Point"""
import asyncio
import uvicorn
from .manager import get_permission_manager
from ..config.settings import get_settings


async def main():
    """Run permission manager server."""
    settings = get_settings()
    manager = get_permission_manager()
    app = manager.get_app()

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.security.permission_manager_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())