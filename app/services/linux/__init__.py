"""
Linux-specific services for VMM Sandbox Analysis System

This module provides Linux-specific implementations for:
- KVM/QEMU virtualization management
- Linux system monitoring (auditd, sysdig, falco)
- ELF file analysis
- Linux malware behavior analysis
"""

from .kvm_controller import KVMController
from .auditd_manager import AuditdManager
from .sysdig_monitor import SysdigMonitor
from .elf_analyzer import ELFAnalyzer

__all__ = [
    'KVMController',
    'AuditdManager', 
    'SysdigMonitor',
    'ELFAnalyzer'
]

__version__ = "1.0.0"
__author__ = "zcyberseclab"
__description__ = "Linux services for malware sandbox analysis"
