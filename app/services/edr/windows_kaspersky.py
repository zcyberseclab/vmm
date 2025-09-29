"""
kaspersky EDR Client Implementation - 简化版本

这个模块提供简化的kaspersky EDR客户端实现。
只保留最有效的威胁检测方法：先通过avp.com命令导出查杀日志到文件,在解析导出的日志文件获取威胁信息。
"""

import os
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pytz
from loguru import logger

from app.models.task import EDRAlert
from .base import EDRClient


class KasperskyEDRClient(EDRClient):
    async def get_alerts(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        file_hash: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[EDRAlert]:
        try:
            report_path = "C:\\Users\\vboxuser\\Desktop\\report.txt"
            export_report_cmd = f"& 'C:\\Program Files (x86)\\Kaspersky Lab\\Kaspersky 21.15\\avp.com' report FM /RA:{report_path}"
            logger.info(f"执行导出Kaspersky报告: {export_report_cmd}")
            logger.info(f"导出路径: {report_path}")
            success_export, _ = await self.vm_controller.execute_command_in_vm(
                self.vm_name,
                export_report_cmd,
                self.username,
                self.password,
                timeout=180,
            )

           
            #获取report.txt文件内容命令
            get_report_cmd = f"powershell.exe -Command Get-Content {report_path}"
            success, output = await self.vm_controller.execute_command_in_vm(
                self.vm_name, get_report_cmd, self.username, self.password, timeout=180
            )
            logger.info(f"powershell.exe -Command Get-Content: {success}")

            if success and output.strip():
                report_json = self.parse_kaspersky_log_to_json(
                    output, start_time, end_time, file_hash, file_name
                )
              
                return report_json
            else:
                logger.warning("avp.com命令执行失败或无输出")
                return []

        except Exception as e:
            logger.error(f"获取报告信息失败: {str(e)}")
            return []

    def parse_kaspersky_log_to_json(
        self,
        log_data,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        file_hash: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[EDRAlert]:
        
        DETECT_REASON_MAP = {
            "专家分析": "Log",
        }
        SEVERITY_MAP = {
            "高": "Critical",
        }
        
        try:
            data = []
            logger.info("解析Kaspersky日志数据")
            lines = log_data.splitlines()
            line_index = -1
            for i, line in enumerate(lines):
                parts = [p.strip() for p in line.split("\t") if p.strip()]  
                if "检测到" in parts: 
                    line_index = i
                    try:
                        time_field = parts[0]
                        str_time = time_field.replace("今天，", "")  # 去掉 "今天，"
                        # 如果你要解析为 datetime，取消注释下面这行（需要导入 datetime）
                        # dt = datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
                    except Exception as e:
                        # 如果解析失败，使用当前时间
                        logger.warning(f"无法解析隔离时间: {time_field}")
                        #dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"

                    alert_hash = str(abs(hash(str(line)))) 
                    reason_need_map = parts[19] if len(parts) > 19 else "None"
                    severity_need_map = parts[10] if len(parts) > 10 else "None"
                
                    alert = EDRAlert(
                        alert_id=str(f"quarantine_{alert_hash}"),
                        severity=SEVERITY_MAP.get(severity_need_map, "None"),
                        alert_type=parts[8],
                        process_name=parts[14],
                        detect_reason=DETECT_REASON_MAP.get(reason_need_map, "None"),
                        detection_time=str_time,
                        file_path=parts[1],
                        source="Kaspersky"
                    )
                    data.append(alert)
                    break  # 只处理第一个匹配行
    
            return data
        except Exception as e:
            logger.error(f"解析Kaspersky日志失败: {str(e)}")
            return []
