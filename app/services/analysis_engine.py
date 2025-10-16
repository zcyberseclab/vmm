import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from app.models.task import AnalysisTask, VMTaskResult, VMTaskStatus, EDRAlert
from app.core.config import get_settings
from app.services.vm_controller import create_vm_controller
from app.services.file_handler import FileHandler
from app.services.windows.edr import EDRManager
from app.services.vm_pool_manager import get_vm_pool_manager


class AnalysisEngine:

    def __init__(self):
        self.settings = get_settings()

        # Use VirtualBox as default controller for Windows analysis
        self.vm_controller = create_vm_controller('virtualbox')
        self.file_handler = FileHandler()

        # 使用新的EDR分析配置
        vm_configs = []
        if self.settings.windows and self.settings.windows.edr_analysis:
            for vm_config in self.settings.windows.edr_analysis.vms:
                vm_configs.append({
                    'name': vm_config.name,
                    'antivirus': vm_config.antivirus,
                    'username': vm_config.username,
                    'password': vm_config.password,
                    'baseline_snapshot': vm_config.baseline_snapshot,
                    'desktop_path': vm_config.desktop_path
                })

        self.edr_manager = EDRManager(self.vm_controller, vm_configs)

        # 初始化VM资源池管理器（异步初始化将在第一次使用时进行）
        self.vm_pool_manager = None
    
    async def analyze_sample(self, task: AnalysisTask):

        logger.info(f"开始分析样本: {task.file_name} (任务ID: {task.task_id}) - 使用 {len(task.vm_names)} 个虚拟机并行分析")

        try:
            # 为每个虚拟机创建任务结果
            for vm_name in task.vm_names:
                vm_result = VMTaskResult(
                    vm_name=vm_name,
                    status=VMTaskStatus.PENDING,
                    start_time=datetime.utcnow()
                )
                task.edr_results.append(vm_result)

            # 并行处理所有虚拟机 - 使用信号量控制并发数
            max_concurrent_vms = min(len(task.vm_names), 8)  # 最多同时处理8个VM
            semaphore = asyncio.Semaphore(max_concurrent_vms)

            async def vm_task_with_semaphore(vm_result):
                async with semaphore:
                    return await self._analyze_on_vm(task, vm_result)

            vm_tasks = []
            for vm_result in task.edr_results:
                vm_task = vm_task_with_semaphore(vm_result)
                vm_tasks.append(vm_task)

            # 并行执行所有VM任务，收集结果和异常
            results = await asyncio.gather(*vm_tasks, return_exceptions=True)

            # 统计结果
            successful_vms = 0
            failed_vms = 0
            total_alerts = 0

            for i, result in enumerate(results):
                vm_result = task.edr_results[i]
                if isinstance(result, Exception):
                    logger.error(f"虚拟机 {vm_result.vm_name} 分析异常: {str(result)}")
                    failed_vms += 1
                else:
                    if vm_result.status == VMTaskStatus.COMPLETED:
                        successful_vms += 1
                        total_alerts += len(vm_result.alerts)
                    else:
                        failed_vms += 1

            logger.info(f"样本分析完成: {task.task_id} - 成功: {successful_vms}, 失败: {failed_vms}, 总告警: {total_alerts}")

        except Exception as e:
            logger.error(f"样本分析失败: {task.task_id} - {str(e)}")
            raise
    
    async def _analyze_on_vm(self, task: AnalysisTask, vm_result: VMTaskResult):

        vm_name = vm_result.vm_name
        task_start_time = datetime.utcnow()
        logger.info(f"开始在虚拟机 {vm_name} 上分析样本")

        # 获取VM资源池管理器
        if not self.vm_pool_manager:
            self.vm_pool_manager = await get_vm_pool_manager()

        # 获取VM资源
        vm_acquired = await self.vm_pool_manager.acquire_vm(vm_name, task.task_id)
        if not vm_acquired:
            raise Exception(f"无法获取VM资源: {vm_name}")

        try:

            vm_result.status = VMTaskStatus.PREPARING
            await self._prepare_vm(vm_name)


            vm_result.status = VMTaskStatus.UPLOADING
            await self._upload_sample_to_vm(task, vm_name)


            vm_result.status = VMTaskStatus.ANALYZING
            analysis_start_time = datetime.utcnow()

            # 执行样本文件
            execution_result = await self._execute_sample_in_vm(task, vm_name)

            # 智能等待分析完成 - 根据执行结果调整等待时间
            if execution_result.get('file_deleted_by_edr', False):
                # 文件被EDR删除，缩短等待时间
                analysis_wait_time = 10
                logger.info(f"文件已被EDR删除，缩短等待时间到 {analysis_wait_time} 秒")
            elif execution_result.get('execution_failed', False):
                # 执行失败，也缩短等待时间
                analysis_wait_time = 15
                logger.info(f"样本执行失败，缩短等待时间到 {analysis_wait_time} 秒")
            else:
                # 正常执行，使用标准等待时间
                analysis_wait_time = min(task.timeout, 25)  # 减少到25秒
                logger.info(f"样本正常执行，等待 {analysis_wait_time} 秒让杀软检测...")

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

            # 更新性能统计
            task_duration = (datetime.utcnow() - task_start_time).total_seconds()
            self.vm_pool_manager.update_stats(True, task_duration)

            logger.info(f"虚拟机 {vm_name} 分析完成，发现 {len(alerts)} 个告警，耗时 {task_duration:.1f} 秒")

        except Exception as e:
            vm_result.status = VMTaskStatus.FAILED
            vm_result.error_message = str(e)
            vm_result.end_time = datetime.utcnow()

            # 标记VM错误状态
            await self.vm_pool_manager.mark_vm_error(vm_name, str(e))

            # 更新性能统计
            task_duration = (datetime.utcnow() - task_start_time).total_seconds()
            self.vm_pool_manager.update_stats(False, task_duration)

            logger.error(f"虚拟机 {vm_name} 分析失败: {str(e)}，耗时 {task_duration:.1f} 秒")

            # 尝试恢复快照和完整清理
            try:
                await self._restore_vm_snapshot(vm_name)
                await self._complete_vm_cleanup(vm_name)
                # 如果恢复成功，重置错误状态
                await self.vm_pool_manager.reset_vm_error(vm_name)
            except Exception as restore_error:
                logger.error(f"恢复快照和清理失败: {str(restore_error)}")

        finally:
            # 释放VM资源
            await self.vm_pool_manager.release_vm(vm_name)
    
    async def _prepare_vm(self, vm_name: str):

        logger.info(f"准备虚拟机: {vm_name}")

        # 使用同步方法获取VM配置，避免协程问题
        vm_config = None
        if self.settings.windows and self.settings.windows.edr_analysis:
            for config in self.settings.windows.edr_analysis.vms:
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

        # 等待虚拟机就绪 - 增加超时时间到600秒
        await self._wait_for_vm_ready(vm_config.name, timeout=600)

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

    async def _wait_for_vm_ready(self, vm_name: str, timeout: int = 600):
        """
        等待虚拟机就绪 - 优化版本，增加详细日志和错误处理

        Args:
            vm_name: 虚拟机名称
            timeout: 超时时间（秒）
        """
        logger.info(f"等待虚拟机启动: {vm_name} (超时: {timeout}秒)")

        start_time = datetime.utcnow()
        check_interval = 10  # 增加检查间隔到10秒，减少频繁检查
        last_status = "unknown"
        status_change_count = 0

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            try:
                status = await self.vm_controller.get_status(vm_name)
                power_state = status.get("power_state", "unknown").lower()

                # 记录状态变化
                if power_state != last_status:
                    logger.info(f"虚拟机 {vm_name} 状态变化: {last_status} -> {power_state} (已等待 {elapsed:.1f}秒)")
                    last_status = power_state
                    status_change_count += 1

                if power_state in ["running", "poweredon"]:
                    logger.info(f"虚拟机 {vm_name} 已启动，等待系统就绪...")

                    # 给系统一些时间完全启动
                    await asyncio.sleep(30)

                    # 尝试执行简单命令检查系统是否就绪
                    vm_config = None
                    if self.settings.windows and self.settings.windows.edr_analysis:
                        for config in self.settings.windows.edr_analysis.vms:
                            if config.name == vm_name:
                                vm_config = config
                                break

                    if vm_config:
                        logger.info(f"检查虚拟机 {vm_name} 系统就绪状态...")
                        ready = await self._check_vm_system_ready(vm_config, max_attempts=5)
                        if ready:
                            logger.info(f"✅ 虚拟机 {vm_name} 系统已就绪 (总耗时: {elapsed + 30:.1f}秒)")
                            return
                        else:
                            logger.warning(f"虚拟机 {vm_name} 系统就绪检查失败，使用传统等待方式")
                            await asyncio.sleep(30)  # 额外等待30秒
                            logger.info(f"✅ 虚拟机 {vm_name} 已就绪（传统方式，总耗时: {elapsed + 60:.1f}秒）")
                            return
                    else:
                        # 如果无法获取配置，使用传统等待方式
                        await asyncio.sleep(30)
                        logger.info(f"✅ 虚拟机 {vm_name} 已就绪（无配置，总耗时: {elapsed + 30:.1f}秒）")
                        return
                else:
                    logger.debug(f"虚拟机 {vm_name} 当前状态: {power_state} (已等待 {elapsed:.1f}秒)")

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.warning(f"检查虚拟机 {vm_name} 状态失败: {str(e)} (已等待 {elapsed:.1f}秒)")
                await asyncio.sleep(check_interval)

        logger.error(f"❌ 虚拟机 {vm_name} 在 {timeout} 秒内未就绪，最终状态: {last_status}，状态变化次数: {status_change_count}")
        raise Exception(f"虚拟机 {vm_name} 在 {timeout} 秒内未就绪")

    async def _get_vm_config(self, vm_name: str):
        """获取虚拟机配置 - 优先从VM资源池获取"""
        if self.vm_pool_manager:
            config = await self.vm_pool_manager.get_vm_config(vm_name)
            if config:
                # 转换为类似原始配置对象的结构
                class VMConfig:
                    def __init__(self, config_dict):
                        for key, value in config_dict.items():
                            setattr(self, key, value)
                return VMConfig(config)

        # 回退到原始方法
        if self.settings.windows and self.settings.windows.edr_analysis:
            for config in self.settings.windows.edr_analysis.vms:
                if config.name == vm_name:
                    return config
        return None

    async def _check_vm_system_ready(self, vm_config, max_attempts: int = 5):
        """
        检查虚拟机系统是否就绪
        通过执行简单命令来验证系统状态
        """
        logger.info(f"开始检查虚拟机 {vm_config.name} 系统就绪状态...")

        for attempt in range(max_attempts):
            try:
                logger.debug(f"虚拟机 {vm_config.name} 系统就绪检查 (尝试 {attempt + 1}/{max_attempts})")

                # 执行简单的系统命令检查
                success, output = await self.vm_controller.execute_command_in_vm(
                    vm_config.name,
                    'echo "system_ready"',
                    vm_config.username,
                    vm_config.password,
                    timeout=30  # 增加超时时间
                )

                if success and "system_ready" in output:
                    logger.info(f"✅ 虚拟机 {vm_config.name} 系统就绪检查通过 (尝试 {attempt + 1})")
                    return True
                else:
                    logger.debug(f"虚拟机 {vm_config.name} 系统就绪检查未通过: success={success}, output='{output.strip()}'")

            except Exception as e:
                logger.debug(f"虚拟机 {vm_config.name} 系统就绪检查异常 (尝试 {attempt + 1}): {str(e)}")

            if attempt < max_attempts - 1:
                wait_time = 10 + (attempt * 5)  # 递增等待时间
                logger.debug(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)

        logger.warning(f"❌ 虚拟机 {vm_config.name} 系统就绪检查失败，已尝试 {max_attempts} 次")
        return False

    async def _upload_sample_to_vm(self, task: AnalysisTask, vm_name: str):

        logger.info(f"上传样本到虚拟机: {vm_name}")

        # 获取虚拟机配置 - 使用同步方法
        vm_config = None
        if self.settings.windows and self.settings.windows.edr_analysis:
            for config in self.settings.windows.edr_analysis.vms:
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

    async def _execute_sample_in_vm(self, task: AnalysisTask, vm_name: str) -> dict:
        """
        在虚拟机中执行样本文件

        Returns:
            dict: 执行结果信息，包含 file_deleted_by_edr, execution_failed 等状态
        """
        logger.info(f"在虚拟机 {vm_name} 中执行样本: {task.file_name}")

        result = {
            'file_deleted_by_edr': False,
            'execution_failed': False,
            'execution_success': False
        }

        # 获取虚拟机配置 - 使用同步方法
        vm_config = None
        if self.settings.windows and self.settings.windows.edr_analysis:
            for config in self.settings.windows.edr_analysis.vms:
                if config.name == vm_name:
                    vm_config = config
                    break

        if not vm_config:
            result['execution_failed'] = True
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

        # 缩短EDR检测等待时间
        logger.info("等待EDR初步检测文件...")
        await asyncio.sleep(3)  # 从5秒减少到3秒

        # 检查文件是否被EDR删除
        check_file_cmd = f"powershell -Command \"Test-Path '{sample_path}'\""
        file_exists, file_check_output = await self.vm_controller.execute_command_in_vm(
            vm_config.name, check_file_cmd, vm_config.username, vm_config.password, timeout=15  # 减少超时时间
        )

        if not file_exists or 'False' in file_check_output or 'false' in file_check_output.lower():
            logger.info(f"文件已被EDR删除: {sample_path}")
            logger.info("文件被删除，直接收集EDR日志，无需执行样本")
            result['file_deleted_by_edr'] = True
            return result

        logger.info(f"文件仍然存在: {sample_path}，继续执行样本")

        try:
            # 根据文件类型选择执行方式（使用实际要执行的文件名）
            file_extension = actual_file_name.lower().split('.')[-1] if '.' in actual_file_name else ''

            if file_extension in ['exe', 'com', 'scr', 'bat', 'cmd']:
                # Windows可执行文件
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

            # 在虚拟机中执行命令，缩短超时时间
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_config.name, f'powershell -Command "{execute_cmd}"',
                vm_config.username, vm_config.password, timeout=30  # 从60秒减少到30秒
            )

            if success:
                logger.info(f"样本执行命令发送成功: {vm_name}")
                result['execution_success'] = True
                if output.strip():
                    logger.info(f"执行输出: {output.strip()}")
            else:
                logger.warning(f"样本执行命令失败: {vm_name} - {output}")
                result['execution_failed'] = True

        except Exception as e:
            logger.error(f"执行样本时发生异常: {vm_name} - {str(e)}")
            result['execution_failed'] = True
            # 不抛出异常，继续分析流程

        return result

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

            # 使用detection_time进行时间比较
            current_detection_time = alert.detection_time or ""

            if key not in alert_map:
                # 第一次遇到这个组合，直接添加
                alert_map[key] = alert
                logger.debug(f"添加新报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {current_detection_time}")
            else:
                # 已存在相同组合，比较detection_time
                existing_alert = alert_map[key]
                existing_detection_time = existing_alert.detection_time or ""

                # 比较时间字符串（如果都有值才比较，否则保留第一个）
                if current_detection_time and existing_detection_time:
                    if current_detection_time > existing_detection_time:
                        # 当前报警更新，替换
                        alert_map[key] = alert
                        logger.debug(f"替换报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {existing_detection_time} -> {current_detection_time}")
                    else:
                        logger.debug(f"保留原报警: {alert.source} - {alert.alert_type} - {alert.file_path} - {existing_detection_time} (跳过 {current_detection_time})")
                elif current_detection_time and not existing_detection_time:
                    # 当前有时间，现有的没有时间，替换
                    alert_map[key] = alert
                    logger.debug(f"替换报警(时间更完整): {alert.source} - {alert.alert_type} - {alert.file_path}")
                else:
                    # 保留现有的报警
                    logger.debug(f"保留原报警: {alert.source} - {alert.alert_type} - {alert.file_path}")

        # 返回去重后的报警列表
        deduplicated_alerts = list(alert_map.values())

        if len(deduplicated_alerts) < len(alerts):
            logger.info(f"报警去重完成: {len(alerts)} -> {len(deduplicated_alerts)} (去除了 {len(alerts) - len(deduplicated_alerts)} 个重复报警)")

        return deduplicated_alerts

    async def _restore_vm_snapshot(self, vm_name: str):
        """恢复虚拟机快照并完全清理资源"""
        logger.info(f"恢复虚拟机快照: {vm_name}")

        # 获取虚拟机配置 - 使用同步方法
        vm_config = None
        if self.settings.windows and self.settings.windows.edr_analysis:
            for config in self.settings.windows.edr_analysis.vms:
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










