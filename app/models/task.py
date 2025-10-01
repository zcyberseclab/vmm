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
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None

    # EDR 特定字段
    detect_reason: Optional[str] = None  # 检测方式/原因
    detection_time: Optional[str] = None
    event_id: Optional[str] = None
    file_path: Optional[str] = None
    file_paths: Optional[List[str]] = Field(default_factory=list)  # 文件路径数组
    network_connections: Optional[List[dict]] = Field(default_factory=list)  # 网络连接数组
    source: Optional[str] = None


class SysmonEvent(BaseModel):
    """Sysmon事件数据结构"""

    # 基本事件信息
    event_id: str  # Sysmon事件ID (1, 3, 5, 7, 10, 11, 22, 23等)
    event_name: str  # 事件名称 (Process Creation, Network Connection等)
    timestamp: str  # 事件时间戳
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

    # 原始事件数据
    raw_data: Optional[Dict[str, Any]] = Field(default_factory=dict)  # 原始事件数据


class SysmonAlert(BaseModel):
    """Sysmon告警数据结构"""

    # 基本告警信息
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: str  # 严重程度: low, medium, high, critical
    alert_type: str  # 告警类型
    detection_time: str  # 检测时间

    # 事件统计信息
    event_count: int = 0  # 相关事件数量
    event_ids: List[str] = Field(default_factory=list)  # 涉及的事件ID列表

    # 进程信息
    processes_involved: List[str] = Field(default_factory=list)  # 涉及的进程列表
    primary_process: Optional[str] = None  # 主要进程
    command_lines: List[str] = Field(default_factory=list)  # 命令行列表

    # 文件操作信息
    files_created: List[str] = Field(default_factory=list)  # 创建的文件列表
    files_deleted: List[str] = Field(default_factory=list)  # 删除的文件列表
    files_modified: List[str] = Field(default_factory=list)  # 修改的文件列表
    file_types: List[str] = Field(default_factory=list)  # 文件类型列表

    # 网络活动信息
    network_connections: List[Dict[str, str]] = Field(default_factory=list)  # 网络连接列表
    dns_queries: List[Dict[str, str]] = Field(default_factory=list)  # DNS查询列表
    remote_addresses: List[str] = Field(default_factory=list)  # 远程地址列表

    # 系统活动信息
    registry_operations: List[Dict[str, str]] = Field(default_factory=list)  # 注册表操作
    process_accesses: List[Dict[str, str]] = Field(default_factory=list)  # 进程访问
    image_loads: List[Dict[str, str]] = Field(default_factory=list)  # 镜像加载

    # 描述和原因
    description: str  # 告警描述
    detection_reason: str  # 检测原因

    # 相关事件
    related_events: List[SysmonEvent] = Field(default_factory=list)  # 相关的Sysmon事件

    # 元数据
    source: str = "sysmon"
    analysis_engine: str = "sysmon"


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
    alerts: List[SysmonAlert] = Field(default_factory=list)  # 使用SysmonAlert而不是EDRAlert
    events_collected: int = 0
    analysis_duration: Optional[float] = None
    raw_events: List[SysmonEvent] = Field(default_factory=list)  # 原始Sysmon事件
    

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
