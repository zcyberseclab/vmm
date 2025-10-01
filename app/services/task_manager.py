"""
任务管理模块 - 简化版（无Redis依赖）
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from app.models.task import AnalysisTask, TaskStatus, VMTaskResult, VMTaskStatus, EDRAlert, BehaviorAnalysisResult, SysmonAlert, SysmonEvent
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

            # 将Sysmon分析结果转换为SysmonAlert格式
            alerts = self._convert_sysmon_to_alerts(analysis_result)
            behavior_result.alerts = alerts
            behavior_result.events_collected = analysis_result.get('raw_events_count', 0)

            # 存储原始事件
            detailed_events = analysis_result.get('sysmon_analysis', {}).get('detailed_events', [])
            raw_events = self._convert_sysmon_events_to_objects(detailed_events)
            behavior_result.raw_events = raw_events

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
        将Sysmon分析结果转换为SysmonAlert格式

        Args:
            sysmon_result: Sysmon分析结果

        Returns:
            list: SysmonAlert列表
        """
        alerts = []

        try:
            sysmon_analysis = sysmon_result.get('sysmon_analysis', {})
            detailed_events = sysmon_analysis.get('detailed_events', [])

            # 转换详细事件为SysmonEvent对象
            sysmon_events = self._convert_sysmon_events_to_objects(detailed_events)

            # 按事件类型分组
            events_by_type = {}
            for event in sysmon_events:
                event_type = event.event_name
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)

            # 创建进程创建告警
            if 'Process Creation' in events_by_type:
                process_events = events_by_type['Process Creation']
                processes_by_image = {}

                for event in process_events:
                    image = event.image or 'Unknown'
                    if image not in processes_by_image:
                        processes_by_image[image] = []
                    processes_by_image[image].append(event)

                for image, events in processes_by_image.items():
                    process_name = image.split('\\')[-1] if '\\' in image else image
                    command_lines = [e.command_line for e in events if e.command_line]
                    users = [e.user for e in events if e.user]

                    alert = SysmonAlert(
                        severity='medium' if any(keyword in image.lower() for keyword in ['powershell', 'cmd']) else 'low',
                        alert_type=f'Process Creation: {process_name}',
                        detection_time=sysmon_result.get('timestamp', ''),
                        event_count=len(events),
                        event_ids=['1'],
                        processes_involved=[process_name],
                        primary_process=image,
                        command_lines=command_lines,
                        description=f'检测到进程 {process_name} 创建了 {len(events)} 次',
                        detection_reason=f'进程 {image} 被创建 {len(events)} 次，命令行: {"; ".join(command_lines[:3])}',
                        related_events=events
                    )
                    alerts.append(alert)

            # 创建文件操作告警
            file_create_events = events_by_type.get('File Create', [])
            if file_create_events:
                files_created = [e.target_filename for e in file_create_events if e.target_filename]
                processes_involved = list(set([e.image.split('\\')[-1] if e.image and '\\' in e.image else e.image for e in file_create_events if e.image]))

                alert = SysmonAlert(
                    severity='medium',
                    alert_type='File Creation Activity',
                    detection_time=sysmon_result.get('timestamp', ''),
                    event_count=len(file_create_events),
                    event_ids=['11'],
                    processes_involved=processes_involved,
                    files_created=files_created,
                    description=f'检测到 {len(file_create_events)} 个文件创建事件',
                    detection_reason=f'创建了 {len(files_created)} 个文件，涉及进程: {", ".join(processes_involved[:5])}',
                    related_events=file_create_events
                )
                alerts.append(alert)

            file_delete_events = events_by_type.get('File Delete', [])
            if file_delete_events:
                files_deleted = [e.target_filename for e in file_delete_events if e.target_filename]
                processes_involved = list(set([e.image.split('\\')[-1] if e.image and '\\' in e.image else e.image for e in file_delete_events if e.image]))

                alert = SysmonAlert(
                    severity='medium',
                    alert_type='File Deletion Activity',
                    detection_time=sysmon_result.get('timestamp', ''),
                    event_count=len(file_delete_events),
                    event_ids=['23'],
                    processes_involved=processes_involved,
                    files_deleted=files_deleted,
                    description=f'检测到 {len(file_delete_events)} 个文件删除事件',
                    detection_reason=f'删除了 {len(files_deleted)} 个文件，涉及进程: {", ".join(processes_involved[:5])}',
                    related_events=file_delete_events
                )
                alerts.append(alert)

            # 创建网络连接告警
            network_events = events_by_type.get('Network Connection', [])
            if network_events:
                connections = []
                processes_involved = set()
                remote_addresses = set()

                for event in network_events:
                    connection_info = {
                        'source_ip': event.source_ip or '',
                        'source_port': event.source_port or '',
                        'destination_ip': event.destination_ip or '',
                        'destination_port': event.destination_port or '',
                        'protocol': event.protocol or '',
                        'process': event.image or '',
                        'timestamp': event.timestamp or ''
                    }
                    connections.append(connection_info)

                    if event.image:
                        process_name = event.image.split('\\')[-1] if '\\' in event.image else event.image
                        processes_involved.add(process_name)

                    if event.destination_ip:
                        remote_addresses.add(event.destination_ip)

                alert = SysmonAlert(
                    severity='medium',
                    alert_type='Network Connection Activity',
                    detection_time=sysmon_result.get('timestamp', ''),
                    event_count=len(network_events),
                    event_ids=['3'],
                    processes_involved=list(processes_involved),
                    network_connections=connections,
                    remote_addresses=list(remote_addresses),
                    description=f'检测到 {len(network_events)} 个网络连接事件',
                    detection_reason=f'建立了 {len(connections)} 个网络连接，涉及进程: {", ".join(list(processes_involved)[:5])}',
                    related_events=network_events
                )
                alerts.append(alert)

            # 创建DNS查询告警
            dns_events = events_by_type.get('DNS query', [])
            if dns_events:
                dns_queries = []
                processes_involved = set()

                for event in dns_events:
                    dns_info = {
                        'query_name': event.query_name or '',
                        'query_results': event.query_results or '',
                        'process': event.image or '',
                        'timestamp': event.timestamp or ''
                    }
                    dns_queries.append(dns_info)

                    if event.image:
                        process_name = event.image.split('\\')[-1] if '\\' in event.image else event.image
                        processes_involved.add(process_name)

                alert = SysmonAlert(
                    severity='medium',
                    alert_type='DNS Query Activity',
                    detection_time=sysmon_result.get('timestamp', ''),
                    event_count=len(dns_events),
                    event_ids=['22'],
                    processes_involved=list(processes_involved),
                    dns_queries=dns_queries,
                    description=f'检测到 {len(dns_events)} 个DNS查询事件',
                    detection_reason=f'执行了 {len(dns_queries)} 个DNS查询，涉及进程: {", ".join(list(processes_involved)[:5])}',
                    related_events=dns_events
                )
                alerts.append(alert)

            # 如果没有生成任何告警，创建一个基础告警
            if not alerts:
                alert = SysmonAlert(
                    severity='info',
                    alert_type='Sysmon Analysis Complete',
                    detection_time=sysmon_result.get('timestamp', ''),
                    event_count=len(sysmon_events),
                    description='Sysmon分析完成',
                    detection_reason=f'Sysmon分析完成，收集了 {len(sysmon_events)} 个事件',
                    related_events=sysmon_events
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"转换Sysmon结果为告警时出错: {str(e)}")
            # 创建错误告警
            alert = SysmonAlert(
                severity='high',
                alert_type='Sysmon Conversion Error',
                detection_time=sysmon_result.get('timestamp', ''),
                description='转换Sysmon分析结果时出错',
                detection_reason=f'转换Sysmon分析结果时出错: {str(e)}'
            )
            alerts.append(alert)

        return alerts

    def _convert_sysmon_events_to_objects(self, detailed_events: list) -> List[SysmonEvent]:
        """
        将详细事件转换为SysmonEvent对象

        Args:
            detailed_events: 详细事件列表

        Returns:
            List[SysmonEvent]: SysmonEvent对象列表
        """
        sysmon_events = []

        for event in detailed_events:
            try:
                sysmon_event = SysmonEvent(
                    event_id=str(event.get('event_id', '')),
                    event_name=event.get('event_type', ''),
                    timestamp=event.get('timestamp', ''),
                    computer_name=event.get('computer_name', ''),

                    # 进程相关信息
                    process_id=event.get('process_id', ''),
                    process_name=event.get('process_name', ''),
                    image=event.get('image', ''),
                    command_line=event.get('command_line', ''),
                    parent_process_id=event.get('parent_process_id', ''),
                    parent_image=event.get('parent_image', ''),
                    user=event.get('user', ''),

                    # 文件相关信息
                    target_filename=event.get('target_filename', ''),
                    creation_utc_time=event.get('creation_utc_time', ''),

                    # 网络相关信息
                    source_ip=event.get('source_ip', ''),
                    source_port=event.get('source_port', ''),
                    destination_ip=event.get('destination_ip', ''),
                    destination_port=event.get('destination_port', ''),
                    protocol=event.get('protocol', ''),

                    # DNS相关信息
                    query_name=event.get('query_name', ''),
                    query_results=event.get('query_results', ''),

                    # 进程访问相关信息
                    source_process_id=event.get('source_process_id', ''),
                    target_process_id=event.get('target_process_id', ''),
                    granted_access=event.get('granted_access', ''),

                    # 镜像加载相关信息
                    image_loaded=event.get('image_loaded', ''),
                    signature=event.get('signature', ''),
                    signed=event.get('signed', ''),

                    # 原始数据
                    raw_data=event
                )
                sysmon_events.append(sysmon_event)
            except Exception as e:
                logger.warning(f"转换Sysmon事件时出错: {e}, 事件: {event}")
                continue

        return sysmon_events

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
