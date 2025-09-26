"""
工具函数模块
"""
import os
import hashlib
import mimetypes
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    计算文件哈希值
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256)
        
    Returns:
        str: 哈希值
    """
    hash_func = getattr(hashlib, algorithm)()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def get_file_type(file_path: str) -> str:
    """
    获取文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: MIME类型
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        str: 格式化后的大小
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """
    格式化时间间隔
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化后的时间
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def is_safe_filename(filename: str) -> bool:
    """
    检查文件名是否安全
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否安全
    """
    if not filename:
        return False
    
    # 检查危险字符
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        if char in filename:
            return False
    
    # 检查长度
    if len(filename) > 255:
        return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """
    清理文件名
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 清理后的文件名
    """
    if not filename:
        return "unknown"
    
    # 替换危险字符
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # 移除连续的点
    while '..' in filename:
        filename = filename.replace('..', '.')
    
    # 限制长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_len = 255 - len(ext)
        filename = name[:max_name_len] + ext
    
    return filename


def validate_ip_address(ip: str) -> bool:
    """
    验证IP地址格式
    
    Args:
        ip: IP地址字符串
        
    Returns:
        bool: 是否有效
    """
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False
        
        return True
    except:
        return False


def create_error_response(message: str, code: str = "UNKNOWN_ERROR") -> Dict[str, Any]:
    """
    创建错误响应
    
    Args:
        message: 错误消息
        code: 错误代码
        
    Returns:
        Dict[str, Any]: 错误响应
    """
    return {
        "error": True,
        "code": code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }


def create_success_response(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        
    Returns:
        Dict[str, Any]: 成功响应
    """
    response = {
        "error": False,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    return response


def parse_timeout(timeout_str: str, default: int = 300) -> int:
    """
    解析超时时间字符串
    
    Args:
        timeout_str: 超时时间字符串 (如: "5m", "30s", "1h")
        default: 默认值（秒）
        
    Returns:
        int: 超时时间（秒）
    """
    if not timeout_str:
        return default
    
    try:
        # 如果是纯数字，直接返回
        if timeout_str.isdigit():
            return int(timeout_str)
        
        # 解析带单位的时间
        timeout_str = timeout_str.lower().strip()
        
        if timeout_str.endswith('s'):
            return int(timeout_str[:-1])
        elif timeout_str.endswith('m'):
            return int(timeout_str[:-1]) * 60
        elif timeout_str.endswith('h'):
            return int(timeout_str[:-1]) * 3600
        else:
            return int(timeout_str)
            
    except (ValueError, IndexError):
        return default


def get_vm_config_by_name(vm_name: str, vm_configs: list) -> Optional[Dict[str, Any]]:
    """
    根据名称获取虚拟机配置
    
    Args:
        vm_name: 虚拟机名称
        vm_configs: 虚拟机配置列表
        
    Returns:
        Optional[Dict[str, Any]]: 虚拟机配置
    """
    for config in vm_configs:
        if config.name == vm_name:
            return config
    return None
