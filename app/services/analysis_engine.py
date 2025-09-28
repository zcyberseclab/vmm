import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from app.models.task import AnalysisTask, VMTaskResult, VMTaskStatus, EDRAlert
from app.core.config import get_settings
from app.services.vm_controller import create_vm_controller
from app.services.file_handler import FileHandler
from app.services.edr import EDRManager


class AnalysisEngine:
 
    def __init__(self):
        self.settings = get_settings()

        controller_type = getattr(self.settings.virtualization, 'controller_type', 'virtualbox')
        self.vm_controller = create_vm_controller(controller_type)
        self.file_handler = FileHandler()

        # 使用新的EDR分析配置
        vm_configs = []
        if hasattr(self.settings, 'edr_analysis') and self.settings.edr_analysis:
            for vm_config in self.settings.edr_analysis.vms:
                vm_configs.append({
                    'name': vm_config.name,
                    'antivirus': vm_config.antivirus,
                    'username': vm_config.username,
                    'password': vm_config.password,
                    'baseline_snapshot': vm_config.baseline_snapshot,
                    'desktop_path': vm_config.desktop_path
                })

        self.edr_manager = EDRManager(self.vm_controller, vm_configs)
    
    async def analyze_sample(self, task: AnalysisTask):
 
        logger.info(f"开始分析样本: {task.file_name} (任务ID: {task.task_id})")

        try:
            # 为每个虚拟机创建任务结果
            for vm_name in task.vm_names:
                vm_result = VMTaskResult(
                    vm_name=vm_name,
                    status=VMTaskStatus.PENDING,
                    start_time=datetime.utcnow()
                )
                task.vm_results.append(vm_result)
            
            # 并行处理所有虚拟机
            vm_tasks = []
            for vm_result in task.vm_results:
                vm_task = self._analyze_on_vm(task, vm_result)
                vm_tasks.append(vm_task)
            
       
            await asyncio.gather(*vm_tasks, return_exceptions=True)
            
            logger.info(f"样本分析完成: {task.task_id}")

        except Exception as e:
            logger.error(f"样本分析失败: {task.task_id} - {str(e)}")
            raise
    
    async def _analyze_on_vm(self, task: AnalysisTask, vm_result: VMTaskResult):
 
        vm_name = vm_result.vm_name
        logger.info(f"开始在虚拟机 {vm_name} 上分析样本")
        
        try:
 
            vm_result.status = VMTaskStatus.PREPARING
            await self._prepare_vm(vm_name)
            
 
            vm_result.status = VMTaskStatus.UPLOADING
            await self._upload_sample_to_vm(task, vm_name)
            
  
            vm_result.status = VMTaskStatus.ANALYZING
            analysis_start_time = datetime.utcnow()

            # 执行样本文件
            await self._execute_sample_in_vm(task, vm_name)

            # 等待分析完成 - 给杀软足够时间检测
            analysis_wait_time = min(task.timeout, 30)  # 最多等待30秒
            logger.info(f"等待 {analysis_wait_time} 秒让杀软检测样本...")
            await asyncio.sleep(analysis_wait_time)
            
       
            vm_result.status = VMTaskStatus.COLLECTING
            alerts = await self._collect_edr_results(vm_name, analysis_start_time, task.file_hash, task.file_name)
            vm_result.alerts = alerts
            

            vm_result.status = VMTaskStatus.RESTORING
            await self._restore_vm_snapshot(vm_name)

            # 执行完整的资源清理
            await self._complete_vm_cleanup(vm_name)


            vm_result.status = VMTaskStatus.COMPLETED
            vm_result.end_time = datetime.utcnow()

            logger.info(f"虚拟机 {vm_name} 分析完成，发现 {len(alerts)} 个告警")

        except Exception as e:
            vm_result.status = VMTaskStatus.FAILED
            vm_result.error_message = str(e)
            vm_result.end_time = datetime.utcnow()
            logger.error(f"虚拟机 {vm_name} 分析失败: {str(e)}")

            # 尝试恢复快照和完整清理
            try:
                await self._restore_vm_snapshot(vm_name)
                await self._complete_vm_cleanup(vm_name)
            except Exception as restore_error:
                logger.error(f"恢复快照和清理失败: {str(restore_error)}")
    
    async def _prepare_vm(self, vm_name: str):

        logger.info(f"准备虚拟机: {vm_name}")

        vm_config = None
        if hasattr(self.settings, 'edr_analysis') and self.settings.edr_analysis:
            for config in self.settings.edr_analysis.vms:
                if config.name == vm_name:
                    vm_config = config
                    break

        if not vm_config:
            raise Exception(f"虚拟机配置不存在: {vm_name}")

        # 检查并处理虚拟机状态
        await self._ensure_vm_stopped(vm_config.name)

        # 恢复到快照
        logger.info(f"恢复快照: {vm_config.baseline_snapshot}")
        if not await self.vm_controller.revert_snapshot(vm_config.name, vm_config.baseline_snapshot):
            raise Exception(f"恢复快照失败: {vm_name}")

        # 启动虚拟机
        if not await self.vm_controller.power_on(vm_config.name):
            raise Exception(f"启动虚拟机失败: {vm_name}")

        # 等待虚拟机就绪
        await self._wait_for_vm_ready(vm_config.name, timeout=300)

        logger.info(f"虚拟机 {vm_name} 已就绪")

    async def _ensure_vm_stopped(self, vm_name: str):
        """
        确保虚拟机处于停止状态，处理锁定问题
        """
        logger.info(f"确保虚拟机停止: {vm_name}")

        try:
            # 使用新的资源清理方法
            if hasattr(self.vm_controller, 'cleanup_vm_resources'):
                logger.info("使用增强的资源清理方法")
                cleanup_success = await self.vm_controller.cleanup_vm_resources(vm_name)
                if cleanup_success:
                    logger.info(f"虚拟机 {vm_name} 资源清理成功")
                    return
                else:
                    logger.warning(f"资源清理失败，使用传统方法: {vm_name}")

            # 向后兼容：使用原有方法
            logger.info("使用传统方法确保虚拟机停止")
            status_info = await self.vm_controller.get_status(vm_name)
            power_state = status_info.get("power_state", "unknown").lower()
            logger.info(f"虚拟机 {vm_name} 当前状态: {power_state}")

            if power_state in ['running', 'paused', 'stuck', 'starting']:
                logger.info(f"虚拟机正在运行，尝试关闭: {vm_name}")
                # 尝试正常关闭
                if not await self.vm_controller.power_off(vm_name):
                    logger.warning(f"正常关闭失败，等待5秒后重试: {vm_name}")
                    await asyncio.sleep(5)
                    # 再次尝试关闭
                    await self.vm_controller.power_off(vm_name)

            # 等待一段时间确保VM完全停止
            await asyncio.sleep(3)

        except Exception as e:
            logger.warning(f"确保虚拟机停止时出现异常: {str(e)}")
            # 即使出现异常也尝试关闭
            try:
                await self.vm_controller.power_off(vm_name)
                await asyncio.sleep(3)
            except:
                logger.error(f"强制关闭虚拟机也失败: {vm_name}")
                pass

    async def _wait_for_vm_ready(self, vm_name: str, timeout: int = 300):
        """
        等待虚拟机就绪

        Args:
            vm_name: 虚拟机名称
            timeout: 超时时间（秒）
        """
        logger.info(f"waiting {vm_name} startup...")

        start_time = datetime.utcnow()
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                status = await self.vm_controller.get_status(vm_name)
                if status.get("power_state") in ["running", "poweredOn"]:
                    # 额外等待一段时间确保系统完全启动
                    await asyncio.sleep(30)
                    logger.info(f"虚拟机 {vm_name} 已就绪")
                    return

                await asyncio.sleep(10)  # 每10秒检查一次

            except Exception as e:
                logger.warning(f"检查虚拟机状态失败: {str(e)}")
                await asyncio.sleep(10)

        raise Exception(f"虚拟机 {vm_name} 在 {timeout} 秒内未就绪")
    
    async def _upload_sample_to_vm(self, task: AnalysisTask, vm_name: str):
 
        logger.info(f"上传样本到虚拟机: {vm_name}")
        
        # 获取虚拟机配置
        vm_config = None
        if hasattr(self.settings, 'edr_analysis') and self.settings.edr_analysis:
            for config in self.settings.edr_analysis.vms:
                if config.name == vm_name:
                    vm_config = config
                    break

        if not vm_config:
            raise Exception(f"虚拟机配置不存在: {vm_name}")

        # 上传文件到虚拟机桌面
        desktop_path = getattr(vm_config, 'desktop_path', f"C:\\Users\\{vm_config.username}\\Desktop")

        # 现在总是上传ZIP文件
        if task.is_compressed:
            # 上传ZIP文件
            zip_file_name = os.path.basename(task.file_path)
            destination_path = f"{desktop_path}\\{zip_file_name}"
            logger.info(f"上传ZIP压缩文件: {zip_file_name}")
        else:
            # 向后兼容：直接上传原始文件
            file_name_only = os.path.basename(task.file_name)
            if '.' not in file_name_only:
                file_name_only += '.bin'
            destination_path = f"{desktop_path}\\{file_name_only}"
            logger.info(f"上传原始文件: {file_name_only}")

        # 使用VirtualBox的guestcontrol功能上传文件
        if hasattr(self.vm_controller, 'copy_file_to_vm'):
            success = await self.vm_controller.copy_file_to_vm(
                vm_config.name,
                task.file_path,  # 这里是ZIP文件路径或原始文件路径
                destination_path,
                vm_config.username,
                vm_config.password
            )
            if not success:
                raise Exception(f"上传样本到虚拟机失败: {vm_name}")
        else:
            raise Exception(f"VM控制器不支持文件上传功能: {vm_name}")

        logger.info(f"样本已上传到虚拟机 {vm_name}: {destination_path}")

    async def _execute_sample_in_vm(self, task: AnalysisTask, vm_name: str):
        """
        在虚拟机中执行样本文件
        """
        logger.info(f"在虚拟机 {vm_name} 中执行样本: {task.file_name}")

        # 获取虚拟机配置
        vm_config = None
        if hasattr(self.settings, 'edr_analysis') and self.settings.edr_analysis:
            for config in self.settings.edr_analysis.vms:
                if config.name == vm_name:
                    vm_config = config
                    break

        if not vm_config:
            raise Exception(f"虚拟机配置不存在: {vm_name}")

        # 构建样本文件路径
        desktop_path = getattr(vm_config, 'desktop_path', f"C:\\Users\\{vm_config.username}\\Desktop")

        # 直接处理上传的文件
        file_name_only = os.path.basename(task.file_name)
        if '.' not in file_name_only:
            file_name_only += '.bin'
        sample_path = f"{desktop_path}\\{file_name_only}"

        # 更新文件名用于后续处理
        actual_file_name = os.path.basename(sample_path)

        # 等待一段时间让EDR检测文件
        logger.info("等待EDR检测文件...")
        await asyncio.sleep(5)

        # 检查文件是否被EDR删除
        check_file_cmd = f"powershell -Command \"Test-Path '{sample_path}'\""
        file_exists, file_check_output = await self.vm_controller.execute_command_in_vm(
            vm_config.name, check_file_cmd, vm_config.username, vm_config.password, timeout=30
        )

        if not file_exists or 'False' in file_check_output or 'false' in file_check_output.lower():
            logger.info(f"文件已被EDR删除: {sample_path}")
            logger.info("文件被删除，直接收集EDR日志，无需执行样本")
            # 文件被删除，直接返回，后续会收集EDR日志
            return

        logger.info(f"文件仍然存在: {sample_path}，继续执行样本")

        try:
            # 根据文件类型选择执行方式（使用实际要执行的文件名）
            file_extension = actual_file_name.lower().split('.')[-1] if '.' in actual_file_name else ''

            if file_extension in ['exe', 'com', 'scr', 'bat', 'cmd']:
                # Windows可执行文件
                #execute_cmd = f'Start-Process -FilePath "{sample_path}" -WindowStyle Hidden'
                execute_cmd = f"Start-Process -FilePath '{sample_path}'"
                logger.info(f"执行Windows可执行文件: {sample_path}")

            elif file_extension in ['ps1']:
                # PowerShell脚本
                execute_cmd = f"powershell -ExecutionPolicy Bypass -File '{sample_path}'"
                logger.info(f"执行PowerShell脚本: {sample_path}")

            elif file_extension in ['vbs', 'js']:
                # 脚本文件
                execute_cmd = f"cscript '{sample_path}'"
                logger.info(f"执行脚本文件: {sample_path}")

            elif file_extension in ['elf']:
                logger.info(f"ELF文件无法在Windows中执行，尝试触发杀软检测: {sample_path}")
                execute_cmd = f"Get-Content '{sample_path}' -TotalCount 1"

            else:
                # 其他文件类型，尝试用默认程序打开
                execute_cmd = f"Start-Process -FilePath '{sample_path}'"
      
                logger.info(f"尝试用默认程序执行: {sample_path}")

            # 在虚拟机中执行命令
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_config.name, f'powershell -Command "{execute_cmd}"',
                vm_config.username, vm_config.password, timeout=60
            )

            if success:
                logger.info(f"样本执行命令发送成功: {vm_name}")
                if output.strip():
                    logger.info(f"执行输出: {output.strip()}")
            else:
                logger.warning(f"样本执行命令失败: {vm_name} - {output}")

        except Exception as e:
            logger.error(f"执行样本时发生异常: {vm_name} - {str(e)}")
            # 不抛出异常，继续分析流程

    async def _collect_edr_results(self, vm_name: str, start_time: datetime, file_hash: str, file_name: str) -> List[EDRAlert]:

        logger.info(f"collect {vm_name} edr result")

        try:
            # 从EDR系统获取告警
            alerts = await self.edr_manager.collect_alerts_from_vm(
                vm_name, start_time, datetime.utcnow(), file_hash, file_name
            )

            # 对报警进行去重处理：相同alert_type和file_path的报警，只保留detection_time最新的
            deduplicated_alerts = self._deduplicate_alerts(alerts)

            logger.info(f"原始告警数量: {len(alerts)}, 去重后告警数量: {len(deduplicated_alerts)}")

            return deduplicated_alerts

        except Exception as e:
            logger.error(f"failed to collect edr result: {str(e)}")
            return []

    def _deduplicate_alerts(self, alerts: List[EDRAlert]) -> List[EDRAlert]:
        """
        对报警进行去重处理：相同source、alert_type和file_path的报警，只保留detection_time最新的

        Args:
            alerts: 原始报警列表

        Returns:
            去重后的报警列表
        """
        if not alerts:
            return alerts

        # 使用字典来跟踪每个(source, alert_type, file_path)组合的最新报警
        alert_map = {}

        for alert in alerts:
            # 创建唯一键：source + alert_type + file_path
            key = (alert.source, alert.alert_type, alert.file_path)

            # 获取detection_time，如果没有则使用timestamp
            current_detection_time = alert.detection_time or alert.timestamp.isoformat()

            if key not in alert_map:
                # 第一次遇到这个组合，直接添加
                alert_map[key] = alert
                logger.debug(f"添加新报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {current_detection_time}")
            else:
                # 已存在相同组合，比较detection_time
                existing_alert = alert_map[key]
                existing_detection_time = existing_alert.detection_time or existing_alert.timestamp.isoformat()

                # 比较时间字符串（ISO格式可以直接比较）
                if current_detection_time > existing_detection_time:
                    # 当前报警更新，替换
                    alert_map[key] = alert
                    logger.debug(f"替换报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {existing_detection_time} -> {current_detection_time}")
                else:
                    logger.debug(f"保留原报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {existing_detection_time} (跳过 {current_detection_time})")

        # 返回去重后的报警列表
        deduplicated_alerts = list(alert_map.values())

        if len(deduplicated_alerts) < len(alerts):
            logger.info(f"报警去重完成: {len(alerts)} -> {len(deduplicated_alerts)} (去除了 {len(alerts) - len(deduplicated_alerts)} 个重复报警)")

        return deduplicated_alerts

    async def _restore_vm_snapshot(self, vm_name: str):
        """恢复虚拟机快照并完全清理资源"""
        logger.info(f"恢复虚拟机快照: {vm_name}")

        # 获取虚拟机配置
        vm_config = None
        if hasattr(self.settings, 'edr_analysis') and self.settings.edr_analysis:
            for config in self.settings.edr_analysis.vms:
                if config.name == vm_name:
                    vm_config = config
                    break

        if not vm_config:
            raise Exception(f"虚拟机配置不存在: {vm_name}")

        # 使用新的资源清理方法
        logger.info(f"清理虚拟机资源: {vm_name}")
        if hasattr(self.vm_controller, 'cleanup_vm_resources'):
            cleanup_success = await self.vm_controller.cleanup_vm_resources(vm_config.name)
            if not cleanup_success:
                logger.warning(f"资源清理可能不完整，继续恢复快照: {vm_name}")
        else:
            # 向后兼容：使用原有的关闭方法
            logger.info("使用传统方法关闭虚拟机")
            try:
                status_info = await self.vm_controller.get_status(vm_config.name)
                power_state = status_info.get("power_state", "unknown").lower()
                if power_state in ['running', 'paused', 'stuck']:
                    logger.info(f"关闭虚拟机: {vm_name}")
                    await self.vm_controller.power_off(vm_config.name)
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"传统关闭方法失败: {str(e)}")

        # 恢复快照
        logger.info(f"恢复快照: {vm_config.baseline_snapshot}")
        if not await self.vm_controller.revert_snapshot(vm_config.name, vm_config.baseline_snapshot):
            raise Exception(f"恢复快照失败: {vm_name}")

        logger.info(f"虚拟机 {vm_name} 快照已恢复")

    async def _complete_vm_cleanup(self, vm_name: str):
        """任务完成后的完整虚拟机清理"""
        logger.info(f"执行任务完成后的完整清理: {vm_name}")

        try:
            # 1. 使用增强的资源清理
            if hasattr(self.vm_controller, 'cleanup_vm_resources'):
                cleanup_success = await self.vm_controller.cleanup_vm_resources(vm_name)
                if cleanup_success:
                    logger.info(f"完整清理成功: {vm_name}")
                else:
                    logger.warning(f"完整清理可能不完整: {vm_name}")

            # 2. 额外等待确保所有资源释放
            await asyncio.sleep(5)

            # 3. 最终状态检查
            try:
                status_info = await self.vm_controller.get_status(vm_name)
                final_state = status_info.get("power_state", "unknown").lower()
                logger.info(f"最终虚拟机状态: {vm_name} - {final_state}")

                if final_state not in ['poweroff', 'aborted', 'saved']:
                    logger.warning(f"虚拟机可能未完全停止: {vm_name} - {final_state}")
                    # 最后一次尝试强制关闭
                    await self.vm_controller.power_off(vm_name)
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"最终状态检查失败: {str(e)}")

            logger.info(f"虚拟机完整清理流程完成: {vm_name}")

        except Exception as e:
            logger.error(f"完整清理过程中发生异常: {vm_name} - {str(e)}")
            # 即使清理失败也不抛出异常，避免影响任务完成状态










