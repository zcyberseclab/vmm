"""
API中间件
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings
from app.core.security import verify_api_key_header
import time
from loguru import logger


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API密钥验证中间件"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health"]
    
    async def dispatch(self, request: Request, call_next):
        # 检查是否为排除路径
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # 检查API密钥
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "缺少API密钥，请在请求头中添加 X-API-Key"}
            )
        
        if not verify_api_key_header(api_key):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "无效的API密钥"}
            )
        
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 记录请求信息
        logger.info(f"请求开始: {request.method} {request.url}")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # 记录响应信息
            logger.info(
                f"请求完成: {request.method} {request.url} - "
                f"状态码: {response.status_code} - "
                f"耗时: {process_time:.3f}s"
            )
            
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = str(process_time)
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"请求异常: {request.method} {request.url} - "
                f"错误: {str(e)} - "
                f"耗时: {process_time:.3f}s"
            )
            raise
