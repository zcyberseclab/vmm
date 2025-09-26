"""
任务数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
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
    alert_id: str
    timestamp: datetime
    severity: str
    alert_type: str
    description: str
    file_hash: Optional[str] = None
    process_name: Optional[str] = None
    command_line: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    additional_data: Dict[str, Any] = Field(default_factory=dict)


class VMTaskResult(BaseModel):
    """虚拟机任务结果"""
    vm_name: str
    status: VMTaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    alerts: List[EDRAlert] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    vm_results: List[VMTaskResult] = Field(default_factory=list)
    
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
    vm_results: List[VMTaskResult]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnalysisResultResponse(BaseModel):
    """分析结果响应"""
    task_id: str
    status: TaskStatus
    total_alerts: int
    vm_results: List[VMTaskResult]
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
