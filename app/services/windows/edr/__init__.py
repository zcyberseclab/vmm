"""
EDR (Endpoint Detection and Response) clients for Windows

This module provides EDR client implementations for various Windows antivirus solutions.
"""

from .manager import EDRManager
from .base import EDRClient
from .windows_defender import WindowsDefenderEDRClient
from .windows_kaspersky import KasperskyEDRClient
from .windows_mcafee import McafeeEDRClient
from .windows_avira import AviraEDRClient
from .windows_trend import TrendMicroEDRClient

__all__ = [
    'EDRManager',
    'EDRClient', 
    'WindowsDefenderEDRClient',
    'KasperskyEDRClient',
    'McafeeEDRClient',
    'AviraEDRClient',
    'TrendMicroEDRClient'
]
