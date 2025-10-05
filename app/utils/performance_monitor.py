"""
性能监控模块
用于监控系统性能指标和分析时间
"""

import time
import asyncio
import psutil
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    # 分析类型和状态
    analysis_type: str = ""  # "sysmon", "edr", "parallel"
    status: str = "running"  # "running", "completed", "failed"
    
    # 系统资源使用
    cpu_usage_start: float = 0.0
    cpu_usage_end: float = 0.0
    memory_usage_start: float = 0.0
    memory_usage_end: float = 0.0
    
    # 分析详情
    vm_count: int = 0
    event_count: int = 0
    alert_count: int = 0
    
    # 错误信息
    error_message: str = ""


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.system_stats: List[Dict] = []
        self.monitoring_active = True
        
    def start_task_monitoring(self, task_id: str, analysis_type: str = "", vm_count: int = 0) -> PerformanceMetrics:
        """开始监控任务性能"""
        
        # 获取当前系统资源使用情况
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory_usage = psutil.virtual_memory().percent
        
        metrics = PerformanceMetrics(
            task_id=task_id,
            start_time=datetime.utcnow(),
            analysis_type=analysis_type,
            vm_count=vm_count,
            cpu_usage_start=cpu_usage,
            memory_usage_start=memory_usage
        )
        
        self.metrics[task_id] = metrics
        
        logger.info(f"📊 开始监控任务: {task_id} ({analysis_type}) - CPU: {cpu_usage:.1f}%, 内存: {memory_usage:.1f}%")
        
        return metrics
    
    def end_task_monitoring(self, task_id: str, status: str = "completed", 
                          event_count: int = 0, alert_count: int = 0, error_message: str = ""):
        """结束任务性能监控"""
        
        if task_id not in self.metrics:
            logger.warning(f"未找到任务监控记录: {task_id}")
            return
        
        metrics = self.metrics[task_id]
        
        # 更新结束时间和状态
        metrics.end_time = datetime.utcnow()
        metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
        metrics.status = status
        metrics.event_count = event_count
        metrics.alert_count = alert_count
        metrics.error_message = error_message
        
        # 获取结束时的系统资源使用情况
        metrics.cpu_usage_end = psutil.cpu_percent(interval=0.1)
        metrics.memory_usage_end = psutil.virtual_memory().percent
        
        # 记录性能日志
        self._log_performance_summary(metrics)
        
        return metrics
    
    def _log_performance_summary(self, metrics: PerformanceMetrics):
        """记录性能摘要"""
        
        status_emoji = "✅" if metrics.status == "completed" else "❌" if metrics.status == "failed" else "⚠️"
        
        logger.info(f"{status_emoji} 任务完成: {metrics.task_id}")
        logger.info(f"   📈 分析类型: {metrics.analysis_type}")
        logger.info(f"   ⏱️  总耗时: {metrics.duration:.1f}秒")
        logger.info(f"   🖥️  CPU使用: {metrics.cpu_usage_start:.1f}% → {metrics.cpu_usage_end:.1f}%")
        logger.info(f"   💾 内存使用: {metrics.memory_usage_start:.1f}% → {metrics.memory_usage_end:.1f}%")
        
        if metrics.vm_count > 0:
            logger.info(f"   🖥️  VM数量: {metrics.vm_count}")
            
        if metrics.event_count > 0:
            logger.info(f"   📋 事件数量: {metrics.event_count}")
            
        if metrics.alert_count > 0:
            logger.info(f"   🚨 告警数量: {metrics.alert_count}")
            
        if metrics.error_message:
            logger.info(f"   ❌ 错误信息: {metrics.error_message}")
    
    def get_task_metrics(self, task_id: str) -> Optional[PerformanceMetrics]:
        """获取任务性能指标"""
        return self.metrics.get(task_id)
    
    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """获取所有性能指标"""
        return self.metrics.copy()
    
    def get_performance_summary(self, hours: int = 24) -> Dict:
        """获取性能摘要统计"""
        
        cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
        recent_metrics = [
            m for m in self.metrics.values() 
            if m.start_time.timestamp() > cutoff_time and m.status in ["completed", "failed"]
        ]
        
        if not recent_metrics:
            return {"message": f"过去{hours}小时内没有完成的任务"}
        
        # 按分析类型分组统计
        stats_by_type = {}
        for metrics in recent_metrics:
            analysis_type = metrics.analysis_type or "unknown"
            if analysis_type not in stats_by_type:
                stats_by_type[analysis_type] = {
                    "count": 0,
                    "success_count": 0,
                    "total_duration": 0,
                    "avg_duration": 0,
                    "min_duration": float('inf'),
                    "max_duration": 0,
                    "total_events": 0,
                    "total_alerts": 0
                }
            
            stats = stats_by_type[analysis_type]
            stats["count"] += 1
            
            if metrics.status == "completed":
                stats["success_count"] += 1
            
            if metrics.duration:
                stats["total_duration"] += metrics.duration
                stats["min_duration"] = min(stats["min_duration"], metrics.duration)
                stats["max_duration"] = max(stats["max_duration"], metrics.duration)
            
            stats["total_events"] += metrics.event_count
            stats["total_alerts"] += metrics.alert_count
        
        # 计算平均值
        for stats in stats_by_type.values():
            if stats["count"] > 0:
                stats["avg_duration"] = stats["total_duration"] / stats["count"]
                stats["success_rate"] = stats["success_count"] / stats["count"] * 100
            
            if stats["min_duration"] == float('inf'):
                stats["min_duration"] = 0
        
        # 总体统计
        total_tasks = len(recent_metrics)
        successful_tasks = len([m for m in recent_metrics if m.status == "completed"])
        total_duration = sum(m.duration or 0 for m in recent_metrics)
        avg_duration = total_duration / total_tasks if total_tasks > 0 else 0
        
        summary = {
            "time_period": f"过去{hours}小时",
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": successful_tasks / total_tasks * 100 if total_tasks > 0 else 0,
            "avg_duration": avg_duration,
            "total_duration": total_duration,
            "stats_by_type": stats_by_type
        }
        
        return summary
    
    async def start_system_monitoring(self, interval: int = 30):
        """启动系统资源监控"""
        logger.info(f"🔍 启动系统资源监控，间隔: {interval}秒")
        
        while self.monitoring_active:
            try:
                # 收集系统资源信息
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # 网络IO统计
                net_io = psutil.net_io_counters()
                
                system_stat = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3),
                    "network_bytes_sent": net_io.bytes_sent,
                    "network_bytes_recv": net_io.bytes_recv
                }
                
                self.system_stats.append(system_stat)
                
                # 只保留最近1000条记录
                if len(self.system_stats) > 1000:
                    self.system_stats = self.system_stats[-1000:]
                
                # 如果资源使用率过高，记录警告
                if cpu_percent > 90:
                    logger.warning(f"⚠️ CPU使用率过高: {cpu_percent:.1f}%")
                
                if memory.percent > 90:
                    logger.warning(f"⚠️ 内存使用率过高: {memory.percent:.1f}%")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"系统监控错误: {str(e)}")
                await asyncio.sleep(interval)
    
    def stop_system_monitoring(self):
        """停止系统资源监控"""
        self.monitoring_active = False
        logger.info("🛑 系统资源监控已停止")
    
    def get_system_stats(self, limit: int = 100) -> List[Dict]:
        """获取系统资源统计"""
        return self.system_stats[-limit:] if self.system_stats else []
    
    def clear_old_metrics(self, hours: int = 168):  # 默认保留7天
        """清理旧的性能指标"""
        cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
        
        old_task_ids = [
            task_id for task_id, metrics in self.metrics.items()
            if metrics.start_time.timestamp() < cutoff_time
        ]
        
        for task_id in old_task_ids:
            del self.metrics[task_id]
        
        logger.info(f"🧹 清理了 {len(old_task_ids)} 个旧的性能指标记录")


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    return performance_monitor
