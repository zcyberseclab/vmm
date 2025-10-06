import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set
from loguru import logger
from enum import Enum

from app.core.config import get_settings


class VMState(str, Enum):
 
    IDLE = "idle"                    # 空闲
    PREPARING = "preparing"          # 准备中
    BUSY = "busy"                   # 忙碌中
    RESTORING = "restoring"         # 恢复中
    ERROR = "error"                 # 错误状态
    MAINTENANCE = "maintenance"      # 维护中


class VMResource:
 
    def __init__(self, vm_name: str, vm_config: dict):
        self.vm_name = vm_name
        self.vm_config = vm_config
        self.state = VMState.IDLE
        self.current_task_id: Optional[str] = None
        self.last_used: Optional[datetime] = None
        self.error_count = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self, task_id: str) -> bool:
  
        async with self.lock:
            if self.state == VMState.IDLE:
                self.state = VMState.BUSY
                self.current_task_id = task_id
                self.last_used = datetime.now()
                return True
            return False
    
    async def release(self):
    
        async with self.lock:
            self.state = VMState.IDLE
            self.current_task_id = None
    
    async def set_error(self, error_msg: str = ""):
  
        async with self.lock:
            self.state = VMState.ERROR
            self.error_count += 1
            logger.warning(f"VM {self.vm_name} 进入错误状态: {error_msg} (错误次数: {self.error_count})")
    
    async def reset_error(self):
       
        async with self.lock:
            if self.state == VMState.ERROR:
                self.state = VMState.IDLE
                logger.info(f"VM {self.vm_name} 错误状态已重置")


class VMPoolManager:
 
    def __init__(self):
        self.settings = get_settings()
        self.vm_resources: Dict[str, VMResource] = {}
        self.initialization_lock = asyncio.Lock()
        self.initialized = False
        
        # 性能统计
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'avg_task_time': 0.0
        }
    
    async def initialize(self):
        """初始化VM资源池"""
        async with self.initialization_lock:
            if self.initialized:
                return
            
            logger.info("初始化虚拟机资源池...")
            
            if self.settings.windows and self.settings.windows.edr_analysis:
                for vm_config in self.settings.windows.edr_analysis.vms:
                    vm_resource = VMResource(
                        vm_name=vm_config.name,
                        vm_config={
                            'name': vm_config.name,
                            'antivirus': vm_config.antivirus,
                            'username': vm_config.username,
                            'password': vm_config.password,
                            'baseline_snapshot': vm_config.baseline_snapshot,
                            'desktop_path': vm_config.desktop_path
                        }
                    )
                    self.vm_resources[vm_config.name] = vm_resource
                    logger.info(f"添加VM资源: {vm_config.name} ({vm_config.antivirus})")
            
            self.initialized = True
            logger.info(f"虚拟机资源池初始化完成，共 {len(self.vm_resources)} 个VM")
    
    async def get_available_vms(self, requested_vms: Optional[List[str]] = None) -> List[str]:
        """
        获取可用的VM列表
        
        Args:
            requested_vms: 请求的VM名称列表，如果为None则返回所有可用VM
            
        Returns:
            可用的VM名称列表
        """
        await self.initialize()
        
        available_vms = []
        
        if requested_vms:
            # 检查请求的VM是否可用
            for vm_name in requested_vms:
                if vm_name in self.vm_resources:
                    vm_resource = self.vm_resources[vm_name]
                    if vm_resource.state in [VMState.IDLE, VMState.ERROR]:
                        available_vms.append(vm_name)
                else:
                    logger.warning(f"请求的VM不存在: {vm_name}")
        else:
            # 返回所有可用VM
            for vm_name, vm_resource in self.vm_resources.items():
                if vm_resource.state in [VMState.IDLE, VMState.ERROR]:
                    available_vms.append(vm_name)
        
        # 按错误次数排序，优先使用错误次数少的VM
        available_vms.sort(key=lambda vm: self.vm_resources[vm].error_count)
        
        return available_vms
    
    async def acquire_vm(self, vm_name: str, task_id: str) -> bool:
        """
        获取指定VM资源
        
        Args:
            vm_name: VM名称
            task_id: 任务ID
            
        Returns:
            是否成功获取
        """
        if vm_name not in self.vm_resources:
            return False
        
        vm_resource = self.vm_resources[vm_name]
        success = await vm_resource.acquire(task_id)
        
        if success:
            logger.debug(f"成功获取VM资源: {vm_name} (任务: {task_id})")
        else:
            logger.debug(f"无法获取VM资源: {vm_name} (当前状态: {vm_resource.state})")
        
        return success
    
    async def release_vm(self, vm_name: str):
        """释放VM资源"""
        if vm_name in self.vm_resources:
            await self.vm_resources[vm_name].release()
            logger.debug(f"释放VM资源: {vm_name}")
    
    async def mark_vm_error(self, vm_name: str, error_msg: str = ""):
        """标记VM为错误状态"""
        if vm_name in self.vm_resources:
            await self.vm_resources[vm_name].set_error(error_msg)
    
    async def reset_vm_error(self, vm_name: str):
        """重置VM错误状态"""
        if vm_name in self.vm_resources:
            await self.vm_resources[vm_name].reset_error()
    
    async def get_vm_config(self, vm_name: str) -> Optional[dict]:
        """获取VM配置"""
        if vm_name in self.vm_resources:
            return self.vm_resources[vm_name].vm_config
        return None
    
    async def get_pool_status(self) -> dict:
        """获取资源池状态"""
        await self.initialize()
        
        status = {
            'total_vms': len(self.vm_resources),
            'idle_vms': 0,
            'busy_vms': 0,
            'error_vms': 0,
            'vm_details': {}
        }
        
        for vm_name, vm_resource in self.vm_resources.items():
            state = vm_resource.state
            status['vm_details'][vm_name] = {
                'state': state,
                'current_task': vm_resource.current_task_id,
                'error_count': vm_resource.error_count,
                'last_used': vm_resource.last_used.isoformat() if vm_resource.last_used else None
            }
            
            if state == VMState.IDLE:
                status['idle_vms'] += 1
            elif state == VMState.BUSY:
                status['busy_vms'] += 1
            elif state == VMState.ERROR:
                status['error_vms'] += 1
        
        status.update(self.stats)
        return status
    
    def update_stats(self, task_successful: bool, task_duration: float):
        """更新性能统计"""
        self.stats['total_tasks'] += 1
        if task_successful:
            self.stats['successful_tasks'] += 1
        else:
            self.stats['failed_tasks'] += 1
        
 
        total_time = self.stats['avg_task_time'] * (self.stats['total_tasks'] - 1) + task_duration
        self.stats['avg_task_time'] = total_time / self.stats['total_tasks']


 
vm_pool_manager = VMPoolManager()


async def get_vm_pool_manager() -> VMPoolManager:
 
    await vm_pool_manager.initialize()
    return vm_pool_manager
