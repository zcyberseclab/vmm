"""
配置管理模块
"""
import os
import yaml
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str
    upload_dir: str = "./uploads"
    max_file_size: int = 104857600  # 100MB


class VirtualizationConfig(BaseModel):
    """虚拟化平台配置"""
    controller_type: str = "virtualbox"
    vboxmanage_path: str = "auto"
    vm_startup_mode: str = "headless"  # gui 或 headless


class VirtualMachineConfig(BaseModel):
    """虚拟机配置（传统方式，兼容性保留）"""
    name: str
    vm_name: str  # 虚拟机名称或路径
    snapshot_name: str
    ip_address: str
    edr_api_endpoint: str
    edr_username: str
    edr_password: str
    vm_path: Optional[str] = None  # 虚拟机文件路径（用于Workstation等）


class EDRVMConfig(BaseModel):
    """EDR分析虚拟机配置"""
    name: str
    antivirus: str
    username: str
    password: str
    baseline_snapshot: str = "disable-realtime"
    desktop_path: Optional[str] = None

    def __post_init__(self):
        if self.desktop_path is None:
            self.desktop_path = f"C:\\Users\\{self.username}\\Desktop"


class EDRTimeoutSettings(BaseModel):
    """EDR特定的超时配置"""
    # 基础操作超时
    file_read_timeout: int = 30          # 文件读取操作
    file_list_timeout: int = 30          # 文件列表获取
    simple_command_timeout: int = 60     # 简单命令执行

    # 复杂操作超时
    report_export_timeout: int = 120     # 报告导出操作
    log_analysis_timeout: int = 90       # 日志分析操作
    complex_operation_timeout: int = 180 # 复杂操作

    # 预检查超时
    availability_check_timeout: int = 15 # EDR软件可用性检查
    service_status_timeout: int = 10     # 服务状态检查


class AnalysisSettings(BaseModel):
    """分析配置"""
    static_scan_timeout: int = 120
    dynamic_analysis_timeout: int = 180
    vm_startup_timeout: int = 60
    file_transfer_timeout: int = 30

    # EDR特定超时设置
    edr_timeouts: EDRTimeoutSettings = EDRTimeoutSettings()


class SampleSettings(BaseModel):
    """样本文件配置"""
    static_suffix: str = "_static"
    dynamic_suffix: str = "_dynamic"
    max_sample_size: int = 52428800  # 50MB
    allowed_extensions: List[str] = [".exe", ".dll", ".bat", ".ps1", ".vbs", ".jar", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".bin"]


class EDRAnalysisConfig(BaseModel):
    """EDR分析配置"""
    vms: List[EDRVMConfig]
    analysis_settings: AnalysisSettings
    sample_settings: SampleSettings


class TaskConfig(BaseModel):
    """任务配置"""
    default_analysis_timeout: int = 300
    max_analysis_timeout: int = 1800
    cleanup_after_analysis: bool = True
    concurrent_tasks: int = 2
    max_queue_size: int = 100


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str = "./logs/vmm_edr.log"
    max_size: str = "10MB"
    backup_count: int = 5


class SysmonVMConfig(BaseModel):
    """Sysmon虚拟机配置"""
    name: str
    antivirus: str
    username: str
    password: str
    baseline_snapshot: str
    desktop_path: str


class SysmonEventCollectionConfig(BaseModel):
    """Sysmon事件收集配置"""
    max_events: int = 1000
    collection_timeout: int = 30
    event_types: List[int] = [1, 3, 5, 7, 8, 10, 11, 12, 13, 22]


class SysmonAnalysisSettingsConfig(BaseModel):
    """Sysmon分析设置配置"""
    pre_execution_delay: int = 5
    post_execution_delay: int = 60
    enable_process_tree: bool = True
    enable_network_analysis: bool = True
    enable_file_analysis: bool = True
    enable_registry_analysis: bool = True


class SysmonOutputSettingsConfig(BaseModel):
    """Sysmon输出设置配置"""
    save_raw_events: bool = True
    save_analysis_report: bool = True
    output_format: str = "json"


class SysmonAnalysisConfig(BaseModel):
    """Sysmon分析配置"""
    enabled: bool = True
    vm: SysmonVMConfig
    config_type: str = "light"
    custom_config_path: str = ""
    event_collection: SysmonEventCollectionConfig
    analysis_settings: SysmonAnalysisSettingsConfig
    output_settings: SysmonOutputSettingsConfig


class WindowsConfig(BaseModel):
    """Windows分析配置"""
    edr_analysis: Optional[EDRAnalysisConfig] = None
    sysmon_analysis: Optional[SysmonAnalysisConfig] = None


class Settings(BaseModel):
    """应用配置"""
    server: ServerConfig
    virtualization: VirtualizationConfig
    virtual_machines: Optional[List[VirtualMachineConfig]] = []  # 兼容性保留
    windows: Optional[WindowsConfig] = None
    task_settings: TaskConfig
    logging: LoggingConfig

    @classmethod
    def load_from_yaml(cls, config_path: str = "config.yaml") -> "Settings":
        """从YAML文件加载配置"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        return cls(**config_data)


# 全局配置实例
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例"""
    global settings
    if settings is None:
        settings = Settings.load_from_yaml()
    return settings
