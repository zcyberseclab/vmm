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

from .arch_manager import ArchManager
from .qemu_controller import QEMUController

__all__ = [
    'ArchManager',
    'QEMUController'
]

# Supported architectures
SUPPORTED_ARCHITECTURES = {
    'x86_64': {
        'name': 'x86_64',
        'description': 'Intel/AMD 64-bit',
        'qemu_binary': 'qemu-system-x86_64',
        'acceleration': 'kvm',
        'endianness': 'little'
    },
    'aarch64': {
        'name': 'aarch64', 
        'description': 'ARM 64-bit',
        'qemu_binary': 'qemu-system-aarch64',
        'acceleration': 'tcg',
        'endianness': 'little'
    },
    'mips64': {
        'name': 'mips64',
        'description': 'MIPS 64-bit',
        'qemu_binary': 'qemu-system-mips64',
        'acceleration': 'tcg', 
        'endianness': 'big'
    },
    'mips': {
        'name': 'mips',
        'description': 'MIPS 32-bit',
        'qemu_binary': 'qemu-system-mips',
        'acceleration': 'tcg',
        'endianness': 'big'
    },
    'ppc64': {
        'name': 'ppc64',
        'description': 'PowerPC 64-bit',
        'qemu_binary': 'qemu-system-ppc64',
        'acceleration': 'tcg',
        'endianness': 'big'
    }
}

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

 