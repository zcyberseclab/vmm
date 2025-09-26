"""
EDR Manager

This module provides the EDRManager class which manages different EDR clients
for multiple virtual machines. It acts as a factory and coordinator for
various EDR implementations.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger

from app.models.task import EDRAlert
from app.services.vm_controller import VMController
from .base import EDRClient
from .windows_defender import WindowsDefenderEDRClient
from .kaspersky import KasperskyEDRClient


class EDRManager:
    """
    EDR管理器 - 管理不同虚拟机的EDR客户端
    
    This class manages EDR clients for different virtual machines and provides
    a unified interface for collecting alerts from various EDR systems.
    """

    def __init__(self, vm_controller: VMController, vm_configs: Optional[List[Dict[str, Any]]] = None):
        """
        初始化EDR管理器

        Args:
            vm_controller: 虚拟机控制器
            vm_configs: 虚拟机配置列表（可选）
        """
        self.vm_controller = vm_controller
        self.vm_configs = {}
        self.edr_clients = {}

        if vm_configs:
            for config in vm_configs:
                self.vm_configs[config['name']] = config
                # 根据杀软类型创建对应的EDR客户端
                self.edr_clients[config['name']] = self._create_edr_client(config)

    def _create_edr_client(self, vm_config: Dict[str, Any]) -> EDRClient:
        """
        根据虚拟机配置创建EDR客户端
        
        Args:
            vm_config: 虚拟机配置字典
            
        Returns:
            对应的EDR客户端实例
        """
        antivirus_type = vm_config.get('antivirus', 'defender').lower()
        vm_name = vm_config['name']
        username = vm_config.get('username', 'vboxuser')
        password = vm_config.get('password', '123456')

        if antivirus_type == 'defender':
            return WindowsDefenderEDRClient(vm_name, self.vm_controller, username, password)
        elif antivirus_type == 'kaspersky':
            return KasperskyEDRClient(vm_name, self.vm_controller, username, password)
        # 可以在这里继续添加其他杀软的支持
        # elif antivirus_type == 'symantec':
        #     return SymantecEDRClient(vm_name, self.vm_controller, username, password)
        # elif antivirus_type == 'mcafee':
        #     return McAfeeEDRClient(vm_name, self.vm_controller, username, password)
        else:
            logger.warning(f"不支持的杀软类型: {antivirus_type}，使用默认的Windows Defender客户端")
            return WindowsDefenderEDRClient(vm_name, self.vm_controller, username, password)

    async def collect_alerts_from_vm(self, vm_name: str, start_time: datetime,
                                   end_time: Optional[datetime] = None,
                                   file_hash: Optional[str] = None,
                                   file_name: Optional[str] = None) -> List[EDRAlert]:
        """
        从指定虚拟机收集告警
        
        Args:
            vm_name: 虚拟机名称
            start_time: 开始时间
            end_time: 结束时间（可选）
            file_hash: 文件哈希（可选）
            file_name: 文件名（可选）
            
        Returns:
            EDRAlert对象列表
        """
        if vm_name not in self.edr_clients:
            logger.error(f"虚拟机EDR客户端不存在: {vm_name}")
            return []

        edr_client = self.edr_clients[vm_name]
        return await edr_client.get_alerts(start_time, end_time, file_hash, file_name)

    def add_vm_config(self, vm_config: Dict[str, Any]) -> None:
        """
        添加新的虚拟机配置
        
        Args:
            vm_config: 虚拟机配置字典
        """
        vm_name = vm_config['name']
        self.vm_configs[vm_name] = vm_config
        self.edr_clients[vm_name] = self._create_edr_client(vm_config)
        logger.info(f"添加虚拟机EDR客户端: {vm_name}")

    def remove_vm_config(self, vm_name: str) -> None:
        """
        移除虚拟机配置
        
        Args:
            vm_name: 虚拟机名称
        """
        if vm_name in self.vm_configs:
            del self.vm_configs[vm_name]
        if vm_name in self.edr_clients:
            del self.edr_clients[vm_name]
        logger.info(f"移除虚拟机EDR客户端: {vm_name}")

    def get_supported_antivirus_types(self) -> List[str]:
        """
        获取支持的杀软类型列表

        Returns:
            支持的杀软类型列表
        """
        return ['defender', 'kaspersky']  # 可以根据实际支持的杀软类型扩展

    def get_vm_names(self) -> List[str]:
        """
        获取所有配置的虚拟机名称
        
        Returns:
            虚拟机名称列表
        """
        return list(self.vm_configs.keys())


def create_edr_manager(vm_controller: VMController, vm_configs: Optional[List[Dict[str, Any]]] = None) -> EDRManager:
    """
    创建EDR管理器
    
    Args:
        vm_controller: 虚拟机控制器
        vm_configs: 虚拟机配置列表（可选）
        
    Returns:
        EDRManager实例
    """
    return EDRManager(vm_controller, vm_configs)
