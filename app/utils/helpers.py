"""
工具函数模块
"""
import os
import hashlib
import mimetypes
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
import pytz


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
        "timestamp": datetime.now(timezone.utc).isoformat()
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
        "timestamp": datetime.now(timezone.utc).isoformat()
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


def utc_to_local_time(utc_time_str: str, local_timezone: str = None) -> str:
    """
    将UTC时间转换为本地时间

    Args:
        utc_time_str: UTC时间字符串，支持多种格式
        local_timezone: 本地时区，默认为系统时区

    Returns:
        str: 本地时间字符串
    """
    if not utc_time_str:
        return ""

    try:
        # 支持的时间格式列表
        time_formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",      # 2025-10-01T12:00:00.123456Z
            "%Y-%m-%dT%H:%M:%SZ",         # 2025-10-01T12:00:00Z
            "%Y-%m-%dT%H:%M:%S.%f",       # 2025-10-01T12:00:00.123456
            "%Y-%m-%dT%H:%M:%S",          # 2025-10-01T12:00:00
            "%Y-%m-%d %H:%M:%S.%f",       # 2025-10-01 12:00:00.123456
            "%Y-%m-%d %H:%M:%S",          # 2025-10-01 12:00:00
            "%Y/%m/%d %H:%M:%S",          # 2025/10/01 12:00:00
            "%d/%m/%Y %H:%M:%S",          # 01/10/2025 12:00:00
        ]

        # 尝试解析UTC时间
        utc_dt = None
        for fmt in time_formats:
            try:
                utc_dt = datetime.strptime(utc_time_str.strip(), fmt)
                break
            except ValueError:
                continue

        if utc_dt is None:
            # 如果所有格式都失败，返回原始字符串
            return utc_time_str

        # 设置为UTC时区
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)

        # 确定目标时区
        if local_timezone:
            try:
                target_tz = pytz.timezone(local_timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                # 如果时区无效，使用系统本地时区
                target_tz = pytz.timezone('Asia/Shanghai')  # 默认使用中国时区
        else:
            # 使用系统本地时区（中国时区）
            target_tz = pytz.timezone('Asia/Shanghai')

        # 转换到本地时区
        local_dt = utc_dt.astimezone(target_tz)

        # 返回格式化的本地时间
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")

    except Exception:
        # 如果转换失败，返回原始字符串
        return utc_time_str


def format_timestamp_to_local(timestamp: Union[str, datetime], local_timezone: str = None) -> str:
    """
    格式化时间戳为本地时间字符串

    Args:
        timestamp: 时间戳（字符串或datetime对象）
        local_timezone: 本地时区，默认为中国时区

    Returns:
        str: 格式化的本地时间字符串
    """
    if not timestamp:
        return ""

    try:
        if isinstance(timestamp, str):
            return utc_to_local_time(timestamp, local_timezone)
        elif isinstance(timestamp, datetime):
            # 如果是datetime对象，先转换为ISO格式字符串
            if timestamp.tzinfo is None:
                # 假设是UTC时间
                timestamp_str = timestamp.isoformat() + "Z"
            else:
                timestamp_str = timestamp.isoformat()
            return utc_to_local_time(timestamp_str, local_timezone)
        else:
            return str(timestamp)
    except Exception:
        return str(timestamp)


def get_current_local_time(local_timezone: str = None) -> str:
    """
    获取当前本地时间

    Args:
        local_timezone: 本地时区，默认为中国时区

    Returns:
        str: 当前本地时间字符串
    """
    try:
        if local_timezone:
            try:
                target_tz = pytz.timezone(local_timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                target_tz = pytz.timezone('Asia/Shanghai')
        else:
            target_tz = pytz.timezone('Asia/Shanghai')

        local_dt = datetime.now(target_tz)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
