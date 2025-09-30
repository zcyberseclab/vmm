"""
任务管理模块 - 简化版（无Redis依赖）
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from app.models.task import AnalysisTask, TaskStatus, VMTaskResult, VMTaskStatus, EDRAlert, BehaviorAnalysisResult
from app.core.config import get_settings


class SimpleTaskManager:
    """简化的任务管理器（使用内存队列）"""

    def __init__(self):
        self.settings = get_settings()
        self.tasks: Dict[str, AnalysisTask] = {}
        self.task_queue = asyncio.Queue(maxsize=self.settings.task_settings.max_queue_size)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.processor_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """启动任务管理器"""
        if self.is_running:
            return

        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_tasks())
        logger.info("任务管理器已启动")

    async def stop(self):
        """停止任务管理器"""
        if not self.is_running:
            return

        self.is_running = False

        # 取消所有运行中的任务
        for task_id, task in self.running_tasks.items():
            task.cancel()
            logger.info(f"取消运行中的任务: {task_id}")

        # 停止处理器
        if self.processor_task and not self.processor_task.done():
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass

        logger.info("任务管理器已停止")

    async def submit_task(self, task: AnalysisTask) -> bool:
        """
        提交分析任务

        Args:
            task: 分析任务

        Returns:
            bool: 提交是否成功
        """
        try:
            # 检查队列是否已满
            if self.task_queue.full():
                logger.warning("任务队列已满，无法提交新任务")
                return False

            # 保存任务
            self.tasks[task.task_id] = task

            # 添加到队列（非阻塞）
            self.task_queue.put_nowait(task.task_id)

            logger.info(f"任务已提交到队列: {task.task_id}")
            return True

        except Exception as e:
            logger.error(f"提交任务失败: {str(e)}")
            return False
    
    async def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            AnalysisTask: 任务对象
        """
        return self.tasks.get(task_id)
    
    async def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[AnalysisTask]:
        """
        获取任务列表
        
        Args:
            status: 状态过滤
            limit: 数量限制
            
        Returns:
            List[AnalysisTask]: 任务列表
        """
        tasks = list(self.tasks.values())
        
        # 状态过滤
        if status:
            tasks = [task for task in tasks if task.status == status]
        
        # 按创建时间倒序排序
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        
        # 限制数量
        return tasks[:limit]
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 取消是否成功
        """
        try:
            task = self.tasks.get(task_id)
            if not task:
                return False

            # 如果任务正在运行，取消运行中的任务
            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                del self.running_tasks[task_id]

            # 更新任务状态
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()

            logger.info(f"任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            return False

    async def _process_tasks(self):
        """处理任务队列"""
        logger.info("任务处理器已启动")

        while self.is_running:
            try:
                # 从队列获取任务（带超时）
                try:
                    task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # 检查并发限制
                if len(self.running_tasks) >= self.settings.task_settings.concurrent_tasks:
                    # 重新放回队列
                    try:
                        self.task_queue.put_nowait(task_id)
                    except asyncio.QueueFull:
                        logger.warning(f"队列已满，丢弃任务: {task_id}")
                    await asyncio.sleep(1)
                    continue

                # 获取任务
                task = self.tasks.get(task_id)
                if not task or task.status != TaskStatus.PENDING:
                    continue

                # 创建任务协程
                task_coroutine = self._process_single_task(task)
                task_future = asyncio.create_task(task_coroutine)

                # 记录运行中的任务
                self.running_tasks[task_id] = task_future

                # 设置任务完成回调
                task_future.add_done_callback(
                    lambda fut, tid=task_id: self._on_task_completed(tid, fut)
                )

                logger.info(f"任务开始处理: {task_id}")

            except Exception as e:
                logger.error(f"任务处理器异常: {str(e)}")
                await asyncio.sleep(1)
    
    def _on_task_completed(self, task_id: str, future: asyncio.Future):
        """任务完成回调"""
        try:
            # 从运行中任务列表移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

            # 检查任务结果
            if future.cancelled():
                logger.info(f"任务被取消: {task_id}")
            elif future.exception():
                exception = future.exception()
                logger.error(f"任务执行异常: {task_id}")
                logger.error(f"异常类型: {type(exception).__name__}")
                logger.error(f"异常详情: {str(exception)}")
                # 如果有traceback信息，也打印出来
                import traceback
                if hasattr(exception, '__traceback__') and exception.__traceback__:
                    logger.error(f"异常堆栈:\n{''.join(traceback.format_tb(exception.__traceback__))}")
            else:
                logger.info(f"任务执行完成: {task_id}")

        except Exception as e:
            logger.error(f"任务完成回调异常: {str(e)}")

    async def _process_single_task(self, task: AnalysisTask):
        """
        处理单个任务

        Args:
            task: 分析任务
        """
        from app.services.analysis_engine import AnalysisEngine

        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()

            # 检查是否启用Sysmon分析
            if (hasattr(self.settings, 'sysmon_analysis') and
                self.settings.sysmon_analysis and
                self.settings.sysmon_analysis.enabled):

                logger.info(f"🔍 Sysmon分析已启用，同时运行Sysmon和EDR分析: {task.task_id}")

                # 先运行Sysmon分析
                await self._process_with_sysmon(task)

                # 然后运行标准EDR分析（如果任务指定了vm_names）
                if task.vm_names:
                    logger.info(f"📊 开始标准EDR分析: {task.task_id} 在 {len(task.vm_names)} 个VM上")
                    engine = AnalysisEngine()
                    await engine.analyze_sample(task)
                else:
                    logger.info(f"📊 跳过标准EDR分析: 任务 {task.task_id} 未指定vm_names")

            else:
                logger.info(f"📊 使用标准EDR分析引擎分析任务: {task.task_id}")
                # 创建标准分析引擎
                engine = AnalysisEngine()
                # 执行分析
                await engine.analyze_sample(task)

            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()

            logger.info(f"任务分析完成: {task.task_id}")

        except asyncio.CancelledError:
            # 任务被取消
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            logger.info(f"任务被取消: {task.task_id}")
            raise  # 重新抛出以正确处理取消

        except Exception as e:
            # 任务执行失败
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            logger.error(f"任务执行失败: {task.task_id} - {str(e)}")

    async def _process_with_sysmon(self, task: AnalysisTask):
        """
        使用Sysmon引擎处理任务

        Args:
            task: 分析任务
        """
        from app.services.sysmon import get_sysmon_engine

        try:
            # 获取Sysmon分析引擎
            sysmon_engine = await get_sysmon_engine()

            # 创建行为分析结果
            start_time = datetime.utcnow()
            behavior_result = BehaviorAnalysisResult(
                analysis_engine="sysmon",
                status=VMTaskStatus.PENDING,
                start_time=start_time
            )
            task.behavior_results = behavior_result

            logger.info(f"🚀 开始Sysmon分析: {task.file_name}")

            # 更新状态
            behavior_result.status = VMTaskStatus.ANALYZING

            # 执行Sysmon分析
            analysis_result = await sysmon_engine.analyze_sample(
                sample_path=task.file_path,
                sample_hash=task.file_hash,
                analysis_timeout=task.timeout,
                config_type=self.settings.sysmon_analysis.config_type
            )

            # 将Sysmon分析结果转换为标准格式
            alerts = self._convert_sysmon_to_alerts(analysis_result)
            behavior_result.alerts = alerts
            behavior_result.events_collected = analysis_result.get('raw_events_count', 0)

            # 更新状态
            end_time = datetime.utcnow()
            behavior_result.status = VMTaskStatus.COMPLETED
            behavior_result.end_time = end_time
            behavior_result.analysis_duration = (end_time - start_time).total_seconds()

            logger.info(f"✅ Sysmon分析完成: {task.file_name}, 生成 {len(alerts)} 个告警")

        except Exception as e:
            logger.error(f"❌ Sysmon分析失败: {task.file_name} - {str(e)}")
            if task.behavior_results:
                task.behavior_results.status = VMTaskStatus.FAILED
                task.behavior_results.end_time = datetime.utcnow()
                task.behavior_results.error_message = str(e)
            raise

    def _convert_sysmon_to_alerts(self, sysmon_result: dict) -> list:
        """
        将Sysmon分析结果转换为标准告警格式

        Args:
            sysmon_result: Sysmon分析结果

        Returns:
            list: 标准告警列表
        """
        # Sysmon事件ID映射表
        sysmon_event_map = {
            1: {"name": "Process Creation", "description": "进程创建事件", "severity": "medium"},
            2: {"name": "File Creation Time Changed", "description": "文件创建时间更改", "severity": "low"},
            3: {"name": "Network Connection", "description": "网络连接事件", "severity": "medium"},
            4: {"name": "Sysmon Service State Changed", "description": "Sysmon服务状态更改", "severity": "info"},
            5: {"name": "Process Terminated", "description": "进程终止事件", "severity": "low"},
            6: {"name": "Driver Loaded", "description": "驱动程序加载", "severity": "medium"},
            7: {"name": "Image Loaded", "description": "镜像/DLL加载", "severity": "low"},
            8: {"name": "CreateRemoteThread", "description": "远程线程创建", "severity": "high"},
            9: {"name": "RawAccessRead", "description": "原始磁盘访问", "severity": "high"},
            10: {"name": "ProcessAccess", "description": "进程访问事件", "severity": "medium"},
            11: {"name": "FileCreate", "description": "文件创建事件", "severity": "medium"},
            12: {"name": "RegistryEvent (Object create and delete)", "description": "注册表对象创建/删除", "severity": "medium"},
            13: {"name": "RegistryEvent (Value Set)", "description": "注册表值设置", "severity": "medium"},
            14: {"name": "RegistryEvent (Key and Value Rename)", "description": "注册表键值重命名", "severity": "medium"},
            15: {"name": "FileCreateStreamHash", "description": "文件流创建", "severity": "medium"},
            16: {"name": "ServiceConfigurationChange", "description": "服务配置更改", "severity": "medium"},
            17: {"name": "PipeEvent (Pipe Created)", "description": "命名管道创建", "severity": "medium"},
            18: {"name": "PipeEvent (Pipe Connected)", "description": "命名管道连接", "severity": "medium"},
            19: {"name": "WmiEvent (WmiEventFilter activity detected)", "description": "WMI事件过滤器活动", "severity": "high"},
            20: {"name": "WmiEvent (WmiEventConsumer activity detected)", "description": "WMI事件消费者活动", "severity": "high"},
            21: {"name": "WmiEvent (WmiEventConsumerToFilter activity detected)", "description": "WMI事件消费者到过滤器活动", "severity": "high"},
            22: {"name": "DNSEvent (DNS query)", "description": "DNS查询事件", "severity": "medium"},
            23: {"name": "FileDelete (File Delete archived)", "description": "文件删除事件", "severity": "medium"},
            24: {"name": "ClipboardChange (New content in the clipboard)", "description": "剪贴板内容更改", "severity": "low"},
            25: {"name": "ProcessTampering (Process image change)", "description": "进程镜像篡改", "severity": "high"},
            26: {"name": "FileDeleteDetected (File Delete logged)", "description": "文件删除检测", "severity": "medium"},
            27: {"name": "FileBlockExecutable", "description": "可执行文件阻止", "severity": "high"},
            28: {"name": "FileBlockShredding", "description": "文件粉碎阻止", "severity": "medium"},
            29: {"name": "FileExecutableDetected", "description": "可执行文件检测", "severity": "medium"},
        }

        alerts = []

        try:
            sysmon_analysis = sysmon_result.get('sysmon_analysis', {})

            # 基于事件类型创建告警
            event_types = sysmon_analysis.get('event_types', {})
            for event_id, count in event_types.items():
                if count > 0:
                    # 获取事件详细信息
                    event_info = sysmon_event_map.get(int(event_id), {
                        "name": f"Unknown Event {event_id}",
                        "description": f"未知Sysmon事件类型 {event_id}",
                        "severity": "medium"
                    })

                    alert = EDRAlert(
                        alert_type=f'Sysmon Event ID {event_id}: {event_info["name"]}',
                        severity=event_info["severity"],
                        detection_time=sysmon_result.get('timestamp'),
                        event_id=str(event_id),
                        detect_reason=f'检测到 {count} 个 {event_info["description"]} 事件',
                        source='sysmon'
                    )
                    alerts.append(alert)

            # 基于详细事件信息创建告警
            detailed_events = sysmon_analysis.get('detailed_events', [])
            process_events = {}
            network_events = []
            file_events = []

            # 分类详细事件
            for event in detailed_events:
                event_type = event.get('event_type', '')
                if event_type == 'Process Creation':
                    image = event.get('image', 'Unknown')
                    if image not in process_events:
                        process_events[image] = []
                    process_events[image].append(event)
                elif event_type == 'Network Connection':
                    network_events.append(event)
                elif event_type in ['File Create', 'File Delete']:
                    file_events.append(event)

            # 基于进程活动创建告警（使用详细信息）
            for process, events in process_events.items():
                if len(events) > 0:
                    # 获取第一个事件的详细信息作为代表
                    sample_event = events[0]
                    alert = EDRAlert(
                        alert_type=f'Process Activity: {process}',
                        severity='low',
                        detection_time=sysmon_result.get('timestamp'),
                        process_name=process.split('\\')[-1] if '\\' in process else process,
                        command_line=sample_event.get('command_line', ''),
                        file_path=process,
                        detect_reason=f'检测到进程 {process} 执行了 {len(events)} 次',
                        source='sysmon'
                    )
                    alerts.append(alert)

            # 基于网络连接创建告警（使用详细信息）
            if network_events:
                unique_connections = {}
                for event in network_events:
                    key = f"{event.get('destination_ip', '')}:{event.get('destination_port', '')}"
                    if key not in unique_connections:
                        unique_connections[key] = []
                    unique_connections[key].append(event)

                # 获取第一个网络事件的详细信息
                sample_net_event = network_events[0] if network_events else {}
                alert = EDRAlert(
                    alert_type='Network Activity (Detailed)',
                    severity='medium',
                    detection_time=sysmon_result.get('timestamp'),
                    source_ip=sample_net_event.get('source_ip', ''),
                    destination_ip=sample_net_event.get('destination_ip', ''),
                    process_name=sample_net_event.get('image', '').split('\\')[-1] if sample_net_event.get('image') else '',
                    detect_reason=f'检测到 {len(network_events)} 个网络连接，涉及 {len(unique_connections)} 个不同目标',
                    source='sysmon'
                )
                alerts.append(alert)

            # 基于文件操作创建告警（使用详细信息）
            if file_events:
                file_creates = [e for e in file_events if e.get('event_type') == 'File Create']
                file_deletes = [e for e in file_events if e.get('event_type') == 'File Delete']

                if file_creates:
                    sample_file_event = file_creates[0]
                    alert = EDRAlert(
                        alert_type='File Creation Activity (Detailed)',
                        severity='medium',
                        detection_time=sysmon_result.get('timestamp'),
                        file_path=sample_file_event.get('target_filename', ''),
                        process_name=sample_file_event.get('image', '').split('\\')[-1] if sample_file_event.get('image') else '',
                        detect_reason=f'检测到 {len(file_creates)} 个文件创建事件',
                        source='sysmon'
                    )
                    alerts.append(alert)

                if file_deletes:
                    sample_delete_event = file_deletes[0]
                    alert = EDRAlert(
                        alert_type='File Deletion Activity (Detailed)',
                        severity='medium',
                        detection_time=sysmon_result.get('timestamp'),
                        file_path=sample_delete_event.get('target_filename', ''),
                        process_name=sample_delete_event.get('image', '').split('\\')[-1] if sample_delete_event.get('image') else '',
                        detect_reason=f'检测到 {len(file_deletes)} 个文件删除事件',
                        source='sysmon'
                    )
                    alerts.append(alert)

            # 基于网络连接创建告警
            network_connections = sysmon_analysis.get('network_connections', [])
            if network_connections:
                alert = EDRAlert(
                    alert_type='Network Activity',
                    severity='medium',
                    detection_time=sysmon_result.get('timestamp'),
                    detect_reason=f'检测到 {len(network_connections)} 个网络连接',
                    source='sysmon'
                )
                alerts.append(alert)

            # 如果没有生成任何告警，创建一个基础告警
            if not alerts:
                alert = EDRAlert(
                    alert_type='Sysmon Analysis Complete',
                    severity='info',
                    detection_time=sysmon_result.get('timestamp'),
                    detect_reason=f'Sysmon分析完成，收集了 {sysmon_result.get("raw_events_count", 0)} 个事件',
                    source='sysmon'
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"转换Sysmon结果为告警时出错: {str(e)}")
            # 创建错误告警
            alert = EDRAlert(
                alert_type='Sysmon Conversion Error',
                severity='error',
                detection_time=sysmon_result.get('timestamp'),
                detect_reason=f'转换Sysmon分析结果时出错: {str(e)}',
                source='sysmon'
            )
            alerts.append(alert)

        return alerts

    async def get_queue_status(self) -> Dict[str, int]:
        """
        获取队列状态

        Returns:
            Dict[str, int]: 队列状态信息
        """
        return {
            "pending_tasks": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "total_tasks": len(self.tasks),
            "completed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED]),
            "queue_capacity": self.settings.task_settings.max_queue_size,
            "is_running": self.is_running
        }

    async def cleanup_old_tasks(self, days: int = 7):
        """
        清理旧任务

        Args:
            days: 保留天数
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if (task.completed_at and task.completed_at < cutoff_time and
                    task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]):
                    tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                del self.tasks[task_id]

            logger.info(f"清理了 {len(tasks_to_remove)} 个旧任务")

        except Exception as e:
            logger.error(f"清理旧任务失败: {str(e)}")


# 全局任务管理器实例
task_manager = SimpleTaskManager()
