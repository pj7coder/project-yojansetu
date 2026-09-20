import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(log_level=settings.log_level)
logger = logging.getLogger("jansetu.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events."""
    logger.info(
        "Configuration loaded | app_name='%s' | env='%s' | version='%s'",
        settings.app_name,
        settings.app_env,
        settings.app_version,
    )
    # Ensure document storage directories exist
    settings.ensure_storage_dirs()
    logger.info("Storage directories initialized at: %s", settings.storage_path)

    # Start Folder Watcher background task if enabled
    watcher_task = None
    if settings.watch_folder_enabled:
        from app.ingestion.folder_watcher import get_folder_watcher
        watcher = get_folder_watcher()
        watcher_task = asyncio.create_task(watcher.run_loop())
        logger.info("Folder Watcher background task initialized for: %s", settings.watch_folder_dir)

    logger.info("Application started successfully on %s:%d", settings.backend_host, settings.backend_port)
    yield

    if watcher_task and not watcher_task.done():
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown completed")


def create_application() -> FastAPI:
    """Factory creating and configuring the primary FastAPI instance."""
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description="Offline-first vernacular government-scheme discovery assistant for Rajasthan.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount versioned API routes
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_application()
