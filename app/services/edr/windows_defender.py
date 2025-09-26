"""
Windows Defender EDR Client Implementation

This module provides the Windows Defender specific implementation of the EDR client.
It handles communication with Windows Defender through PowerShell commands and
parses the quarantine information to generate EDR alerts.
"""

import os
import re
import asyncio
import tempfile
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

import pytz
from loguru import logger

from app.models.task import EDRAlert
from .base import EDRClient


class WindowsDefenderEDRClient(EDRClient):
    """
    Windows Defender EDR client implementation.
    
    This class provides Windows Defender specific functionality for retrieving
    security alerts and quarantine information through PowerShell commands.
    """

    async def get_alerts(self, start_time: datetime, end_time: Optional[datetime] = None,
                        file_hash: Optional[str] = None, file_name: Optional[str] = None) -> List[EDRAlert]:
        """
        Retrieve alerts from Windows Defender.
        
        This method queries Windows Defender's quarantine system to retrieve
        information about detected threats and converts them to EDRAlert objects.
        
        Args:
            start_time: Start time for alert search
            end_time: End time for alert search (optional, defaults to current time)
            file_hash: Specific file hash to search for (optional)
            file_name: Specific file name to search for (optional)
            
        Returns:
            List of EDRAlert objects containing Windows Defender alerts
        """
        try:
            alerts = []

            # 获取隔离区信息
            quarantine_info = await self.get_quarantine_info(file_name)
            print("get_quarantine_info")
            print(quarantine_info)
            if quarantine_info:
                alerts.extend(self._convert_quarantine_to_alerts(quarantine_info, start_time, end_time))

            logger.info(f"从Windows Defender获取到 {len(alerts)} 个告警")
            return alerts

        except Exception as e:
            logger.error(f"获取Windows Defender告警失败: {str(e)}")
            return []

    async def get_quarantine_info(self, file_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取隔离信息 - 使用批处理文件方法"""
        try:
            quarantine_data = []

            list_cmd = r"& 'C:\Program Files\Windows Defender\MpCmdRun.exe' -Restore -ListAll"
            success1, output1 = await self.vm_controller.execute_command_in_vm(
                self.vm_name, list_cmd, self.username, self.password, timeout=60
            )

            print("get_quarantine_info MpCmdRun -ListAll")
            print(f"Success: {success1}")
            print(f"Output: \n{output1}")

            if success1 and output1.strip():
                quarantine_data.extend(self._parse_quarantine_output(output1, file_name))
 
            return quarantine_data

        except Exception as e:
            logger.error(f"获取隔离区信息失败: {str(e)}")
            return []

    
    def _parse_quarantine_output(self, output: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        解析MpCmdRun -Restore -ListAll的输出

        Args:
            output: MpCmdRun命令的输出
            filename: 要匹配的文件名（可选）

        Returns:
            解析后的隔离记录列表
        """
        logger.info("解析隔离区输出数据")
        print("----_parse_quarantine_output")
        print(output)

        if not output:
            return []

        # 按威胁名称分割输出
        threat_blocks = re.split(r'(?=ThreatName = )', output)[1:]
        threat_records = {}

        # 获取本地时区
        local_tz = pytz.timezone('Asia/Shanghai')  # 可以配置化

        for block in threat_blocks:
            threat_name_match = re.match(r'ThreatName = (.+)', block)
            if not threat_name_match:
                continue

            threat_name = threat_name_match.group(1).strip()

            # 查找文件条目
            file_entries = re.findall(
                r'file:([^\s]+)\s+quarantined at\s+(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}\s+\(UTC\))',
                block
            )

            for file_path, quarantine_time in file_entries:
                # 如果提供了文件名，进行匹配检查
                if filename:
                    quarantined_filename = os.path.basename(file_path)
                    input_filename = os.path.basename(filename)

                    match_found = (
                        filename in file_path or
                        input_filename == quarantined_filename or
                        input_filename in quarantined_filename or
                        quarantined_filename in input_filename
                    )

                    if not match_found:
                        continue

                # 解析时间
                try:
                    utc_time = datetime.strptime(quarantine_time, '%Y/%m/%d %H:%M:%S (UTC)')
                    utc_time = pytz.utc.localize(utc_time)

                    # 保留最新的记录
                    if threat_name not in threat_records or utc_time > threat_records[threat_name]['utc_time']:
                        # 转换为本地时间
                        local_time = utc_time.astimezone(local_tz).strftime('%Y/%m/%d %H:%M:%S (%Z)')
                        threat_records[threat_name] = {
                            'ThreatName': threat_name,
                            'QuarantineTime': local_time,
                            'FilePath': file_path,
                            'utc_time': utc_time
                        }
                except ValueError as e:
                    logger.warning(f"解析隔离时间失败: {quarantine_time} - {str(e)}")
                    continue

        # 构建结果列表
        results = []
        for record in threat_records.values():
            results.append({
                'ThreatName': record['ThreatName'],
                'QuarantineTime': record['QuarantineTime'],
                'FilePath': record['FilePath']
            })

        logger.info(f"解析到 {len(results)} 个隔离记录")
        return results

    def _convert_quarantine_to_alerts(self, quarantine_data: List[Dict[str, Any]],
                                    start_time: datetime, end_time: Optional[datetime] = None) -> List[EDRAlert]:
        """
        将隔离区数据转换为EDR告警

        Args:
            quarantine_data: 隔离区数据列表
            start_time: 开始时间
            end_time: 结束时间（可选）

        Returns:
            EDRAlert对象列表
        """
        alerts = []
        for item in quarantine_data:
            try:
                # 检查是否有威胁名称，如果没有则跳过（认为没有报警）
                threat_name = item.get('ThreatName')
                if not threat_name:
                    logger.debug("跳过没有威胁名称的记录")
                    continue

                # 使用 QuarantineTime 而不是 DetectionTime
                quarantine_time_str = item.get("QuarantineTime")
                if quarantine_time_str:
                    # 解析时间字符串，格式如: "2024/01/15 14:30:25 (CST)"
                    try:
                        # 移除时区信息进行解析
                        time_part = quarantine_time_str.split(' (')[0]
                        detection_time = datetime.strptime(time_part, '%Y/%m/%d %H:%M:%S')
                    except ValueError:
                        # 如果解析失败，使用当前时间
                        logger.warning(f"无法解析隔离时间: {quarantine_time_str}")
                        detection_time = datetime.now()

                    # 检查时间范围
                    if start_time <= detection_time <= (end_time or datetime.now()):
                        # 使用威胁名称作为报警类型标签
                        alert_type = f"Threat Detected: {threat_name}"

                        alert = EDRAlert(
                            alert_id=str(item.get("ThreatID", f"quarantine_{hash(str(item))}")),
                            timestamp=detection_time,
                            severity="High",
                            alert_type=alert_type,
                            description=f"威胁已被检测并隔离: {threat_name}",
                            additional_data=item
                        )
                        alerts.append(alert)
            except Exception as e:
                logger.error(f"转换隔离区数据失败: {str(e)}")
                continue
        return alerts

    def _parse_event_log_output(self, output: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        解析Windows事件日志输出
        """
        logger.info("解析Windows事件日志输出数据")
        records = []

        try:
            # 简单解析事件日志输出
            lines = output.strip().split('\n')
            for line in lines:
                if 'Defender' in line and ('threat' in line.lower() or 'malware' in line.lower()):
                    record = {
                        'source': 'Windows Event Log',
                        'detection_time': datetime.now().isoformat(),
                        'threat_name': 'Unknown',
                        'file_path': filename or 'Unknown',
                        'raw_output': line.strip()
                    }
                    records.append(record)

            logger.info(f"解析到 {len(records)} 个事件日志记录")
            return records

        except Exception as e:
            logger.error(f"解析事件日志输出失败: {str(e)}")
            return []

    def _parse_threat_detection_output(self, output: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        解析Get-MpThreatDetection输出
        """
        logger.info("解析威胁检测输出数据")
        records = []

        try:
            # 简单解析威胁检测输出
            lines = output.strip().split('\n')
            for line in lines:
                if line.strip() and not line.startswith('-') and 'DetectionTime' not in line:
                    # 尝试解析表格格式的输出
                    parts = line.split()
                    if len(parts) >= 2:
                        record = {
                            'source': 'Get-MpThreatDetection',
                            'detection_time': parts[0] if len(parts) > 0 else 'Unknown',
                            'threat_name': parts[1] if len(parts) > 1 else 'Unknown',
                            'file_path': filename or 'Unknown',
                            'raw_output': line.strip()
                        }
                        records.append(record)

            logger.info(f"解析到 {len(records)} 个威胁检测记录")
            return records

        except Exception as e:
            logger.error(f"解析威胁检测输出失败: {str(e)}")
            return []

    async def _extract_file_from_vm(self, vm_file_path: str) -> Optional[str]:
        """从虚拟机中提取文件内容"""
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_path = temp_file.name

            # 使用VBoxManage copyfrom
            vboxmanage_path = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
            copy_cmd = [
                vboxmanage_path, "guestcontrol", self.vm_name, "copyfrom",
                "--username", self.username, "--password", self.password,
                vm_file_path, temp_path
            ]

            result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0 and os.path.exists(temp_path):
                with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass

                return content
            else:
                logger.error(f"文件提取失败: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"文件提取异常: {str(e)}")
            return None

    async def _get_mpcmdrun_via_copyto(self) -> List[Dict[str, Any]]:
        """使用copyto + PowerShell脚本方法获取MpCmdRun输出"""
        try:
            logger.info("使用copyto + PowerShell脚本方法获取MpCmdRun输出...")

            # 步骤1: 创建本地PowerShell脚本
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ps1', encoding='utf-8') as ps_file:
                ps_script = f"""# MpCmdRun Quarantine Information Collection
Write-Host "Executing MpCmdRun to get quarantine information..."

# 输出文件
$outputFile = "C:\\Users\\{self.username}\\Desktop\\mpcmdrun_result.txt"

# 执行MpCmdRun -Restore -ListAll
try {{
    $mpcmdResult = & 'C:\\Program Files\\Windows Defender\\MpCmdRun.exe' -Restore -ListAll 2>&1
    $mpcmdResult | Out-File -FilePath $outputFile -Encoding UTF8
    Write-Host "MpCmdRun execution completed"
}} catch {{
    "MpCmdRun Error: $_" | Out-File -FilePath $outputFile -Encoding UTF8
    Write-Host "MpCmdRun execution failed: $_"
}}

Write-Host "Script completed successfully"
"""
                ps_file.write(ps_script)
                local_ps_path = ps_file.name

            logger.info("本地PowerShell脚本创建成功")

            # 步骤2: 复制PowerShell脚本到虚拟机
            vm_ps_path = f"C:\\Users\\{self.username}\\Desktop\\mpcmdrun_script.ps1"

            # 使用VBoxManage copyto
            vboxmanage_path = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
            copy_cmd = [
                vboxmanage_path, "guestcontrol", self.vm_name, "copyto",
                "--username", self.username, "--password", self.password,
                local_ps_path, vm_ps_path
            ]

            result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.error(f"PowerShell脚本上传失败: {result.stderr}")
                return []

            logger.info("PowerShell脚本上传成功")

            # 步骤3: 执行PowerShell脚本
            exec_cmd = f'powershell.exe -ExecutionPolicy Bypass -File {vm_ps_path}'

            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, exec_cmd, self.username, self.password, timeout=120
            )

            if not success:
                logger.error(f"PowerShell脚本执行失败: {output}")
                return []

            logger.info(f"PowerShell脚本执行成功: {output}")

            # 步骤4: 等待执行完成
            await asyncio.sleep(5)

            # 步骤5: 使用copyfrom提取结果文件
            logger.info("提取MpCmdRun结果文件...")
            result_file = f"C:\\Users\\{self.username}\\Desktop\\mpcmdrun_result.txt"
            local_content = await self._extract_file_from_vm(result_file)

            if local_content:
                logger.info(f"成功获取MpCmdRun输出 ({len(local_content)} 字符)")
                logger.info(f"MpCmdRun输出内容: {local_content[:200]}...")

                # 检查是否包含威胁信息
                if any(keyword in local_content.lower() for keyword in ["quarantined", "threatname", "trojan", "malware", "virus", "threat"]):
                    return self._parse_mpcmdrun_output(local_content)
                else:
                    logger.info("MpCmdRun执行成功，但当前无隔离项目")
                    return []
            else:
                logger.warning("未能提取MpCmdRun结果文件")
                return []

            # 清理本地文件
            try:
                os.unlink(local_ps_path)
            except:
                pass

        except Exception as e:
            logger.error(f"copyto + PowerShell脚本方法失败: {str(e)}")
            return []

    async def _get_event_log_via_batch(self) -> List[Dict[str, Any]]:
        """使用批处理文件方法获取Windows事件日志"""
        try:
            logger.info("使用批处理文件方法获取Windows事件日志...")

            # 步骤1: 创建批处理文件
            batch_file = f"C:\\Users\\{self.username}\\Desktop\\get_eventlog.bat"
            result_file = f"C:\\Users\\{self.username}\\Desktop\\eventlog_result.txt"

            # Windows事件日志PowerShell命令
            powershell_cmd = "powershell -Command \"Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational'; ID=1116,1117} -MaxEvents 10 | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-Table -AutoSize\""

            # 创建批处理文件的命令
            create_batch_cmd = f"""echo @echo off > {batch_file} && echo echo Getting event logs... >> {batch_file} && echo {powershell_cmd} ^> {result_file} 2^>^&1 >> {batch_file} && echo echo Event log check completed. >> {batch_file}"""

            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, create_batch_cmd, self.username, self.password, timeout=30
            )

            if not success:
                logger.error(f"创建事件日志批处理文件失败: {output}")
                return []

            # 步骤2: 执行批处理文件
            logger.info("执行事件日志批处理文件...")
            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, batch_file, self.username, self.password, timeout=120
            )

            if not success:
                logger.error(f"执行事件日志批处理文件失败: {output}")
                return []

            # 步骤3: 等待执行完成
            await asyncio.sleep(5)

            # 步骤4: 使用copyfrom提取结果文件
            logger.info("提取事件日志结果文件...")
            local_content = await self._extract_file_from_vm(result_file)

            if local_content:
                logger.info(f"成功获取事件日志输出 ({len(local_content)} 字符)")
                print("=" * 60)
                print("🎉 Windows事件日志真实输出:")
                print(local_content)
                print("=" * 60)
                return self._parse_event_log_output(local_content)
            else:
                logger.warning("未能提取事件日志结果文件")
                return []

        except Exception as e:
            logger.error(f"事件日志批处理文件方法失败: {str(e)}")
            return []

    async def _get_threat_detection_via_batch(self) -> List[Dict[str, Any]]:
        """使用批处理文件方法获取威胁检测信息"""
        try:
            logger.info("使用批处理文件方法获取威胁检测信息...")

            # 步骤1: 创建批处理文件
            batch_file = f"C:\\Users\\{self.username}\\Desktop\\get_threats.bat"
            result_file = f"C:\\Users\\{self.username}\\Desktop\\threats_result.txt"

            # 威胁检测PowerShell命令
            powershell_cmd = "powershell -Command \"Get-MpThreatDetection | Select-Object DetectionTime, ThreatName, Resources, ProcessName | Format-Table -AutoSize\""

            # 创建批处理文件的命令
            create_batch_cmd = f"""echo @echo off > {batch_file} && echo echo Getting threat detections... >> {batch_file} && echo {powershell_cmd} ^> {result_file} 2^>^&1 >> {batch_file} && echo echo Threat detection check completed. >> {batch_file}"""

            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, create_batch_cmd, self.username, self.password, timeout=30
            )

            if not success:
                logger.error(f"创建威胁检测批处理文件失败: {output}")
                return []

            # 步骤2: 执行批处理文件
            logger.info("执行威胁检测批处理文件...")
            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, batch_file, self.username, self.password, timeout=120
            )

            if not success:
                logger.error(f"执行威胁检测批处理文件失败: {output}")
                return []

            # 步骤3: 等待执行完成
            await asyncio.sleep(5)

            # 步骤4: 使用copyfrom提取结果文件
            logger.info("提取威胁检测结果文件...")
            local_content = await self._extract_file_from_vm(result_file)

            if local_content:
                logger.info(f"成功获取威胁检测输出 ({len(local_content)} 字符)")
                print("=" * 60)
                print("🎉 威胁检测真实输出:")
                print(local_content)
                print("=" * 60)
                return self._parse_threat_detection_output(local_content)
            else:
                logger.warning("未能提取威胁检测结果文件")
                return []

        except Exception as e:
            logger.error(f"威胁检测批处理文件方法失败: {str(e)}")
            return []

    async def _copy_to_vm(self, local_file: str, vm_file: str) -> bool:
        """复制文件到虚拟机"""
        try:
            vboxmanage_path = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
            copy_cmd = [
                vboxmanage_path, "guestcontrol", self.vm_name, "copyto",
                "--username", self.username, "--password", self.password,
                local_file, vm_file
            ]

            result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info(f"文件复制成功: {local_file} -> {vm_file}")
                return True
            else:
                logger.error(f"文件复制失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"文件复制异常: {str(e)}")
            return False

    async def _get_mpcmdrun_via_copyto(self) -> List[Dict[str, Any]]:
        """使用copyto方法获取MpCmdRun输出 - 最终解决方案"""
        try:
            logger.info("使用copyto方法获取MpCmdRun输出...")

            # 创建本地PowerShell脚本
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ps1', encoding='utf-8') as ps_file:
                ps_script = f"""# Windows Defender MpCmdRun Script - Final Solution
Write-Host "Starting Windows Defender check..."

try {{
    # 输出文件路径
    $outputFile = "C:\\Users\\{self.username}\\Desktop\\mpcmd_final_result.txt"
    $errorFile = "C:\\Users\\{self.username}\\Desktop\\mpcmd_final_error.txt"

    # 方法1: 直接执行MpCmdRun
    Write-Host "Executing MpCmdRun directly..."

    try {{
        $result = & 'C:\\Program Files\\Windows Defender\\MpCmdRun.exe' -Restore -ListAll 2>&1
        $result | Out-File -FilePath $outputFile -Encoding UTF8
        Write-Host "MpCmdRun direct execution completed"
    }} catch {{
        Write-Host "Direct execution failed: $_"
        $_.Exception.Message | Out-File -FilePath $errorFile -Encoding UTF8
    }}

    # 方法2: 使用Start-Process
    Write-Host "Trying Start-Process method..."

    try {{
        $process = Start-Process -FilePath 'C:\\Program Files\\Windows Defender\\MpCmdRun.exe' -ArgumentList '-Restore', '-ListAll' -Wait -NoNewWindow -PassThru -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile
        Write-Host "Start-Process completed with exit code: $($process.ExitCode)"
    }} catch {{
        Write-Host "Start-Process failed: $_"
    }}

    # 检查输出文件
    if (Test-Path $outputFile) {{
        $content = Get-Content $outputFile -Raw
        Write-Host "Output file created with $($content.Length) characters"
    }}

    # 检查错误文件
    if (Test-Path $errorFile) {{
        $errorContent = Get-Content $errorFile -Raw
        if ($errorContent.Length -gt 0) {{
            Write-Host "Error file created with $($errorContent.Length) characters"
        }}
    }}

}} catch {{
    Write-Host "Script error: $_"
    $_.Exception.Message | Out-File -FilePath "C:\\Users\\{self.username}\\Desktop\\script_error.txt" -Encoding UTF8
}}

Write-Host "Script completed successfully"
"""
                ps_file.write(ps_script)
                local_ps_path = ps_file.name

            logger.info(f"本地PowerShell脚本创建: {local_ps_path}")

            # 复制脚本到虚拟机
            vm_ps_path = f"C:\\Users\\{self.username}\\Desktop\\mpcmd_final_script.ps1"

            if not await self._copy_to_vm(local_ps_path, vm_ps_path):
                logger.error("PowerShell脚本复制失败")
                return []

            # 执行PowerShell脚本
            logger.info("执行PowerShell脚本...")
            exec_cmd = f'powershell.exe -ExecutionPolicy Bypass -File {vm_ps_path}'

            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, exec_cmd, self.username, self.password, timeout=180
            )

            if not success:
                logger.error(f"PowerShell脚本执行失败: {output}")
                return []

            logger.info(f"PowerShell脚本执行成功: {output}")

            # 等待执行完成
            await asyncio.sleep(10)

            # 提取结果文件
            result_files = [
                f"C:\\Users\\{self.username}\\Desktop\\mpcmd_final_result.txt",
                f"C:\\Users\\{self.username}\\Desktop\\mpcmd_final_error.txt"
            ]

            for result_file in result_files:
                content = await self._extract_file_from_vm(result_file)

                if content and len(content.strip()) > 0:
                    logger.info(f"成功获取MpCmdRun输出 ({len(content)} 字符)")
                    print("=" * 60)
                    print("🎉 MpCmdRun真实输出 (copyto方法):")
                    print(content)
                    print("=" * 60)

                    # 检查是否包含威胁信息
                    if any(keyword in content.lower() for keyword in ["quarantined", "threatname", "trojan", "malware", "virus", "threat"]):
                        return self._parse_mpcmdrun_output(content)
                    elif "no items" in content.lower() or len(content.strip()) > 50:
                        logger.info("MpCmdRun执行成功，但当前无隔离项目")
                        return []

            logger.warning("未能获取有效的MpCmdRun输出")
            return []

        except Exception as e:
            logger.error(f"copyto方法失败: {str(e)}")
            return []
        finally:
            # 清理本地文件
            try:
                if 'local_ps_path' in locals():
                    os.unlink(local_ps_path)
            except:
                pass
