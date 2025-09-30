"""
Sysmon Manager for EDR Analysis VMs
This module provides functionality to install, configure, and manage Sysmon on virtual machines.
This is a standalone module that doesn't depend on external app modules.
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

# Simple logging setup for standalone operation
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleVMController:
    """Simple VM controller for standalone operation"""

    def __init__(self):
        self.vboxmanage_path = self._find_vboxmanage()

    def _find_vboxmanage(self) -> str:
        """Find VBoxManage executable"""
        possible_paths = [
            r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
            "/usr/bin/VBoxManage",
            "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        raise FileNotFoundError("VBoxManage not found. Please ensure VirtualBox is installed.")

    async def execute_command_in_vm(self, vm_name: str, command: str, username: str = "vboxuser",
                                  password: str = "123456", timeout: int = 120) -> Tuple[bool, str]:
        """Execute command in VM using VBoxManage guestcontrol"""
        try:
            logger.info(f"Executing command in VM {vm_name}: {command}")

            # Use powershell.exe directly instead of going through cmd.exe
            vbox_cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "run", "--exe", "powershell.exe",
                "--wait-stdout", "--wait-stderr",
                "--",
                "-Command", command
            ]

            result = subprocess.run(vbox_cmd, capture_output=True, text=True, timeout=timeout)
            logger.info(f"Command completed with return code: {result.returncode}")

            if result.returncode == 0:
                logger.info("Command executed successfully")
                return True, result.stdout
            else:
                logger.error(f"Command execution failed: {result.stderr}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            logger.error("Command execution timeout")
            return False, "Command execution timeout"
        except Exception as e:
            logger.error(f"Failed to execute command in VM: {str(e)}")
            return False, str(e)

    async def copy_file_to_vm(self, vm_name: str, local_path: str, remote_path: str,
                            username: str = "vboxuser", password: str = "123456") -> bool:
        """Copy file to VM using VBoxManage guestcontrol"""
        try:
            logger.info(f"Copying file to VM: {local_path} -> {remote_path}")

            # Ensure local path is absolute
            local_path_abs = os.path.abspath(local_path)

            if not os.path.exists(local_path_abs):
                logger.error(f"Local file not found: {local_path_abs}")
                return False

            # Create target directory first
            target_dir = os.path.dirname(remote_path).replace('\\', '/')
            mkdir_cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "mkdir", target_dir, "--parents"
            ]

            subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)

            # Copy file
            copy_cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "copyto", local_path_abs, remote_path
            ]

            result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                logger.info(f"File copied successfully: {remote_path}")
                return True
            else:
                logger.error(f"File copy failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("File copy timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to copy file to VM: {str(e)}")
            return False


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
    
    def __init__(self, vm_controller=None):
        self.vm_controller = vm_controller or SimpleVMController()
        self.sysmon_url = "https://download.sysinternals.com/files/Sysmon.zip"
        self.tools_dir = Path(__file__).parent
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
            vm_sysmon_path = "C:\\Tools\\Sysmon"
            success = await self._copy_sysmon_to_vm(vm_name, sysmon_path, vm_sysmon_path, username, password)
            if not success:
                return False, "Failed to copy Sysmon to VM"
            
            # Copy configuration to VM
            vm_config_path = "C:\\sysmon-config.xml"
            success = await self.vm_controller.copy_file_to_vm(
                vm_name, str(config_path), vm_config_path, username, password
            )
            if not success:
                return False, "Failed to copy configuration to VM"
            
            # Install Sysmon
            success = await self._install_sysmon_on_vm(vm_name, vm_sysmon_path, vm_config_path, username, password)
            if not success:
                return False, "Failed to install Sysmon on VM"
            
            # Verify installation
            await asyncio.sleep(5)  # Wait for service to start
            status, message = await self.get_sysmon_status(vm_name, username, password)
            if status == SysmonStatus.RUNNING:
                logger.info(f"Sysmon successfully installed and running on {vm_name}")
                return True, "Sysmon installed and running successfully"
            else:
                logger.warning(f"Sysmon installed but not running on {vm_name}: {message}")
                return True, f"Sysmon installed but status is: {status}"
                
        except Exception as e:
            logger.error(f"Failed to install Sysmon on {vm_name}: {str(e)}")
            return False, f"Installation failed: {str(e)}"
    
    async def uninstall_sysmon(
        self, 
        vm_name: str, 
        username: str = "vboxuser", 
        password: str = "123456"
    ) -> Tuple[bool, str]:
        """
        Uninstall Sysmon from the specified VM
        
        Args:
            vm_name: Name of the virtual machine
            username: VM username
            password: VM password
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Uninstalling Sysmon from VM: {vm_name}")
            
            # Check if Sysmon is installed
            status, _ = await self.get_sysmon_status(vm_name, username, password)
            if status == SysmonStatus.NOT_INSTALLED:
                return True, "Sysmon is not installed"
            
            # Uninstall Sysmon - try common locations
            uninstall_cmd = 'if exist "C:\\Windows\\Sysmon64.exe" (C:\\Windows\\Sysmon64.exe -u -accepteula) else if exist "C:\\Windows\\Sysmon.exe" (C:\\Windows\\Sysmon.exe -u -accepteula) else echo Sysmon not found'
            
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, uninstall_cmd, username, password, timeout=60
            )
            
            if success:
                # Verify uninstallation
                await asyncio.sleep(3)
                status, _ = await self.get_sysmon_status(vm_name, username, password)
                if status == SysmonStatus.NOT_INSTALLED:
                    logger.info(f"Sysmon successfully uninstalled from {vm_name}")
                    return True, "Sysmon uninstalled successfully"
                else:
                    return False, "Uninstallation may have failed - Sysmon still detected"
            else:
                return False, f"Uninstallation command failed: {output}"
                
        except Exception as e:
            logger.error(f"Failed to uninstall Sysmon from {vm_name}: {str(e)}")
            return False, f"Uninstallation failed: {str(e)}"
    
    async def update_sysmon_config(
        self, 
        vm_name: str, 
        config_type: SysmonConfigType = SysmonConfigType.LIGHT,
        custom_config_path: Optional[str] = None,
        username: str = "vboxuser", 
        password: str = "123456"
    ) -> Tuple[bool, str]:
        """
        Update Sysmon configuration on the specified VM
        
        Args:
            vm_name: Name of the virtual machine
            config_type: Type of Sysmon configuration to use
            custom_config_path: Path to custom configuration file (if config_type is CUSTOM)
            username: VM username
            password: VM password
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Updating Sysmon configuration on VM: {vm_name}")
            
            # Check if Sysmon is installed
            status, _ = await self.get_sysmon_status(vm_name, username, password)
            if status == SysmonStatus.NOT_INSTALLED:
                return False, "Sysmon is not installed"
            
            # Get configuration file
            config_path = await self._get_config_file(config_type, custom_config_path)
            if not config_path:
                return False, "Configuration file not found"
            
            # Copy new configuration to VM
            vm_config_path = "C:\\sysmon-config-new.xml"
            success = await self.vm_controller.copy_file_to_vm(
                vm_name, str(config_path), vm_config_path, username, password
            )
            if not success:
                return False, "Failed to copy new configuration to VM"
            
            # Update Sysmon configuration
            update_cmd = f'$sysmon = Get-ChildItem C:\\Windows\\Sysmon*.exe -ErrorAction SilentlyContinue | Select-Object -First 1; if ($sysmon) {{ & $sysmon.FullName -c "{vm_config_path}" }} else {{ Write-Host "Sysmon executable not found" }}'
            
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, update_cmd, username, password, timeout=60
            )
            
            if success:
                logger.info(f"Sysmon configuration updated on {vm_name}")
                return True, "Configuration updated successfully"
            else:
                return False, f"Configuration update failed: {output}"
                
        except Exception as e:
            logger.error(f"Failed to update Sysmon configuration on {vm_name}: {str(e)}")
            return False, f"Configuration update failed: {str(e)}"
    
    async def get_sysmon_status(
        self, 
        vm_name: str, 
        username: str = "vboxuser", 
        password: str = "123456"
    ) -> Tuple[SysmonStatus, str]:
        """
        Get Sysmon status on the specified VM
        
        Args:
            vm_name: Name of the virtual machine
            username: VM username
            password: VM password
            
        Returns:
            Tuple of (status, details)
        """
        try:
            # Check if Sysmon service exists and its status
            status_cmd = 'Get-Service -Name "Sysmon*" -ErrorAction SilentlyContinue | Select-Object Name, Status | ConvertTo-Json'
            
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, status_cmd, username, password, timeout=30
            )
            
            if not success:
                return SysmonStatus.ERROR, f"Failed to check status: {output}"
            
            if not output.strip() or output.strip() == "null":
                return SysmonStatus.NOT_INSTALLED, "Sysmon service not found"
            
            # Parse service status
            import json
            try:
                services = json.loads(output)
                if not isinstance(services, list):
                    services = [services]
                
                running_services = [s for s in services if s.get('Status') == 'Running']
                stopped_services = [s for s in services if s.get('Status') == 'Stopped']
                
                if running_services:
                    service_names = [s['Name'] for s in running_services]
                    return SysmonStatus.RUNNING, f"Running services: {', '.join(service_names)}"
                elif stopped_services:
                    service_names = [s['Name'] for s in stopped_services]
                    return SysmonStatus.STOPPED, f"Stopped services: {', '.join(service_names)}"
                else:
                    return SysmonStatus.INSTALLED, "Service exists but status unknown"
                    
            except json.JSONDecodeError:
                # Fallback: check if output contains service information
                if "Sysmon" in output and "Running" in output:
                    return SysmonStatus.RUNNING, "Service appears to be running"
                elif "Sysmon" in output:
                    return SysmonStatus.INSTALLED, "Service exists"
                else:
                    return SysmonStatus.NOT_INSTALLED, "No Sysmon service found"
                    
        except Exception as e:
            logger.error(f"Failed to get Sysmon status from {vm_name}: {str(e)}")
            return SysmonStatus.ERROR, f"Status check failed: {str(e)}"
    
    async def get_sysmon_events(
        self, 
        vm_name: str, 
        max_events: int = 100,
        username: str = "vboxuser", 
        password: str = "123456"
    ) -> Tuple[bool, List[Dict]]:
        """
        Get recent Sysmon events from the specified VM
        
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
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Sysmon events JSON from {vm_name}")
                return False, []
                
        except Exception as e:
            logger.error(f"Failed to get Sysmon events from {vm_name}: {str(e)}")
            return False, []

    async def _download_sysmon(self) -> Optional[str]:
        """
        Download Sysmon from Microsoft Sysinternals

        Returns:
            Path to extracted Sysmon directory or None if failed
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

            logger.info(f"Sysmon extracted to: {extract_path}")
            return extract_path

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

    async def _copy_sysmon_to_vm(
        self,
        vm_name: str,
        local_sysmon_path: str,
        vm_sysmon_path: str,
        username: str,
        password: str
    ) -> bool:
        """
        Copy Sysmon files to VM

        Args:
            vm_name: Name of the virtual machine
            local_sysmon_path: Local path to Sysmon directory
            vm_sysmon_path: VM path where Sysmon should be copied
            username: VM username
            password: VM password

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Copying Sysmon files to VM: {vm_name}")

            # Create directory on VM
            mkdir_cmd = f'New-Item -ItemType Directory -Path "{vm_sysmon_path}" -Force'
            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, mkdir_cmd, username, password, timeout=30
            )

            if not success:
                logger.error(f"Failed to create directory on VM: {output}")
                return False

            # Copy Sysmon executable files
            sysmon_files = []
            for file_name in os.listdir(local_sysmon_path):
                if file_name.lower().endswith(('.exe', '.sys')):
                    sysmon_files.append(file_name)

            if not sysmon_files:
                logger.error("No Sysmon executable files found")
                return False

            # Copy each file
            for file_name in sysmon_files:
                local_file = os.path.join(local_sysmon_path, file_name)
                vm_file = f"{vm_sysmon_path}\\{file_name}"

                success = await self.vm_controller.copy_file_to_vm(
                    vm_name, local_file, vm_file, username, password
                )

                if not success:
                    logger.error(f"Failed to copy {file_name} to VM")
                    return False

                logger.info(f"Copied {file_name} to VM")

            return True

        except Exception as e:
            logger.error(f"Failed to copy Sysmon to VM: {str(e)}")
            return False

    async def _install_sysmon_on_vm(
        self,
        vm_name: str,
        vm_sysmon_path: str,
        vm_config_path: str,
        username: str,
        password: str
    ) -> bool:
        """
        Install Sysmon on VM using the copied files

        Args:
            vm_name: Name of the virtual machine
            vm_sysmon_path: VM path where Sysmon files are located
            vm_config_path: VM path to configuration file
            username: VM username
            password: VM password

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Installing Sysmon on VM: {vm_name}")

            # Find Sysmon executable (prefer standard 64-bit version)
            find_exe_cmd = f'$files = Get-ChildItem "{vm_sysmon_path}" -Name "Sysmon*.exe"; if ($files -contains "Sysmon64.exe") {{ "Sysmon64.exe" }} elseif ($files -contains "Sysmon.exe") {{ "Sysmon.exe" }} else {{ $files | Select-Object -First 1 }}'

            success, sysmon_exe = await self.vm_controller.execute_command_in_vm(
                vm_name, find_exe_cmd, username, password, timeout=30
            )

            if not success or not sysmon_exe.strip():
                logger.error("Failed to find Sysmon executable on VM")
                return False

            sysmon_exe = sysmon_exe.strip()
            sysmon_full_path = f"{vm_sysmon_path}\\{sysmon_exe}"

            logger.info(f"Using Sysmon executable: {sysmon_full_path}")

            # Install Sysmon with configuration
            install_cmd = f'& "{sysmon_full_path}" -accepteula -i "{vm_config_path}"'

            success, output = await self.vm_controller.execute_command_in_vm(
                vm_name, install_cmd, username, password, timeout=120
            )

            if success:
                logger.info(f"Sysmon installation command completed on {vm_name}")
                return True
            else:
                logger.error(f"Sysmon installation failed on {vm_name}: {output}")
                return False

        except Exception as e:
            logger.error(f"Failed to install Sysmon on VM: {str(e)}")
            return False
