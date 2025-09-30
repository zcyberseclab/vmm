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
    """VirtualBox控制器"""
    
    def __init__(self):
        self.vboxmanage_path = self._find_vboxmanage()
    
    def _find_vboxmanage(self) -> str:
        """查找VBoxManage可执行文件"""
        possible_paths = [
            r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
            "/usr/bin/VBoxManage",
            "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError("未找到VBoxManage，请确保安装了VirtualBox")
    
    async def _run_vboxmanage(self, *args) -> bool:
        """执行VBoxManage命令"""
        try:
            cmd = [self.vboxmanage_path] + list(args)
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.debug(f"命令执行成功: {result.stdout}")
                return True
            else:
                logger.error(f"命令执行失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"执行VBoxManage命令异常: {str(e)}")
            return False
    
    async def power_on(self, vm_name: str) -> bool:
        """启动虚拟机，使用配置的启动模式"""
        settings = get_settings()
        startup_mode = getattr(settings.virtualization, 'vm_startup_mode', 'headless')

        # 验证启动模式
        if startup_mode not in ['gui', 'headless']:
            logger.warning(f"无效的启动模式: {startup_mode}，使用默认的headless模式")
            startup_mode = 'headless'

        logger.info(f"启动虚拟机 {vm_name} (模式: {startup_mode})")
        return await self._run_vboxmanage("startvm", vm_name, "--type", startup_mode)
    
    async def power_off(self, vm_name: str) -> bool:
        """关闭虚拟机"""
        return await self._run_vboxmanage("controlvm", vm_name, "poweroff")

 
    async def unlock_vm_session(self, vm_name: str) -> bool:
        """解锁虚拟机会话"""
        logger.info(f"尝试解锁虚拟机会话: {vm_name}")

        try:
            # 尝试解锁会话
            result = await self._run_vboxmanage("startvm", vm_name, "--type", "emergencystop")
            if result:
                logger.info("紧急停止成功")
                await asyncio.sleep(2)

            # 再次尝试正常关闭
            return await self.power_off(vm_name)

        except Exception as e:
            logger.error(f"解锁会话失败: {str(e)}")
            return False

    async def cleanup_vm_resources(self, vm_name: str) -> bool:
        """完全清理虚拟机资源"""
        logger.info(f"开始清理虚拟机资源: {vm_name}")

        try:
            # 1. 获取当前状态
            status_info = await self.get_status(vm_name)
            power_state = status_info.get("power_state", "unknown").lower()
            logger.info(f"当前虚拟机状态: {power_state}")

            # 2. 如果虚拟机正在运行，尝试多种方式关闭
            if power_state in ['running', 'paused', 'stuck', 'starting']:
                logger.info("虚拟机正在运行，尝试关闭...")

                # 尝试1: 正常关闭
                if await self.power_off(vm_name):
                    logger.info("正常关闭成功")
                    await asyncio.sleep(3)
                else:
                    logger.warning("正常关闭失败，尝试ACPI关闭")
                    # 尝试2: ACPI关闭
                    if await self._run_vboxmanage("controlvm", vm_name, "acpipowerbutton"):
                        logger.info("ACPI关闭成功")
                        await asyncio.sleep(5)  # ACPI关闭需要更长时间
                    else:
                        logger.warning("ACPI关闭失败，尝试强制关闭")
                        # 尝试3: 强制关闭
                        await self._run_vboxmanage("controlvm", vm_name, "poweroff")
                        await asyncio.sleep(2)

            # 3. 等待虚拟机完全停止
            max_wait = 30  # 最多等待30秒
            wait_count = 0
            while wait_count < max_wait:
                status_info = await self.get_status(vm_name)
                power_state = status_info.get("power_state", "unknown").lower()

                if power_state in ['poweroff', 'aborted', 'saved']:
                    logger.info(f"虚拟机已停止，状态: {power_state}")
                    break

                logger.info(f"等待虚拟机停止... 当前状态: {power_state} ({wait_count+1}/{max_wait})")
                await asyncio.sleep(1)
                wait_count += 1

            # 4. 如果仍未停止，记录警告但继续
            if wait_count >= max_wait:
                logger.warning(f"虚拟机在{max_wait}秒内未完全停止，继续清理流程")

            # 5. 额外等待确保所有进程完全退出
            await asyncio.sleep(2)

            logger.info(f"虚拟机资源清理完成: {vm_name}")
            return True

        except Exception as e:
            logger.error(f"清理虚拟机资源失败: {str(e)}")
            return False
    
    async def revert_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """恢复快照"""
        return await self._run_vboxmanage("snapshot", vm_name, "restore", snapshot_name)
    
    async def get_status(self, vm_name: str) -> Dict[str, Any]:
        """获取虚拟机状态"""
        try:
            cmd = [self.vboxmanage_path, "showvminfo", vm_name, "--machinereadable"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 解析输出
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
            logger.error(f"获取虚拟机状态失败: {str(e)}")
            return {"error": str(e)}

    async def copy_file_to_vm(self, vm_name: str, local_path: str, remote_path: str, username: str = "admin", password: str = "password") -> bool:
        """复制文件到虚拟机 - 使用VBoxManage guestcontrol"""
        try:
            # 确保使用绝对路径
            local_path_abs = os.path.abspath(local_path)

            if not os.path.exists(local_path_abs):
                logger.error(f"本地文件不存在: {local_path_abs}")
                return False

            # 检查文件大小和权限
            file_stat = os.stat(local_path_abs)
            logger.info(f"文件信息: {local_path_abs}, 大小: {file_stat.st_size} bytes")

            # 检查虚拟机状态和Guest Additions
            logger.info("检查虚拟机状态和Guest Additions...")
            status_info = await self.get_status(vm_name)
            logger.info(f"虚拟机状态: {status_info}")

            logger.info(f"复制文件到虚拟机: {local_path_abs} -> {remote_path}")

            # 首先尝试创建目标目录
            target_dir = os.path.dirname(remote_path).replace('\\', '/')
            mkdir_cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "mkdir", target_dir, "--parents"
            ]

            logger.info(f"创建目标目录: {' '.join(mkdir_cmd)}")
            mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=60)
            if mkdir_result.returncode != 0:
                logger.warning(f"创建目录失败（可能已存在）: {mkdir_result.stderr}")

            cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "copyto", local_path_abs, remote_path
            ]

            logger.info(f"执行文件复制命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                logger.info(f"文件复制成功: {remote_path}")
                return True
            else:
                logger.error(f"文件复制失败: {result.stderr}")
                logger.error(f"命令输出: {result.stdout}")

                # 尝试备用方法：使用共享文件夹
                logger.info("尝试使用备用文件传输方法...")
                return await self._copy_file_via_shared_folder(vm_name, local_path_abs, remote_path, username, password)

        except subprocess.TimeoutExpired:
            logger.error("文件复制超时")
            return False
        except Exception as e:
            logger.error(f"复制文件到虚拟机失败: {str(e)}")
            return False

    async def _copy_file_via_shared_folder(self, vm_name: str, local_path: str, remote_path: str, username: str, password: str) -> bool:
        """
        备用文件传输方法：通过在虚拟机中执行命令来复制文件
        """
        try:
            logger.info("使用备用方法：通过PowerShell命令传输文件")

            # 读取本地文件内容并转换为Base64
            with open(local_path, 'rb') as f:
                file_content = f.read()

            import base64
            b64_content = base64.b64encode(file_content).decode('utf-8')

            # 分块传输（PowerShell命令行有长度限制）
            chunk_size = 8000  # 保守的块大小
            chunks = [b64_content[i:i+chunk_size] for i in range(0, len(b64_content), chunk_size)]

            logger.info(f"文件将分为 {len(chunks)} 个块进行传输")

            # 清空目标文件
            clear_cmd = f'powershell -Command "if (Test-Path \'{remote_path}\') {{ Remove-Item \'{remote_path}\' -Force }}"'
            await self.execute_command_in_vm(vm_name, clear_cmd, username, password, timeout=30)

            # 逐块写入文件
            for i, chunk in enumerate(chunks):
                if i == 0:
                    # 第一块：创建新文件
                    ps_cmd = f'powershell -Command "[System.Convert]::FromBase64String(\'{chunk}\') | Set-Content -Path \'{remote_path}\' -Encoding Byte"'
                else:
                    # 后续块：追加到文件
                    ps_cmd = f'powershell -Command "[System.Convert]::FromBase64String(\'{chunk}\') | Add-Content -Path \'{remote_path}\' -Encoding Byte"'

                success, output = await self.execute_command_in_vm(vm_name, ps_cmd, username, password, timeout=60)
                if not success:
                    logger.error(f"传输第 {i+1} 块失败: {output}")
                    return False

                logger.info(f"已传输 {i+1}/{len(chunks)} 块")

            # 验证文件大小
            verify_cmd = f'powershell -Command "(Get-Item \\"{remote_path}\\").Length"'
            success, size_output = await self.execute_command_in_vm(vm_name, verify_cmd, username, password, timeout=30)

            if success and size_output.strip().isdigit():
                remote_size = int(size_output.strip())
                local_size = len(file_content)
                if remote_size == local_size:
                    logger.info(f"备用方法文件传输成功，大小验证通过: {remote_size} bytes")
                    return True
                else:
                    logger.error(f"文件大小不匹配: 本地 {local_size} bytes, 远程 {remote_size} bytes")
                    return False
            else:
                logger.warning("无法验证远程文件大小，但传输过程未报错")
                return True

        except Exception as e:
            logger.error(f"备用文件传输方法失败: {str(e)}")
            return False

    async def copy_file_from_vm(self, vm_name: str, remote_path: str, local_path: str, username: str = "admin", password: str = "password") -> bool:
        """从虚拟机复制文件 - 使用VBoxManage guestcontrol"""
        try:
            logger.info(f"从虚拟机复制文件: {remote_path} -> {local_path}")

            cmd = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "copyfrom", remote_path, local_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info(f"文件复制成功: {local_path}")
                return True
            else:
                logger.error(f"文件复制失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("文件复制超时")
            return False
        except Exception as e:
            logger.error(f"从虚拟机复制文件失败: {str(e)}")
            return False

    async def execute_command_in_vm(self, vm_name: str, command: str, username: str = "vboxuser", password: str = "123456", timeout: int = 120) -> tuple[bool, str]:
        """在虚拟机中执行命令"""
        try:
            logger.info(f"在虚拟机中执行命令: {command}")

            vbox_cmd  = [
                self.vboxmanage_path, "guestcontrol", vm_name,
                "--username", username,
                "--password", password,
                "run", "--exe", "cmd.exe",
                "--", 
                "/c",  # cmd.exe 的参数，表示执行后关闭
                "powershell",
                "-Command",
                command
            ]

            logger.debug(f"{vbox_cmd}")
            result = subprocess.run(vbox_cmd, capture_output=True, text=True, timeout=timeout)
            logger.info(f"命令执行完成，返回码: {result.returncode}")

            if result.returncode == 0:
                logger.info("命令执行成功")
                return True, result.stdout
            else:
                logger.error(f"命令执行失败: {result.stderr}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            logger.error("命令执行超时")
            return False, "命令执行超时"
        except Exception as e:
            logger.error(f"在虚拟机中执行命令失败: {str(e)}")
            return False, str(e)

    async def execute_program_in_vm(self, vm_name: str, program_path: str, arguments: list = None, username: str = "vboxuser", password: str = "123456", timeout: int = 120) -> tuple[bool, str]:
        """在虚拟机中直接执行程序（不通过cmd.exe）"""
        try:
            if arguments is None:
                arguments = []

            logger.info(f"在虚拟机中直接执行程序: {program_path} {' '.join(arguments)}")

            vbox_cmd = [
                self.vboxmanage_path,
                "guestcontrol", vm_name, "run",
                "--exe", program_path,
                "--username", username,
                "--password", password,
                "--wait-stdout", "--wait-stderr"
            ]

            # 添加程序参数
            if arguments:
                vbox_cmd.extend(["--"] + arguments)

            result = subprocess.run(vbox_cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode == 0:
                logger.info("程序执行成功")
                return True, result.stdout
            else:
                logger.error(f"程序执行失败: {result.stderr}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            logger.error("程序执行超时")
            return False, "程序执行超时"
        except Exception as e:
            logger.error(f"在虚拟机中执行程序失败: {str(e)}")
            return False, str(e)


 
def create_vm_controller(controller_type: str = None) -> VMController:
    if controller_type is None:
        # 从配置中读取控制器类型
        from app.core.config import get_settings
        settings = get_settings()
        controller_type = settings.virtualization.controller_type

    if controller_type.lower() == "virtualbox":
        return VBoxManageController()
    else:
        raise ValueError(f"not support vm type: {controller_type}")
