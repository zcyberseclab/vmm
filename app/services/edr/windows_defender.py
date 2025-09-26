"""
Windows Defender EDR Client Implementation

This module provides the Windows Defender specific implementation of the EDR client.
It handles communication with Windows Defender through PowerShell commands and
parses the quarantine information to generate EDR alerts.
"""

import os
import re
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

        try:
            # 使用多种方法获取Windows Defender检测信息
            quarantine_data = []

            # 方法1: 获取隔离区列表 - 使用短路径避免空格问题
            list_cmd = r'powershell -Command "C:\Progra~1\Windows~1\MpCmdRun.exe -Restore -ListAll"'
            success1, output1 = await self.vm_controller.execute_command_in_vm(
                self.vm_name, list_cmd, self.username, self.password, timeout=60
            )

            print("get_quarantine_info MpCmdRun -ListAll")
            print(f"Success: {success1}")
            print(f"Output: \n{output1}")

            if success1 and output1.strip():
                quarantine_data.extend(self._parse_quarantine_output(output1, file_name))

            # 方法2: 获取Windows Defender事件日志
            event_cmd = r'powershell -Command "Get-WinEvent -FilterHashtable @{LogName=\'Microsoft-Windows-Windows Defender/Operational\'; ID=1116,1117} -MaxEvents 10 | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-Table -AutoSize"'
            success2, output2 = await self.vm_controller.execute_command_in_vm(
                self.vm_name, event_cmd, self.username, self.password, timeout=60
            )

            print("get_quarantine_info Windows Event Log")
            print(f"Success: {success2}")
            print(f"Output: \n{output2}")

            if success2 and output2.strip():
                quarantine_data.extend(self._parse_event_log_output(output2, file_name))

            # 方法3: 获取威胁历史
            threat_cmd = r'powershell -Command "Get-MpThreatDetection | Select-Object DetectionTime, ThreatName, Resources, ProcessName | Format-Table -AutoSize"'
            success3, output3 = await self.vm_controller.execute_command_in_vm(
                self.vm_name, threat_cmd, self.username, self.password, timeout=60
            )

            print("get_quarantine_info Get-MpThreatDetection")
            print(f"Success: {success3}")
            print(f"Output: \n{output3}")

            if success3 and output3.strip():
                quarantine_data.extend(self._parse_threat_detection_output(output3, file_name))

            if not quarantine_data:
                logger.warning("所有Windows Defender检测方法都没有返回数据")

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
