import os
import subprocess
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
from loguru import logger

from app.core.config import get_settings


class VMController(ABC):
 
    @abstractmethod
    async def power_on(self, vm_name: str) -> bool:
        pass
    
    @abstractmethod
    async def power_off(self, vm_name: str) -> bool:
        pass
    
    @abstractmethod
    async def revert_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        pass
    
    @abstractmethod
    async def get_status(self, vm_name: str) -> Dict[str, Any]:
        pass

 

class VBoxManageController(VMController):
    """VirtualBox controller"""

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

        raise FileNotFoundError("VBoxManage not found, please ensure VirtualBox is installed")
    
    async def _run_vboxmanage(self, *args) -> bool:
        """Execute VBoxManage command"""
        try:
            cmd = [self.vboxmanage_path] + list(args)
            logger.debug(f"Executing command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.debug(f"Command executed successfully: {result.stdout}")
                return True
            else:
                logger.error(f"Command execution failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"VBoxManage command exception: {str(e)}")
            return False
    
    async def power_on(self, vm_name: str) -> bool:
        """Start virtual machine with configured startup mode"""
        settings = get_settings()

        # Get startup mode from new configuration structure
        startup_mode = 'headless'  # Default
        if hasattr(settings, 'virtualization') and hasattr(settings.virtualization, 'virtualbox'):
            startup_mode = getattr(settings.virtualization.virtualbox, 'vm_startup_mode', 'headless')

        # Validate startup mode
        if startup_mode not in ['gui', 'headless']:
            logger.warning(f"Invalid startup mode: {startup_mode}, using default headless mode")
            startup_mode = 'headless'

        logger.info(f"Starting virtual machine {vm_name} (mode: {startup_mode})")
        return await self._run_vboxmanage("startvm", vm_name, "--type", startup_mode)

    async def power_off(self, vm_name: str) -> bool:
        """Power off virtual machine"""
        return await self._run_vboxmanage("controlvm", vm_name, "poweroff")

 
    async def unlock_vm_session(self, vm_name: str) -> bool:
        """Unlock virtual machine session"""
        logger.info(f"Attempting to unlock VM session: {vm_name}")

        try:
            # Try to unlock session
            result = await self._run_vboxmanage("startvm", vm_name, "--type", "emergencystop")
            if result:
                logger.info("Emergency stop successful")
                await asyncio.sleep(2)

            # Try normal shutdown again
            return await self.power_off(vm_name)

        except Exception as e:
            logger.error(f"Failed to unlock session: {str(e)}")
            return False

    async def cleanup_vm_resources(self, vm_name: str) -> bool:
        """Completely clean up virtual machine resources"""
        logger.info(f"Starting VM resource cleanup: {vm_name}")

        try:
            # 1. Get current status
            status_info = await self.get_status(vm_name)
            power_state = status_info.get("power_state", "unknown").lower()
            logger.info(f"Current VM state: {power_state}")

            # 2. If VM is running, try multiple shutdown methods
            if power_state in ['running', 'paused', 'stuck', 'starting']:
                logger.info("VM is running, attempting shutdown...")

                # Try 1: Normal shutdown
                if await self.power_off(vm_name):
                    logger.info("Normal shutdown successful")
                    await asyncio.sleep(3)
                else:
                    logger.warning("Normal shutdown failed, trying ACPI shutdown")
                    # Try 2: ACPI shutdown
                    if await self._run_vboxmanage("controlvm", vm_name, "acpipowerbutton"):
                        logger.info("ACPI shutdown successful")
                        await asyncio.sleep(5)  # ACPI shutdown needs more time
                    else:
                        logger.warning("ACPI shutdown failed, trying force shutdown")
                        # Try 3: Force shutdown
                        await self._run_vboxmanage("controlvm", vm_name, "poweroff")
                        await asyncio.sleep(2)

            # 3. Wait for VM to completely stop
            max_wait = 30  # Maximum wait 30 seconds
            wait_count = 0
            while wait_count < max_wait:
                status_info = await self.get_status(vm_name)
                power_state = status_info.get("power_state", "unknown").lower()

                if power_state in ['poweroff', 'aborted', 'saved']:
                    logger.info(f"VM stopped, state: {power_state}")
                    break

                logger.info(f"Waiting for VM to stop... Current state: {power_state} ({wait_count+1}/{max_wait})")
                await asyncio.sleep(1)
                wait_count += 1

            # 4. If still not stopped, log warning but continue
            if wait_count >= max_wait:
                logger.warning(f"VM did not fully stop within {max_wait} seconds, continuing cleanup process")

            # 5. Additional wait to ensure all processes exit completely
            await asyncio.sleep(2)

            logger.info(f"VM resource cleanup completed: {vm_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup VM resources: {str(e)}")
            return False
    
    async def revert_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """Restore snapshot"""
        return await self._run_vboxmanage("snapshot", vm_name, "restore", snapshot_name)
    
    async def get_status(self, vm_name: str) -> Dict[str, Any]:
        """Get virtual machine status"""
        try:
            cmd = [self.vboxmanage_path, "showvminfo", vm_name, "--machinereadable"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Parse output
                info = {}
                for line in result.stdout.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        info[key.strip()] = value.strip('"')

                return {
                    "power_state": info.get("VMState", "unknown"),
                    "vm_name": vm_name,
                    "guest_additions": info.get("GuestAdditionsVersion", "unknown")
                }
            else:
                return {"error": result.stderr}

        except Exception as e:
            logger.error(f"Failed to get VM status: {str(e)}")
            return {"error": str(e)}

    async def copy_file_to_vm(self, vm_name: str, local_path: str, remote_path: str, username: str = "admin", password: str = "password") -> bool:
        """Copy file to virtual machine - using VBoxManage guestcontrol"""
        try:
            # Ensure absolute path
            local_path_abs = os.path.abspath(local_path)

            if not os.path.exists(local_path_abs):
                logger.error(f"Local file does not exist: {local_path_abs}")
                return False

            # Check file size and permissions
            file_stat = os.stat(local_path_abs)
            logger.info(f"File info: {local_path_abs}, size: {file_stat.st_size} bytes")

            # Check VM status and Guest Additions
            logger.info("Checking VM status and Guest Additions...")
            status_info = await self.get_status(vm_name)
            logger.info(f"VM status: {status_info}")

            logger.info(f"Copying file to VM: {local_path_abs} -> {remote_path}")

            # First try to create target directory
            target_dir = os.path.dirname(remote_path).replace('\\', '/')
            mkdir_cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "mkdir", target_dir, "--parents"
            ]

            logger.info(f"Creating target directory: {' '.join(mkdir_cmd)}")
            mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=60)
            if mkdir_result.returncode != 0:
                logger.warning(f"Failed to create directory (may already exist): {mkdir_result.stderr}")

            cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "copyto", local_path_abs, remote_path
            ]

            logger.info(f"Executing file copy command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                logger.info(f"File copy successful: {remote_path}")
                return True
            else:
                logger.error(f"File copy failed: {result.stderr}")
                logger.error(f"Command output: {result.stdout}")

                # Try alternative method: using shared folder
                logger.info("Trying alternative file transfer method...")
                return await self._copy_file_via_shared_folder(vm_name, local_path_abs, remote_path, username, password)

        except subprocess.TimeoutExpired:
            logger.error("File copy timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to copy file to VM: {str(e)}")
            return False

    async def _copy_file_via_shared_folder(self, vm_name: str, local_path: str, remote_path: str, username: str, password: str) -> bool:
        """
        Alternative file transfer method: copy files by executing commands in VM
        """
        try:
            logger.info("Using alternative method: file transfer via PowerShell commands")

            # Read local file content and convert to Base64
            with open(local_path, 'rb') as f:
                file_content = f.read()

            import base64
            b64_content = base64.b64encode(file_content).decode('utf-8')

            # Transfer in chunks (PowerShell command line has length limits)
            chunk_size = 8000  # Conservative chunk size
            chunks = [b64_content[i:i+chunk_size] for i in range(0, len(b64_content), chunk_size)]

            logger.info(f"File will be transferred in {len(chunks)} chunks")

            # Clear target file
            clear_cmd = f'powershell -Command "if (Test-Path \'{remote_path}\') {{ Remove-Item \'{remote_path}\' -Force }}"'
            await self.execute_command_in_vm(vm_name, clear_cmd, username, password, timeout=30)

            # Write file chunk by chunk
            for i, chunk in enumerate(chunks):
                if i == 0:
                    # First chunk: create new file
                    ps_cmd = f'powershell -Command "[System.Convert]::FromBase64String(\'{chunk}\') | Set-Content -Path \'{remote_path}\' -Encoding Byte"'
                else:
                    # Subsequent chunks: append to file
                    ps_cmd = f'powershell -Command "[System.Convert]::FromBase64String(\'{chunk}\') | Add-Content -Path \'{remote_path}\' -Encoding Byte"'

                success, output = await self.execute_command_in_vm(vm_name, ps_cmd, username, password, timeout=60)
                if not success:
                    logger.error(f"Failed to transfer chunk {i+1}: {output}")
                    return False

                logger.info(f"Transferred {i+1}/{len(chunks)} chunks")

            # Verify file size
            verify_cmd = f'powershell -Command "(Get-Item \\"{remote_path}\\").Length"'
            success, size_output = await self.execute_command_in_vm(vm_name, verify_cmd, username, password, timeout=30)

            if success and size_output.strip().isdigit():
                remote_size = int(size_output.strip())
                local_size = len(file_content)
                if remote_size == local_size:
                    logger.info(f"Alternative file transfer successful, size verification passed: {remote_size} bytes")
                    return True
                else:
                    logger.error(f"File size mismatch: local {local_size} bytes, remote {remote_size} bytes")
                    return False
            else:
                logger.warning("Cannot verify remote file size, but transfer process completed without errors")
                return True

        except Exception as e:
            logger.error(f"Alternative file transfer method failed: {str(e)}")
            return False

    async def copy_file_from_vm(self, vm_name: str, remote_path: str, local_path: str, username: str = "admin", password: str = "password") -> bool:
        """Copy file from virtual machine - using VBoxManage guestcontrol"""
        try:
            logger.info(f"Copying file from VM: {remote_path} -> {local_path}")

            cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "copyfrom", remote_path, local_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info(f"File copy successful: {local_path}")
                return True
            else:
                logger.error(f"File copy failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("File copy timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to copy file from VM: {str(e)}")
            return False

    async def execute_command_in_vm(self, vm_name: str, command: str, username: str = "vboxuser", password: str = "123456", timeout: int = 120) -> tuple[bool, str]:
        """Execute command in virtual machine"""
        try:
            logger.info(f"Executing command in VM: {command}")

            vbox_cmd  = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "run", "--exe", "cmd.exe",
                "--",
                "/c",  # cmd.exe parameter, execute and close
                "powershell",
                "-Command",
                command
            ]

            logger.debug(f"{vbox_cmd}")
            result = subprocess.run(vbox_cmd, capture_output=True, text=True, timeout=timeout)
            logger.info(f"Command execution completed, return code: {result.returncode}")

            if result.returncode == 0:
                logger.info("Command execution successful")
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

    async def execute_program_in_vm(self, vm_name: str, program_path: str, arguments: list = None, username: str = "vboxuser", password: str = "123456", timeout: int = 120) -> tuple[bool, str]:
        """Execute program directly in virtual machine (not through cmd.exe)"""
        try:
            if arguments is None:
                arguments = []

            logger.info(f"Executing program directly in VM: {program_path} {' '.join(arguments)}")

            vbox_cmd = [
                self.vboxmanage_path,
                "guestcontrol", vm_name, "run",
                "--exe", program_path,
                "--username", username,
                "--password", password,
                "--wait-stdout", "--wait-stderr"
            ]

            # Add program arguments
            if arguments:
                vbox_cmd.extend(["--"] + arguments)

            result = subprocess.run(vbox_cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode == 0:
                logger.info("Program execution successful")
                return True, result.stdout
            else:
                logger.error(f"Program execution failed: {result.stderr}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            logger.error("Program execution timeout")
            return False, "Program execution timeout"
        except Exception as e:
            logger.error(f"Failed to execute program in VM: {str(e)}")
            return False, str(e)


 
def create_vm_controller(controller_type: str = None) -> VMController:
    if controller_type is None:
        # Default to VirtualBox for Windows analysis
        controller_type = 'virtualbox'

    if controller_type.lower() == "virtualbox":
        return VBoxManageController()
    else:
        raise ValueError(f"not support vm type: {controller_type}")
