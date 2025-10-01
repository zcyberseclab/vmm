"""
任务数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import uuid


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


class SysmonEvent(BaseModel):
    """Sysmon事件数据结构 - 简化扁平结构"""

    # 基本事件信息
    event_id: str  # Sysmon事件ID (1, 3, 5, 7, 10, 11, 22, 23等)
    event_name: Optional[str] = None  # 事件名称 (Process Creation, Network Connection等)
    timestamp: Optional[str] = None  # 事件时间戳
    computer_name: Optional[str] = None  # 计算机名

    # 进程相关信息
    process_id: Optional[str] = None  # 进程ID
    process_name: Optional[str] = None  # 进程名称
    image: Optional[str] = None  # 进程完整路径
    command_line: Optional[str] = None  # 命令行参数
    parent_process_id: Optional[str] = None  # 父进程ID
    parent_image: Optional[str] = None  # 父进程路径
    user: Optional[str] = None  # 用户

    # 文件相关信息
    target_filename: Optional[str] = None  # 目标文件名
    creation_utc_time: Optional[str] = None  # 文件创建时间

    # 网络相关信息
    source_ip: Optional[str] = None  # 源IP
    source_port: Optional[str] = None  # 源端口
    destination_ip: Optional[str] = None  # 目标IP
    destination_port: Optional[str] = None  # 目标端口
    protocol: Optional[str] = None  # 协议

    # DNS相关信息
    query_name: Optional[str] = None  # DNS查询名称
    query_results: Optional[str] = None  # DNS查询结果

    # 进程访问相关信息
    source_process_id: Optional[str] = None  # 源进程ID
    target_process_id: Optional[str] = None  # 目标进程ID
    granted_access: Optional[str] = None  # 授予的访问权限

    # 镜像加载相关信息
    image_loaded: Optional[str] = None  # 加载的镜像路径
    signature: Optional[str] = None  # 签名信息
    signed: Optional[str] = None  # 是否签名

    # 新增字段 - 从parsed_fields提取的关键信息
    event_type: Optional[str] = None  # 事件类型
    source_process_guid: Optional[str] = None  # 源进程GUID
    source_image: Optional[str] = None  # 源进程镜像路径
    target_process_guid: Optional[str] = None  # 目标进程GUID
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
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
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
            datetime: lambda v: v.isoformat()
        }


class AnalysisResultResponse(BaseModel):
    """分析结果响应"""
    task_id: str
    status: TaskStatus
    total_alerts: int
    edr_results: List[VMTaskResult]
    behavior_results: Optional[BehaviorAnalysisResult] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
