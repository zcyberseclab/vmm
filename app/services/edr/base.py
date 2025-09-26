"""
Base EDR Client Abstract Class

This module defines the abstract base class for all EDR (Endpoint Detection and Response) clients.
It provides a common interface that all EDR implementations must follow.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from app.models.task import EDRAlert
from app.services.vm_controller import VMController


class EDRClient(ABC):
    """
    Abstract base class for EDR clients.
    
    This class defines the interface that all EDR client implementations must follow.
    Each EDR vendor (Windows Defender, Kaspersky, Symantec, etc.) should implement
    this interface to provide consistent functionality across different EDR systems.
    """

    def __init__(self, vm_name: str, vm_controller: VMController, username: str = "vboxuser", password: str = "123456"):
        """
        Initialize the EDR client.
        
        Args:
            vm_name: Name of the virtual machine
            vm_controller: VM controller instance for executing commands
            username: Username for VM authentication
            password: Password for VM authentication
        """
        self.vm_name = vm_name
        self.vm_controller = vm_controller
        self.username = username
        self.password = password

    @abstractmethod
    async def get_alerts(self, start_time: datetime, end_time: Optional[datetime] = None,
                        file_hash: Optional[str] = None, file_name: Optional[str] = None) -> List[EDRAlert]:
        """
        Retrieve alerts from the EDR system.
        
        This method must be implemented by all EDR client subclasses to provide
        vendor-specific alert retrieval functionality.
        
        Args:
            start_time: Start time for alert search
            end_time: End time for alert search (optional, defaults to current time)
            file_hash: Specific file hash to search for (optional)
            file_name: Specific file name to search for (optional)
            
        Returns:
            List of EDRAlert objects containing the retrieved alerts
            
        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        pass
