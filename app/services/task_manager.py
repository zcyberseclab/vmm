"""
任务管理模块 - 简化版（无Redis依赖）
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from app.models.task import AnalysisTask, TaskStatus, VMTaskResult, VMTaskStatus
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

            # 创建分析引擎
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
