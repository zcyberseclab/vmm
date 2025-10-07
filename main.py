import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.api.routes import router
from app.api.middleware import APIKeyMiddleware, LoggingMiddleware
from app.services.task_manager import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Malware analysis system starting...")

    # Load configuration
    settings = get_settings()

    # Create necessary directories
    os.makedirs(settings.server.upload_dir, exist_ok=True)
    os.makedirs(os.path.dirname(settings.logging.file), exist_ok=True)

    # Start task manager
    await task_manager.start()

    logger.info(f"Server configuration:")
    logger.info(f"  - Listen address: {settings.server.host}:{settings.server.port}")
    logger.info(f"  - Upload directory: {settings.server.upload_dir}")
    logger.info(f"  - Max file size: {settings.server.max_file_size} bytes")
    vm_count = 0
    if settings.windows and settings.windows.edr_analysis:
        vm_count = len(settings.windows.edr_analysis.vms)
    logger.info(f"  - Virtual machines: {vm_count}")
    logger.info(f"  - Max queue size: {settings.task_settings.max_queue_size}")
    logger.info(f"  - Concurrent tasks: {settings.task_settings.concurrent_tasks}")
    logger.info("System startup completed!")

    yield

    # Shutdown
    logger.info("Malware analysis system shutting down...")

    # Stop task manager
    await task_manager.stop()

    logger.info("System shutdown completed")


def create_app() -> FastAPI:
    """Create FastAPI application"""

    # Load configuration
    settings = get_settings()

    # Configure logging
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        level=settings.logging.level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        settings.logging.file,
        level=settings.logging.level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=settings.logging.max_size,
        retention=settings.logging.backup_count,
        encoding="utf-8"
    )
    
    # Create FastAPI application
    app = FastAPI(
        title="Malware Analysis System",
        description="Malware analysis system",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        APIKeyMiddleware,
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/api/health"]
    )

    # Register routes
    app.include_router(router)

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    import logging
    import sys

    settings = get_settings()

    # Check if running in production mode or from PyInstaller
    is_production = "--production" in sys.argv or "--prod" in sys.argv
    is_frozen = getattr(sys, 'frozen', False)  # PyInstaller sets this

    if is_production or is_frozen:
        # Production mode or PyInstaller executable
        if is_frozen:
            logger.info("Starting server from executable...")
        else:
            logger.info("Starting production server...")

        # Disable debug logging in production
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

        uvicorn.run(
            app if is_frozen else "main:app",  # Use app object when frozen
            host=settings.server.host,
            port=settings.server.port,
            reload=False,           # No auto-reload in production or when frozen
            log_level="warning",    # Higher log level for production
            access_log=True,        # Enable access logs for production monitoring
            workers=1               # Single worker for this process
        )
    else:
        # Development mode configuration
        logger.info("Starting development server...")

        # Disable uvicorn default logging in development
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

        uvicorn.run(
            "main:app",
            host=settings.server.host,
            port=settings.server.port,
            reload=True,            # Auto-reload for development
            log_level="warning",    # Set uvicorn log level to warning to reduce noise
            access_log=False        # Disable access logs in development
        )
