"""
任务数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_serializer
import uuid
from app.utils.helpers import format_timestamp_to_local


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 等待中
    RUNNING = "running"          # 运行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"      # 已取消


class VMTaskStatus(str, Enum):
    """虚拟机任务状态枚举"""
    PENDING = "pending"          # 等待中
    PREPARING = "preparing"      # 准备中（启动虚拟机）
    UPLOADING = "uploading"      # 上传样本中
    ANALYZING = "analyzing"      # 分析中
    COLLECTING = "collecting"    # 收集结果中
    RESTORING = "restoring"      # 恢复快照中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"           # 失败


class EDRAlert(BaseModel):
    """EDR告警信息"""

    severity: str
    alert_type: str

    process_name: Optional[str] = None
    command_line: Optional[str] = None

    # EDR 特定字段
    detect_reason: Optional[str] = None  # 检测方式/原因
    detection_time: Optional[str] = None
    file_path: Optional[str] = None
    file_paths: Optional[List[str]] = Field(default_factory=list)  # 文件路径数组
    network_connections: Optional[List[dict]] = Field(default_factory=list)  # 网络连接数组
    source: Optional[str] = None

    @model_serializer
    def serialize_model(self):
        """自定义序列化，将detection_time转换为本地时间格式"""
        from app.utils.helpers import format_timestamp_to_local

        return {
            'severity': self.severity,
            'alert_type': self.alert_type,
            'process_name': self.process_name,
            'command_line': self.command_line,
            'detect_reason': self.detect_reason,
            'detection_time': format_timestamp_to_local(self.detection_time) if self.detection_time else None,
            'file_path': self.file_path,
            'file_paths': self.file_paths,
            'network_connections': self.network_connections,
            'source': self.source
        }


class SysmonEvent(BaseModel):
    """Sysmon事件数据结构 - 精简版，只保留有实际数据的字段"""

    # 基本事件信息
    event_id: str  # Sysmon事件ID (1, 3, 5, 7, 10, 11, 22, 23等)
    event_name: Optional[str] = None  # 事件名称 (Process Creation, Network Connection等)
    timestamp: Optional[str] = None  # 事件时间戳（本地时间）
    event_type: Optional[str] = None  # 事件类型

    # 进程相关信息（有实际数据的字段）
    process_id: Optional[str] = None  # 进程ID
    image: Optional[str] = None  # 进程完整路径
    user: Optional[str] = None  # 用户

    # 文件相关信息（File Create事件使用）
    target_filename: Optional[str] = None  # 目标文件名

    # 进程访问相关信息（Process Access事件使用）
    source_process_id: Optional[str] = None  # 源进程ID
    target_process_id: Optional[str] = None  # 目标进程ID
    granted_access: Optional[str] = None  # 授予的访问权限
    source_image: Optional[str] = None  # 源进程镜像路径
    target_image: Optional[str] = None  # 目标进程镜像路径
    call_trace: Optional[str] = None  # 调用跟踪
    source_user: Optional[str] = None  # 源用户
    target_user: Optional[str] = None  # 目标用户


class BehaviorStatistics(BaseModel):
    """行为分析统计信息"""

    # 事件统计
    total_events: int = 0  # 总事件数
    event_types: Dict[str, int] = Field(default_factory=dict)  # 事件类型统计 {"1": 5, "3": 2}

    # 进程统计
    process_creations: int = 0  # 进程创建数量
    unique_processes: int = 0  # 唯一进程数量

    # 文件统计
    file_creations: int = 0  # 文件创建数量
    file_deletions: int = 0  # 文件删除数量
    file_modifications: int = 0  # 文件修改数量

    # 网络统计
    network_connections: int = 0  # 网络连接数量
    dns_queries: int = 0  # DNS查询数量
    unique_destinations: int = 0  # 唯一目标地址数量

    # 注册表统计
    registry_operations: int = 0  # 注册表操作数量

    # 其他统计
    process_accesses: int = 0  # 进程访问数量
    image_loads: int = 0  # 镜像加载数量

    # 时间范围
    first_event_time: Optional[str] = None  # 第一个事件时间
    last_event_time: Optional[str] = None  # 最后一个事件时间
    analysis_duration: Optional[float] = None  # 分析持续时间（秒）


class VMTaskResult(BaseModel):
    """虚拟机任务结果"""
    vm_name: str
    status: VMTaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    alerts: List[EDRAlert] = Field(default_factory=list)

    @model_serializer
    def serialize_model(self):
        """自定义序列化，将datetime转换为本地时间格式"""
        return {
            'vm_name': self.vm_name,
            'status': self.status,
            'start_time': format_timestamp_to_local(self.start_time) if self.start_time else None,
            'end_time': format_timestamp_to_local(self.end_time) if self.end_time else None,
            'error_message': self.error_message,
            'alerts': self.alerts
        }


class BehaviorAnalysisResult(BaseModel):
    """行为分析结果"""
    analysis_engine: str = "sysmon"
    status: VMTaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None

    # 使用SysmonEvent结构，保留原始数据
    events: List[SysmonEvent] = Field(default_factory=list)  # 原始事件数据，不做分析

    # 统计信息
    statistics: BehaviorStatistics = Field(default_factory=BehaviorStatistics)  # 行为统计

    @model_serializer
    def serialize_model(self):
        """自定义序列化，将datetime转换为本地时间格式"""
        return {
            'analysis_engine': self.analysis_engine,
            'status': self.status,
            'start_time': format_timestamp_to_local(self.start_time) if self.start_time else None,
            'end_time': format_timestamp_to_local(self.end_time) if self.end_time else None,
            'error_message': self.error_message,
            'events': self.events,
            'statistics': self.statistics
        }
    

class AnalysisTask(BaseModel):
    """分析任务模型"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str  # 文件名
    file_hash: str  # 文件哈希
    file_size: int  # 文件大小
    file_path: str  # 文件路径
    is_compressed: bool = False  # 保留字段以兼容现有代码
    vm_names: List[str]
    timeout: int = 300
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    edr_results: List[VMTaskResult] = Field(default_factory=list)
    behavior_results: Optional[BehaviorAnalysisResult] = None
    analysis_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_serializer
    def serialize_model(self):
        """自定义序列化，将datetime转换为本地时间格式"""
        return {
            'task_id': self.task_id,
            'file_name': self.file_name,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'file_path': self.file_path,
            'is_compressed': self.is_compressed,
            'vm_names': self.vm_names,
            'timeout': self.timeout,
            'status': self.status,
            'created_at': format_timestamp_to_local(self.created_at) if self.created_at else None,
            'started_at': format_timestamp_to_local(self.started_at) if self.started_at else None,
            'completed_at': format_timestamp_to_local(self.completed_at) if self.completed_at else None,
            'error_message': self.error_message,
            'edr_results': self.edr_results,
            'behavior_results': self.behavior_results,
            'analysis_metadata': self.analysis_metadata
        }

    class Config:
        json_encoders = {
            datetime: lambda v: format_timestamp_to_local(v)
        }


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    vm_names: Optional[List[str]] = None  # 如果为空，使用所有可用虚拟机
    timeout: int = Field(default=300, ge=60, le=1800)  # 60秒到30分钟
    

class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    status: TaskStatus
    message: str
    

class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    task_id: str
    file_name: str
    file_hash: str
    file_size: int
    vm_names: List[str]
    timeout: int
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    edr_results: List[VMTaskResult]
    behavior_results: Optional[BehaviorAnalysisResult] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: format_timestamp_to_local(v)
        }


class AnalysisResultResponse(BaseModel):
    """分析结果响应"""
    task_id: str
    status: TaskStatus
    total_alerts: int
    edr_results: List[VMTaskResult]
    behavior_results: Optional[BehaviorAnalysisResult] = None
    analysis_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: format_timestamp_to_local(v)
        }
