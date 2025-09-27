"""
Windows Defender EDR Client Implementation - 简化版本

这个模块提供简化的Windows Defender EDR客户端实现。
只保留最有效的威胁检测方法：通过Windows事件日志获取威胁信息。
"""

import os
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

import pytz
from loguru import logger

from app.models.task import EDRAlert
from .base import EDRClient


class WindowsDefenderEDRClient(EDRClient):
    """
    Windows Defender EDR客户端 - 简化版本
    
    只使用最可靠的方法：通过Windows事件日志获取威胁检测信息
    """

    async def get_alerts(self, start_time: datetime, end_time: Optional[datetime] = None,
                        file_hash: Optional[str] = None, file_name: Optional[str] = None) -> List[EDRAlert]:

        try:
            alerts = []

            logger.info("开始获取Windows Defender威胁检测信息...")

            # 获取威胁检测信息（通过事件日志）
            threat_data = await self._get_threat_events(file_name)

            print("=== 威胁数据汇总 ===")
            print(f"获取到 {len(threat_data)} 条威胁数据")
            for i, data in enumerate(threat_data):
                print(f"记录 {i+1}: {data}")

            # 转换为EDR告警
            if threat_data:
                alerts.extend(self._convert_threat_data_to_alerts(threat_data, start_time, end_time))

            logger.info(f"从Windows Defender获取到 {len(alerts)} 个告警")
            return alerts

        except Exception as e:
            logger.error(f"获取Windows Defender告警失败: {str(e)}")
            return []

    async def _get_threat_events(self, file_name: Optional[str] = None) -> List[Dict[str, Any]]:
       
        try:
            logger.info("查询Windows Defender事件日志...")
            threat_data = []

  
            program_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            arguments = [
                "-Command",
                "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational'; ID=1116,1117,1118,1119} -MaxEvents 20 | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-List"
            ]

            success, output = await self.vm_controller.execute_program_in_vm(
                self.vm_name, program_path, arguments, self.username, self.password, timeout=60
            )

            # 如果方法1失败，回退到cmd.exe方法
            if not success:
                logger.warning("PowerShell直接执行失败，回退到cmd.exe方法...")
                event_cmd = 'powershell -Command "Get-WinEvent -FilterHashtable @{LogName=\'Microsoft-Windows-Windows Defender/Operational\'; ID=1116,1117,1118,1119} -MaxEvents 20 | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-List"'

                success, output = await self.vm_controller.execute_command_in_vm(
                    self.vm_name, event_cmd, self.username, self.password, timeout=60
                )

            print(f"=== Windows Defender 事件日志查询结果 ===")
            print(f"Success: {success}")
            print(f"Output: \n{output}")
            print("=" * 60)

            if success and output.strip() and ("TimeCreated" in output or "Message" in output):
                parsed_events = self._parse_event_log_output(output, file_name)
                if parsed_events:
                    logger.info(f"从事件日志解析到 {len(parsed_events)} 个威胁记录")
                    threat_data.extend(parsed_events)
                else:
                    logger.info("事件日志解析未发现威胁记录")
            else:
                logger.warning("事件日志查询失败或无数据")

            return threat_data

        except Exception as e:
            logger.error(f"获取威胁事件日志失败: {str(e)}")
            return []

    def _convert_threat_data_to_alerts(self, threat_data: List[Dict[str, Any]], 
                                     start_time: datetime, end_time: Optional[datetime] = None) -> List[EDRAlert]:
        """
        将威胁数据转换为EDR告警
        """
        alerts = []
        for item in threat_data:
            try:
                # 检查是否有威胁名称
                threat_name = item.get('ThreatName') or item.get('threat_name')
                if not threat_name or threat_name == 'Unknown':
                    logger.debug("跳过没有威胁名称的记录")
                    continue

                # 获取检测时间
                detection_time_str = (item.get('DetectionTime') or 
                                    item.get('detection_time') or 
                                    item.get('TimeCreated'))
                
                if detection_time_str:
                    try:
                        # 尝试解析不同的时间格式
                        if isinstance(detection_time_str, str):
                            # 移除时区信息进行解析
                            time_part = detection_time_str.split(' (')[0].split('.')[0]
                            # 尝试多种时间格式
                            for fmt in ['%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S']:
                                try:
                                    detection_time = datetime.strptime(time_part, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                # 如果所有格式都失败，使用当前时间
                                detection_time = datetime.now()
                        else:
                            detection_time = detection_time_str
                    except (ValueError, AttributeError):
                        detection_time = datetime.now()
                else:
                    detection_time = datetime.now()

                # 检查时间范围
                if start_time <= detection_time <= (end_time or datetime.now()):
                    # 获取文件路径
                    file_path = (item.get('FilePath') or 
                               item.get('file_path') or 
                               item.get('Resources') or 
                               'Unknown')

                    # 创建告警描述
                    description = f"Windows Defender检测到威胁: {threat_name}"
                    
                    # 添加更多详细信息
                    if item.get('Action'):
                        description += f" (操作: {item.get('Action')})"
                    if item.get('Severity'):
                        description += f" (严重性: {item.get('Severity')})"

                    # 确定严重性
                    severity = "High"
                    if any(keyword in threat_name.lower() for keyword in ['trojan', 'virus', 'malware', 'worm']):
                        severity = "Critical"
                    elif any(keyword in threat_name.lower() for keyword in ['adware', 'pup']):
                        severity = "Medium"

                    alert = EDRAlert(
                        alert_id=str(hash(f"{threat_name}_{detection_time}_{file_path}")),
                        timestamp=detection_time,
                        severity=severity,
                        alert_type=f"Threat Detected: {threat_name}",
                        description=description,
                        additional_data=item
                    )
                    alerts.append(alert)
                    
            except Exception as e:
                logger.error(f"转换威胁数据失败: {str(e)}")
                continue
                
        return alerts

    def _parse_event_log_output(self, output: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        解析Windows事件日志输出 - 专门处理Windows Defender事件日志
        """
        logger.info("解析Windows事件日志输出数据")
        records = []

        try:
            if not output or output.strip() == "":
                logger.info("事件日志输出为空")
                return records

            # 检查是否包含威胁信息
            threat_keywords = ['名称:', 'name:', 'threat', 'trojan', 'virus', 'malware', 'worm', 'defender']
            if not any(keyword in output.lower() for keyword in threat_keywords):
                logger.info("事件日志中未发现威胁相关信息")
                return records

            # 解析Format-List格式的事件日志输出
            current_record = {}
            current_message = []
            lines = output.strip().split('\n')

            for line in lines:
                line_stripped = line.strip()

                if not line_stripped:
                    # 空行表示一个记录结束
                    if current_record and (current_record.get('Message') or current_record.get('TimeCreated')):
                        # 处理完整的消息
                        full_message = '\n'.join(current_message)
                        current_record['Message'] = full_message

                        # 从消息中提取威胁信息
                        threat_info = self._extract_threat_info_from_message(full_message)

                        if threat_info['threat_name'] != 'Unknown':
                            record = {
                                'ThreatName': threat_info['threat_name'],
                                'DetectionTime': current_record.get('TimeCreated', datetime.now().isoformat()),
                                'FilePath': threat_info['file_path'] or filename or 'Unknown',
                                'ProcessName': threat_info['process_name'],
                                'Action': threat_info['action'],
                                'Severity': threat_info['severity'],
                                'EventId': current_record.get('Id', 'Unknown'),
                                'Message': full_message,
                                'source': 'Windows Event Log'
                            }
                            records.append(record)
                            logger.info(f"解析到威胁: {threat_info['threat_name']}")

                    # 重置当前记录
                    current_record = {}
                    current_message = []
                    continue

                # 解析键值对格式
                if ':' in line_stripped and not line_stripped.startswith(' '):
                    # 这是一个新的字段
                    parts = line_stripped.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()

                        if key in ['TimeCreated', 'Id', 'LevelDisplayName']:
                            current_record[key] = value
                        elif key == 'Message':
                            current_record[key] = value
                            current_message = [value] if value else []
                else:
                    # 这是消息的续行
                    if 'Message' in current_record:
                        current_message.append(line_stripped)

            # 处理最后一个记录
            if current_record and current_record.get('Message'):
                full_message = '\n'.join(current_message)
                current_record['Message'] = full_message

                threat_info = self._extract_threat_info_from_message(full_message)

                if threat_info['threat_name'] != 'Unknown':
                    record = {
                        'ThreatName': threat_info['threat_name'],
                        'DetectionTime': current_record.get('TimeCreated', datetime.now().isoformat()),
                        'FilePath': threat_info['file_path'] or filename or 'Unknown',
                        'ProcessName': threat_info['process_name'],
                        'Action': threat_info['action'],
                        'Severity': threat_info['severity'],
                        'EventId': current_record.get('Id', 'Unknown'),
                        'Message': full_message,
                        'source': 'Windows Event Log'
                    }
                    records.append(record)
                    logger.info(f"解析到威胁: {threat_info['threat_name']}")

            logger.info(f"总共解析到 {len(records)} 个事件日志记录")
            return records

        except Exception as e:
            logger.error(f"解析事件日志输出失败: {str(e)}")
            logger.error(f"原始输出: {output[:500]}...")
            return []

    def _extract_threat_info_from_message(self, message: str) -> Dict[str, str]:
        """从Windows Defender事件消息中提取威胁信息"""
        threat_info = {
            'threat_name': 'Unknown',
            'file_path': 'Unknown',
            'process_name': 'Unknown',
            'action': 'Unknown',
            'severity': 'Unknown'
        }

        try:
            # 提取威胁名称 - 支持中英文，考虑前面可能有空格
            # 中文格式: "        名称: TrojanDropper:Win32/Conficker.gen!A"
            # 英文格式: "        Name: TrojanDropper:Win32/Conficker.gen!A"
            name_patterns = [
                r'\s*名称:\s*([^\r\n]+)',
                r'\s*Name:\s*([^\r\n]+)',
                r'\s*ThreatName:\s*([^\r\n]+)'
            ]

            for pattern in name_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    threat_info['threat_name'] = match.group(1).strip()
                    break

            # 提取文件路径 - 考虑前面可能有空格
            # 格式: "        路径: file:_C:\Users\vboxuser\Desktop\C9E0917FE3231A652C014AD76B55B26A.exe"
            path_patterns = [
                r'\s*路径:\s*file:_([^\r\n]+)',
                r'\s*Path:\s*file:_([^\r\n]+)',
                r'file:_([^\r\n;,\s]+)'
            ]

            for pattern in path_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    threat_info['file_path'] = match.group(1).strip()
                    break

            # 提取进程名称 - 考虑前面可能有空格
            # 格式: "        进程名称: C:\Windows\System32\VBoxService.exe"
            process_patterns = [
                r'\s*进程名称:\s*([^\r\n]+)',
                r'\s*Process Name:\s*([^\r\n]+)',
                r'\s*ProcessName:\s*([^\r\n]+)'
            ]

            for pattern in process_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    threat_info['process_name'] = match.group(1).strip()
                    break

            # 提取操作 - 考虑前面可能有空格
            # 格式: "        操作: 隔离"
            action_patterns = [
                r'\s*操作:\s*([^\r\n]+)',
                r'\s*Action:\s*([^\r\n]+)'
            ]

            for pattern in action_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    threat_info['action'] = match.group(1).strip()
                    break

            # 提取严重性 - 考虑前面可能有空格
            # 格式: "        严重性: 严重"
            severity_patterns = [
                r'\s*严重性:\s*([^\r\n]+)',
                r'\s*Severity:\s*([^\r\n]+)'
            ]

            for pattern in severity_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    threat_info['severity'] = match.group(1).strip()
                    break

        except Exception as e:
            logger.error(f"提取威胁信息失败: {str(e)}")

        return threat_info
