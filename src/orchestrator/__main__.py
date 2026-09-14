"""Orchestrator Main Entry Point"""
import asyncio
import uvicorn
from .main import create_app
from ..config.settings import get_settings


async def main():
    """Run orchestrator server."""
    settings = get_settings()
    app = create_app()

    config = uvicorn.Config(
        app,
        host=settings.orchestrator.host,
        port=settings.orchestrator.port,
        workers=settings.orchestrator.workers,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())