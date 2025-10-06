import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.api.routes import router
from app.api.middleware import APIKeyMiddleware, LoggingMiddleware
from app.services.task_manager import task_manager


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    
    # 加载配置
    settings = get_settings()
    
    # 配置日志
    logger.remove()  # 移除默认处理器
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
    
    # 创建FastAPI应用
    app = FastAPI(
        title="EDR样本分析系统",
        description="基于虚拟机的EDR样本自动化分析系统",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加自定义中间件
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        APIKeyMiddleware,
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/api/health"]
    )
    
    # 注册路由
    app.include_router(router)
    
    # 启动事件
    @app.on_event("startup")
    async def startup_event():
        logger.info("EDR样本分析系统启动中...")

        # 创建必要的目录
        os.makedirs(settings.server.upload_dir, exist_ok=True)
        os.makedirs(os.path.dirname(settings.logging.file), exist_ok=True)

        # 启动任务管理器
        await task_manager.start()

        logger.info(f"服务器配置:")
        logger.info(f"  - 监听地址: {settings.server.host}:{settings.server.port}")
        logger.info(f"  - 上传目录: {settings.server.upload_dir}")
        logger.info(f"  - 最大文件大小: {settings.server.max_file_size} bytes")
        vm_count = 0
        edr_config = settings.edr_analysis
        if edr_config:
            vm_count = len(edr_config.vms)
        logger.info(f"  - 虚拟机数量: {vm_count}")
        logger.info(f"  - 最大队列大小: {settings.task_settings.max_queue_size}")
        logger.info(f"  - 并发任务数: {settings.task_settings.concurrent_tasks}")
        logger.info("系统启动完成!")

    # 关闭事件
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("EDR样本分析系统正在关闭...")

        # 停止任务管理器
        await task_manager.stop()

        logger.info("系统已关闭")
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    logger.info("启动开发服务器...")
    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
        log_level=settings.logging.level.lower()
    )
