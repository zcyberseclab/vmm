"""
Sysmon Manager for EDR Analysis VMs
This module provides functionality to install, configure, and manage Sysmon on virtual machines.
"""

import asyncio
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import requests
from enum import Enum
from loguru import logger


class SysmonConfigType(str, Enum):
    """Sysmon configuration types"""
    LIGHT = "light"
    FULL = "full"
    CUSTOM = "custom"


class SysmonStatus(str, Enum):
    """Sysmon installation status"""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class SysmonManager:
    """Manages Sysmon installation and configuration on VMs"""
    
    def __init__(self, vm_controller):
        self.vm_controller = vm_controller
        self.sysmon_url = "https://download.sysinternals.com/files/Sysmon.zip"
        # Update paths to point to the tools directory
        self.tools_dir = Path(__file__).parent.parent.parent.parent.parent / "tools" / "sysmon"
        self.configs_dir = self.tools_dir / "configs"
        self.scripts_dir = self.tools_dir / "scripts"

        # Configuration file mappings
        self.config_files = {
            SysmonConfigType.LIGHT: self.configs_dir / "sysmon-config-light.xml",
            SysmonConfigType.FULL: self.configs_dir / "sysmon-config.xml"
        }
    
    async def install_sysmon(
        self, 
        vm_name: str, 
        username: str = "vboxuser", 
        password: str = "123456",
        config_type: SysmonConfigType = SysmonConfigType.LIGHT,
        custom_config_path: Optional[str] = None,
        force_reinstall: bool = False
    ) -> Tuple[bool, str]:
        """
        Install Sysmon on the specified VM
        
        Args:
            vm_name: Name of the virtual machine
            username: VM username
            password: VM password
            config_type: Type of Sysmon configuration to use
            custom_config_path: Path to custom configuration file (if config_type is CUSTOM)
            force_reinstall: Force reinstallation even if already installed
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Starting Sysmon installation on VM: {vm_name}")

            # Check if Sysmon is already installed
            if not force_reinstall:
                status, _ = await self.get_sysmon_status(vm_name, username, password)
                if status in [SysmonStatus.INSTALLED, SysmonStatus.RUNNING]:
                    logger.info(f"Sysmon already installed on {vm_name}")
                    return True, "Sysmon is already installed"
            
            # Download and prepare Sysmon
            sysmon_path = await self._download_sysmon()
            if not sysmon_path:
                return False, "Failed to download Sysmon"
            
            # Get configuration file
            config_path = await self._get_config_file(config_type, custom_config_path)
            if not config_path:
                return False, "Configuration file not found"
            
            # Copy Sysmon to VM
            vm_sysmon_path = "C:\\Windows\\Temp\\Sysmon64.exe"
            success = await self.vm_controller.copy_file_to_vm(
                vm_name, sysmon_path, vm_sysmon_path, username, password
            )
            if not success:
                return False, "Failed to copy Sysmon to VM"
            
            # Copy configuration to VM
            vm_config_path = "C:\\Windows\\Temp\\sysmon-config.xml"
            success = await self.vm_controller.copy_file_to_vm(
                vm_name, str(config_path), vm_config_path, username, password
            )
            if not success:
                return False, "Failed to copy Sysmon configuration to VM"
            
            # Uninstall existing Sysmon if force reinstall
            if force_reinstall:
                logger.info("Force reinstall requested, uninstalling existing Sysmon")
                await self._uninstall_sysmon(vm_name, username, password)
            
            # Install Sysmon with configuration
            install_cmd = f'& "{vm_sysmon_path}" -accepteula -i "{vm_config_path}"'
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, install_cmd, username, password, timeout=120
            )
            
            if success:
                logger.info(f"Sysmon installed successfully on {vm_name}")
                
                # Verify installation
                await asyncio.sleep(5)
                status, details = await self.get_sysmon_status(vm_name, username, password)
                if status in [SysmonStatus.INSTALLED, SysmonStatus.RUNNING]:
                    return True, f"Sysmon installed and running (Status: {status})"
                else:
                    return False, f"Sysmon installation verification failed (Status: {status})"
            else:
                logger.error(f"Sysmon installation failed: {output}")
                return False, f"Installation failed: {output}"
                
        except Exception as e:
            logger.error(f"Error installing Sysmon: {str(e)}")
            return False, f"Installation error: {str(e)}"
    
    async def get_sysmon_status(
        self,
        vm_name: str,
        username: str = "vboxuser",
        password: str = "123456"
    ) -> Tuple[SysmonStatus, str]:
        """
        Get Sysmon installation and running status

        Returns:
            Tuple of (status, details)
        """
        try:
            # Check for multiple possible Sysmon service names
            service_names = ["Sysmon64", "Sysmon", "SysmonDrv"]

            for service_name in service_names:
                service_cmd = f'Get-Service -Name "{service_name}" -ErrorAction SilentlyContinue | Select-Object Name, Status | ConvertTo-Json'
                success, output = await self.vm_controller.execute_command_in_vm(
                    vm_name, service_cmd, username, password, timeout=30
                )

                if success and output.strip() and output.strip() != "null":
                    # Parse service status
                    import json
                    try:
                        service_info = json.loads(output)
                        service_status = service_info.get("Status", "").lower()
                        service_found_name = service_info.get("Name", service_name)

                        if service_status == "running":
                            return SysmonStatus.RUNNING, f"Sysmon service '{service_found_name}' is running"
                        elif service_status == "stopped":
                            return SysmonStatus.STOPPED, f"Sysmon service '{service_found_name}' is stopped"
                        else:
                            return SysmonStatus.INSTALLED, f"Sysmon service '{service_found_name}' status: {service_status}"

                    except json.JSONDecodeError:
                        # If JSON parsing fails, try alternative method
                        if "running" in output.lower():
                            return SysmonStatus.RUNNING, f"Sysmon service '{service_name}' is running"
                        elif "stopped" in output.lower():
                            return SysmonStatus.STOPPED, f"Sysmon service '{service_name}' is stopped"
                        else:
                            return SysmonStatus.INSTALLED, f"Sysmon service '{service_name}' exists but status unclear"

            # If no service found, check if Sysmon executable exists
            logger.info("No Sysmon service found, checking for Sysmon executable...")
            exe_check_cmd = 'Get-ChildItem -Path "C:\\Windows\\Sysmon*.exe" -ErrorAction SilentlyContinue | Select-Object Name'
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, exe_check_cmd, username, password, timeout=30
            )

            if success and output.strip() and "sysmon" in output.lower():
                logger.info("Sysmon executable found but service not running")
                return SysmonStatus.INSTALLED, "Sysmon executable found but service not running"

            return SysmonStatus.NOT_INSTALLED, "Sysmon service and executable not found"

        except Exception as e:
            logger.error(f"Error checking Sysmon status: {str(e)}")
            # Instead of returning ERROR, try to be more graceful
            # Check if we can at least detect Sysmon executable
            try:
                logger.info("Attempting fallback Sysmon detection...")
                exe_check_cmd = 'Get-ChildItem -Path "C:\\Windows\\Sysmon*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1'
                success, output = await self.vm_controller.execute_command_in_vm(
                    vm_name, exe_check_cmd, username, password, timeout=15
                )
                if success and output.strip() and "sysmon" in output.lower():
                    logger.info("Sysmon executable found via fallback detection")
                    return SysmonStatus.INSTALLED, f"Sysmon executable detected (service status unknown: {str(e)})"

                # Try alternative path
                alt_check_cmd = 'Test-Path "C:\\Windows\\System32\\drivers\\SysmonDrv.sys"'
                success, output = await self.vm_controller.execute_command_in_vm(
                    vm_name, alt_check_cmd, username, password, timeout=15
                )
                if success and "true" in output.lower():
                    logger.info("Sysmon driver found via fallback detection")
                    return SysmonStatus.INSTALLED, f"Sysmon driver detected (service status unknown: {str(e)})"

            except Exception as fallback_error:
                logger.warning(f"Fallback detection also failed: {str(fallback_error)}")

            # As a last resort, assume NOT_INSTALLED only if we're really sure
            logger.warning(f"Could not determine Sysmon status due to error: {str(e)}")
            return SysmonStatus.NOT_INSTALLED, f"Status check failed: {str(e)}"
    
    async def get_sysmon_events(
        self, 
        vm_name: str, 
        max_events: int = 1000,
        username: str = "vboxuser", 
        password: str = "123456"
    ) -> Tuple[bool, List[Dict]]:
        """
        Retrieve Sysmon events from the VM
        
        Args:
            vm_name: Name of the virtual machine
            max_events: Maximum number of events to retrieve
            username: VM username
            password: VM password
            
        Returns:
            Tuple of (success, events_list)
        """
        try:
            logger.info(f"Retrieving Sysmon events from VM: {vm_name}")
            
            # Get Sysmon events from Windows Event Log
            events_cmd = f'Get-WinEvent -LogName "Microsoft-Windows-Sysmon/Operational" -MaxEvents {max_events} -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, LevelDisplayName, Message | ConvertTo-Json'
            
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, events_cmd, username, password, timeout=120
            )
            
            if not success:
                return False, []
            
            if not output.strip() or output.strip() == "null":
                return True, []  # No events found
            
            # Parse events
            import json
            try:
                events = json.loads(output)
                if not isinstance(events, list):
                    events = [events]
                
                return True, events
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Sysmon events JSON: {str(e)}")
                return False, []
                
        except Exception as e:
            logger.error(f"Error retrieving Sysmon events: {str(e)}")
            return False, []

    async def _uninstall_sysmon(
        self,
        vm_name: str,
        username: str = "vboxuser",
        password: str = "123456"
    ) -> bool:
        """Uninstall Sysmon from VM"""
        try:
            logger.info(f"Uninstalling Sysmon from VM: {vm_name}")

            # Try to uninstall using Sysmon64.exe first
            uninstall_cmd = 'Sysmon64.exe -u'
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, uninstall_cmd, username, password, timeout=60
            )

            if success:
                logger.info("Sysmon uninstalled successfully")
                return True
            else:
                # Try alternative uninstall method
                logger.warning("Standard uninstall failed, trying alternative method")
                alt_uninstall_cmd = 'sc.exe delete Sysmon64'
                success, output = await self.vm_controller.execute_command_in_vm(
                    vm_name, alt_uninstall_cmd, username, password, timeout=30
                )
                return success

        except Exception as e:
            logger.error(f"Error uninstalling Sysmon: {str(e)}")
            return False

    async def _download_sysmon(self) -> Optional[str]:
        """
        Download Sysmon from Microsoft Sysinternals

        Returns:
            Path to Sysmon64.exe or None if failed
        """
        try:
            logger.info("Downloading Sysmon from Microsoft Sysinternals")

            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="sysmon_")
            zip_path = os.path.join(temp_dir, "Sysmon.zip")
            extract_path = os.path.join(temp_dir, "sysmon")

            # Download Sysmon zip file
            response = requests.get(self.sysmon_url, timeout=300)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Sysmon downloaded to: {zip_path}")

            # Extract zip file
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            # Find Sysmon64.exe
            sysmon64_path = os.path.join(extract_path, "Sysmon64.exe")
            if os.path.exists(sysmon64_path):
                logger.info(f"Sysmon64.exe found at: {sysmon64_path}")
                return sysmon64_path
            else:
                # Fallback to Sysmon.exe
                sysmon_path = os.path.join(extract_path, "Sysmon.exe")
                if os.path.exists(sysmon_path):
                    logger.info(f"Sysmon.exe found at: {sysmon_path}")
                    return sysmon_path
                else:
                    logger.error("No Sysmon executable found in downloaded package")
                    return None

        except Exception as e:
            logger.error(f"Failed to download Sysmon: {str(e)}")
            return None

    async def _get_config_file(self, config_type: SysmonConfigType, custom_path: Optional[str] = None) -> Optional[Path]:
        """
        Get the appropriate configuration file path

        Args:
            config_type: Type of configuration
            custom_path: Custom configuration file path

        Returns:
            Path to configuration file or None if not found
        """
        try:
            if config_type == SysmonConfigType.CUSTOM:
                if custom_path and os.path.exists(custom_path):
                    return Path(custom_path)
                else:
                    logger.error("Custom configuration path not provided or doesn't exist")
                    return None

            config_path = self.config_files.get(config_type)
            if config_path and config_path.exists():
                return config_path
            else:
                logger.error(f"Configuration file not found for type: {config_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to get configuration file: {str(e)}")
            return None
