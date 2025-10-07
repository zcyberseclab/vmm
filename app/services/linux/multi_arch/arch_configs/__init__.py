"""
Architecture-specific configurations for multi-architecture support

This module contains configuration classes for different CPU architectures
supported by the VMM sandbox analysis system.
"""

from .x86_64_config import X86_64Config
from .aarch64_config import AArch64Config
from .mips_config import MIPSConfig
from .ppc64_config import PPC64Config

__all__ = [
    'X86_64Config',
    'AArch64Config', 
    'MIPSConfig',
    'PPC64Config'
]

# Architecture configuration registry
ARCH_CONFIGS = {
    'x86_64': X86_64Config,
    'aarch64': AArch64Config,
    'mips64': MIPSConfig,
    'mips': MIPSConfig,
    'ppc64': PPC64Config
}

def get_arch_config(architecture: str):
    """Get configuration class for specific architecture"""
    config_class = ARCH_CONFIGS.get(architecture)
    if config_class:
        return config_class()
    else:
        raise ValueError(f"Unsupported architecture: {architecture}")
