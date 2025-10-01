"""
任务管理模块 - 简化版（无Redis依赖）
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from app.models.task import AnalysisTask, TaskStatus, VMTaskResult, VMTaskStatus, EDRAlert, BehaviorAnalysisResult, SysmonEvent, BehaviorStatistics
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

            # 将Sysmon分析结果转换为Event格式（保留原始数据）
            detailed_events = analysis_result.get('sysmon_analysis', {}).get('detailed_events', [])
            events = self._convert_to_events(detailed_events)
            behavior_result.events = events

            # 生成统计信息
            statistics = self._generate_behavior_statistics(detailed_events, analysis_result)
            behavior_result.statistics = statistics

            # 更新状态
            end_time = datetime.utcnow()
            behavior_result.status = VMTaskStatus.COMPLETED
            behavior_result.end_time = end_time

            logger.info(f"✅ Sysmon分析完成: {task.file_name}, 收集 {len(events)} 个事件")

        except Exception as e:
            logger.error(f"❌ Sysmon分析失败: {task.file_name} - {str(e)}")
            if task.behavior_results:
                task.behavior_results.status = VMTaskStatus.FAILED
                task.behavior_results.end_time = datetime.utcnow()
                task.behavior_results.error_message = str(e)
            raise

    def _convert_to_events(self, detailed_events: list) -> List[SysmonEvent]:
        """
        将详细事件转换为SysmonEvent对象（扁平化结构，提取关键字段）

        Args:
            detailed_events: 详细事件列表

        Returns:
            List[SysmonEvent]: SysmonEvent对象列表
        """
        events = []

        for event in detailed_events:
            try:
                # 提取parsed_fields中的关键信息
                parsed_fields = event.get('parsed_fields', {})

                # 从UtcTime字段获取格式化的时间戳
                utc_time = parsed_fields.get('UtcTime', event.get('timestamp', ''))

                # 创建简化的SysmonEvent对象
                event_obj = SysmonEvent(
                    event_id=str(event.get('event_id', '')),
                    event_name=event.get('event_type', ''),
                    timestamp=utc_time,
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

                    # 新增字段 - 从parsed_fields提取
                    event_type=event.get('event_type', ''),
                    source_process_guid=parsed_fields.get('SourceProcessGUID', ''),
                    source_image=parsed_fields.get('SourceImage', event.get('source_image', '')),
                    target_process_guid=parsed_fields.get('TargetProcessGUID', ''),
                    target_image=parsed_fields.get('TargetImage', event.get('target_image', '')),
                    call_trace=parsed_fields.get('CallTrace', event.get('call_trace', '')),
                    source_user=parsed_fields.get('SourceUser', ''),
                    target_user=parsed_fields.get('TargetUser', '')
                )
                events.append(event_obj)
            except Exception as e:
                logger.warning(f"转换SysmonEvent时出错: {e}, 事件: {event}")
                continue

        return events

    def _generate_behavior_statistics(self, detailed_events: list, analysis_result: dict) -> BehaviorStatistics:
        """
        生成行为分析统计信息

        Args:
            detailed_events: 详细事件列表
            analysis_result: 分析结果

        Returns:
            BehaviorStatistics: 统计信息对象
        """
        statistics = BehaviorStatistics()

        # 基本统计
        statistics.total_events = len(detailed_events)

        # 事件类型统计
        event_types = {}
        process_images = set()
        destinations = set()
        timestamps = []

        for event in detailed_events:
            event_id = str(event.get('event_id', ''))
            timestamp = event.get('timestamp', '')

            # 事件类型统计
            if event_id:
                event_types[event_id] = event_types.get(event_id, 0) + 1

            # 收集时间戳
            if timestamp:
                timestamps.append(timestamp)

            # 根据事件类型进行统计
            if event_id == '1':  # Process Creation
                statistics.process_creations += 1
                image = event.get('image', '')
                if image:
                    process_images.add(image)
            elif event_id == '11':  # File Create
                statistics.file_creations += 1
            elif event_id == '23':  # File Delete
                statistics.file_deletions += 1
            elif event_id == '3':  # Network Connection
                statistics.network_connections += 1
                dest_ip = event.get('destination_ip', '')
                if dest_ip:
                    destinations.add(dest_ip)
            elif event_id == '22':  # DNS Query
                statistics.dns_queries += 1
            elif event_id == '10':  # Process Access
                statistics.process_accesses += 1
            elif event_id == '7':  # Image Load
                statistics.image_loads += 1

        # 设置统计结果
        statistics.event_types = event_types
        statistics.unique_processes = len(process_images)
        statistics.unique_destinations = len(destinations)

        # 时间范围
        if timestamps:
            timestamps.sort()
            statistics.first_event_time = timestamps[0]
            statistics.last_event_time = timestamps[-1]

        # 分析持续时间
        statistics.analysis_duration = analysis_result.get('analysis_duration')

        return statistics

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
