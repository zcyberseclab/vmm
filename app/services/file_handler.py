"""
文件处理模块
"""
import os
import hashlib
import shutil
import aiofiles
from typing import Dict, Any
from fastapi import UploadFile
from loguru import logger

from app.core.config import get_settings


class FileHandler:
    """文件处理器"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def save_uploaded_file(self, file: UploadFile) -> Dict[str, Any]:
        """
        保存上传的文件

        Args:
            file: 上传的文件对象

        Returns:
            Dict[str, Any]: 文件信息（包含文件的路径、哈希、大小等）
        """
        try:
            # 确保上传目录存在
            os.makedirs(self.settings.server.upload_dir, exist_ok=True)

            # 读取文件内容
            content = await file.read()
            file_size = len(content)

            # 计算文件哈希
            file_hash = hashlib.sha256(content).hexdigest()

            # 生成文件路径
            file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
            if not file_extension:
                file_extension = ".bin"
            file_name = f"{file_hash}{file_extension}"
            file_path = os.path.join(self.settings.server.upload_dir, file_name)

            # 如果文件已存在，直接返回信息
            if os.path.exists(file_path):
                logger.info(f"文件已存在: {file_path}")
                return {
                    "path": file_path,
                    "hash": file_hash,
                    "size": file_size,
                    "original_name": file.filename,
                    "is_compressed": False
                }

            # 保存文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)

            logger.info(f"文件已保存: {file_path} (大小: {file_size} bytes)")

            return {
                "path": file_path,
                "hash": file_hash,
                "size": file_size,
                "original_name": file.filename,
                "is_compressed": False
            }

        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            raise



    async def calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: SHA256哈希值
        """
        try:
            hash_sha256 = hashlib.sha256()
            
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            logger.error(f"计算文件哈希失败: {str(e)}")
            raise
     
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 文件信息
        """
        try:
            if not os.path.exists(file_path):
                return {"error": "文件不存在"}
            
            stat = os.stat(file_path)
            
            return {
                "path": file_path,
                "size": stat.st_size,
                "created_time": stat.st_ctime,
                "modified_time": stat.st_mtime,
                "is_file": os.path.isfile(file_path),
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"获取文件信息失败: {str(e)}")
            return {"error": str(e)}
