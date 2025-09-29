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

            print("get_quarantine_info avp")
            print(f"Success: {success_export}")
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
            "专家分析": "Expert Analysis",
        }
        SEVERITY_MAP = {
            "高": "High",
        }
        
        try:
            data = []
            logger.info("解析Kaspersky日志数据")
            for line in log_data.splitlines():
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                if len(parts) < 16:
                    parts += [""] * (16 - len(parts))
                if (parts[5] not in ["检测到"]) or (parts[2] != file_name):
                    continue
                try:
                    # 移除时区信息进行解析
                    s = parts[0].replace("今天，", "")
                    #dt = datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
                except ValueError:
                    # 如果解析失败，使用当前时间
                    logger.warning(f"无法解析隔离时间: {parts[0]}")
                    #dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    
                alert_hash = (str(abs(hash(str(line)))))
                reason_need_map = parts[19] if len(parts) > 19 else "None"
                severity_need_map = parts[10]
                alert = EDRAlert(
                    alert_id=str(f"quarantine_{alert_hash}"),
                    quarantine_time=s,
                    severity=SEVERITY_MAP.get(severity_need_map, "None"),
                    alert_type=parts[8],
                    description=f"检测到威胁类型：{parts[8]}",
                    file_path=parts[1],
                    detect_reason=DETECT_REASON_MAP.get(reason_need_map, "None")
                )
                # print("----_parse_quarantine_output")
                # print(type(report_json))
                # #print(report_json, indent=2, ensure_ascii=False)
                # json_str = json.dumps(data, ensure_ascii=False, indent=2)
                data.append(alert)
            return data
        except Exception as e:
            logger.error(f"解析Kaspersky日志失败: {str(e)}")
            return []
