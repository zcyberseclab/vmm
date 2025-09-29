import os
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import pytz
from loguru import logger

from app.models.task import EDRAlert
from .base import EDRClient


class McafeeEDRClient(EDRClient):

    async def get_alerts(self, start_time: datetime, end_time: Optional[datetime] = None,
                        file_hash: Optional[str] = None, file_name: Optional[str] = None) -> List[EDRAlert]:

        try:
            alerts = []

            logger.info("开始获取Mcafee威胁检测信息...")

            # 获取威胁检测信息（通过事件日志）
            threat_data = await self._get_threat_datas(file_name)

            print("=== 威胁数据汇总 ===")
            print(f"获取到 {len(threat_data)} 条威胁数据")
            for i, data in enumerate(threat_data):
                print(f"记录 {i+1}: {data}")

            # 转换为EDR告警
            if threat_data:
                alerts.extend(self._convert_threat_data_to_alerts(threat_data, start_time, end_time, file_name))

            logger.info(f"从Mcafee获取到 {len(alerts)} 个告警")
            return alerts

        except Exception as e:
            logger.error(f"获取Mcafee告警失败: {str(e)}")
            return []

    async def _get_threat_datas(self, file_name: Optional[str] = None) -> List[Dict[str, Any]]:
       
        try:
            log_path = (r"'C:\ProgramData\McAfee\wps\Detection.log'")
            get_log_cmd = f"powershell -Command Get-Content {log_path}" 
            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, get_log_cmd, self.username, self.password, timeout=180
            )
                        
            if success and output.strip():
                data = json.loads(output)
                results = []
                results.append(data)
                return results
            
            else:
                logger.warning("McafeeParser命令执行失败或无输出")
                return []

        except Exception as e:
            logger.error(f"获取隔离区信息失败: {str(e)}")
            return []

    def _convert_threat_data_to_alerts(self, threat_data: List[Dict[str, Any]],
                                     start_time: datetime, end_time: Optional[datetime] = None,
                                     file_name: Optional[str] = None) -> List[EDRAlert]:
        """
        将威胁数据转换为EDR告警
        """
        alerts = []

        for item in threat_data:
            try:
                alert = EDRAlert(
                    alert_id=str(item.get("ThreatID", f"quarantine_{hash(str(item))}")),
                    severity='Critical',
                    alert_type=item.get('detection_name'),
                    process_name=item.get('initiator_name'),
                    detect_reason='Log',
                    detection_time=item.get('timestamp'),
                    file_path=item.get("target_name"),
                    source='McAfee',
                )
                alerts.append(alert)

            except Exception as e:
                logger.error(f"转换隔离区数据失败: {str(e)  }")
                continue
            
        return alerts

  