"""
Multi-Architecture Support for VMM Sandbox Analysis System

This module provides support for analyzing malware across multiple CPU architectures:
- x86/x64: Traditional PC and server malware
- ARM64: Mobile and IoT device malware  
- MIPS: Router and embedded device malware
- PowerPC: Server and embedded system malware

Key Components:
- ArchManager: Central architecture management
- QEMUController: Multi-architecture QEMU control
- Architecture-specific configurations and monitors
- Unified cross-architecture analysis interface
"""

# 条件导入 - Windows上可能缺少某些依赖
try:
    from .arch_manager import ArchManager
except ImportError as e:
    print(f"Warning: ArchManager import failed: {e}")
    ArchManager = None

try:
    from .qemu_controller import QEMUController
except ImportError as e:
    print(f"Warning: QEMUController import failed: {e}")
    QEMUController = None

__all__ = [
    'ArchManager',
    'QEMUController',
    'ELF_ARCH_MAPPING'
]

# ELF machine type to architecture mapping
ELF_ARCH_MAPPING = {
    0x3E: 'x86_64',    # EM_X86_64
    0x03: 'x86',       # EM_386
    0xB7: 'aarch64',   # EM_AARCH64
    0x28: 'arm',       # EM_ARM
    0x08: 'mips',      # EM_MIPS
    0x15: 'ppc64',     # EM_PPC64
    0x14: 'ppc'        # EM_PPC
}

 