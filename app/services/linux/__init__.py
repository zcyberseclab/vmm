"""
Linux-specific services for VMM Sandbox Analysis System

This module provides Linux-specific implementations for:
- QEMU multi-architecture virtualization management
- Linux system monitoring (auditd, sysdig, falco)
- ELF file analysis
- Linux malware behavior analysis
"""

# 条件导入 - 避免Windows上的libvirt依赖问题
try:
    from .kvm_controller import KVMController
except ImportError:
    KVMController = None

try:
    from .auditd_manager import AuditdManager
except ImportError:
    AuditdManager = None

try:
    from .sysdig_monitor import SysdigMonitor
except ImportError:
    SysdigMonitor = None

try:
    from .elf_analyzer import ELFAnalyzer
except ImportError:
    ELFAnalyzer = None

# 导入多架构支持 (优先使用)
try:
    from .multi_arch.arch_manager import ArchManager
    from .multi_arch.qemu_controller import QEMUController
except ImportError:
    ArchManager = None
    QEMUController = None

__all__ = [
    'KVMController',
    'AuditdManager',
    'SysdigMonitor',
    'ELFAnalyzer',
    'ArchManager',
    'QEMUController'
]

__version__ = "1.0.0"
__author__ = "zcyberseclab"
__description__ = "Linux services for malware sandbox analysis"
