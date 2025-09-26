"""
安全认证模块
"""
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import get_settings

security = HTTPBearer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    验证API密钥
    
    Args:
        credentials: HTTP Bearer认证凭据
        
    Returns:
        str: 验证通过的API密钥
        
    Raises:
        HTTPException: 认证失败时抛出401错误
    """
    settings = get_settings()
    
    if credentials.credentials != settings.server.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials


def verify_api_key_header(api_key: str) -> bool:
    """
    验证API密钥（用于Header方式）
    
    Args:
        api_key: API密钥
        
    Returns:
        bool: 验证结果
    """
    settings = get_settings()
    return api_key == settings.server.api_key
