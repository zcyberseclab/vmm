"""
EDR Package

This package provides EDR (Endpoint Detection and Response) client implementations
for various antivirus and security solutions. It includes:

- Base abstract class for all EDR clients
- Windows Defender EDR client implementation
- EDR manager for coordinating multiple EDR clients
- Factory functions for creating EDR instances

Usage:
    from app.services.edr import EDRManager, create_edr_manager
    
    # Create EDR manager with VM configurations
    edr_manager = create_edr_manager(vm_controller, vm_configs)
    
    # Collect alerts from a specific VM
    alerts = await edr_manager.collect_alerts_from_vm(vm_name, start_time)
"""

from .base import EDRClient
from .windows_defender import WindowsDefenderEDRClient
from .windows_kaspersky import KasperskyEDRClient
from .windows_mcafee import McafeeEDRClient
from .windows_avira import AviraEDRClient
from .windows_trend import TrendMicroEDRClient


from .manager import EDRManager, create_edr_manager

__all__ = [
    'EDRClient',
    'WindowsDefenderEDRClient',
    'KasperskyEDRClient',
    'McafeeEDRClient',
    'AviraEDRClient',
    'TrendMicroEDRClient',
    'EDRManager',
    'create_edr_manager'
]

# Version information
__version__ = '1.0.0'
__author__ = 'VMM EDR Team'
__description__ = 'EDR client implementations for virtual machine malware analysis'
