"""
avira EDR Client Implementation - 简化版本

这个模块提供简化的avira客户端实现。
只保留最有效的威胁检测方法：通过读取保存在隔离样本的文件头部信息获取威胁信息(avira会把恶意文件加密,并在文件头添加标签,修改后缀名.qua后保存隔离)。
"""

import os
import re
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pytz
from loguru import logger

from app.models.task import EDRAlert
from .base import EDRClient


class AviraEDRClient(EDRClient):
    async def get_alerts(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        file_hash: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[EDRAlert]:
        try:
            report_path = r"'C:\ProgramData\Avira\Endpoint Protection SDK\quarantine'"
            data = []
            # get_report_path = f"powershell.exe -Command Get-ChildItem {report_path} -File -Filter '*.qua' |  Select-Object -ExpandProperty Name"
            # success_get_path, output_path = (
            #     await self.vm_controller.execute_command_in_vm(
            #         self.vm_name,
            #         get_report_path,
            #         self.username,
            #         self.password,
            #         timeout=180,
            #     )
            # )
            program_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            arguments = [
                "-Command",
                f"Get-ChildItem {report_path} -File -Filter '*.qua' |  Select-Object -ExpandProperty Name",
            ]

            success_get_path, output_path = (
                await self.vm_controller.execute_program_in_vm(
                    self.vm_name,
                    program_path,
                    arguments,
                    self.username,
                    self.password,
                    timeout=60,
                )
            )
            if output_path.strip() == "":
                logger.info("Avira隔离区没有文件")
                return []
            for line_filename in output_path.splitlines():
                print(line_filename)  # 文件名
                if line_filename.endswith(".qua"):
                    report_path_temp = f"'C:\\ProgramData\\Avira\\Endpoint Protection SDK\\quarantine\\{line_filename}'"
                    print(f"匹配到文件: {report_path_temp}")
                    # parse_report = f"powershell.exe -Command C:\\get_report\\get_report_.ps1 -FilePath  {report_path_temp}"
                    # success, output = await self.vm_controller.execute_command_in_vm(
                    #     self.vm_name,
                    #     parse_report,
                    #     self.username,
                    #     self.password,
                    #     timeout=180,
                    # )
                    parse_report = [
                        "-Command",
                        f"C:\\get_report\\get_report_.ps1 -FilePath  {report_path_temp}",
                    ]

                    success, output = (
                        await self.vm_controller.execute_program_in_vm(
                            self.vm_name,
                            program_path,
                            parse_report,
                            self.username,
                            self.password,
                            timeout=60,
                        )
                    )
                    if success and output.strip():
                        try:
                            print(f"Output: \n{output}")
                            # 解析output
                            parse_report_out = json.loads(output)
                            alert_hash = str(abs(hash(str(output))))
                            # dt = datetime.strptime(
                            #     parse_report_out["utc"], "%Y-%m-%d %H:%M:%S"
                            # )
                            if parse_report_out["path"].startswith("\\\\?\\"):
                                path_f = parse_report_out["path"][4:]
                            dt = datetime.fromtimestamp(
                                parse_report_out["utc"], tz=None
                            ).strftime("%Y-%m-%d %H:%M:%S")
                            alert = EDRAlert(
                                alert_id=str(f"quarantine_{alert_hash}"),
                                quarantine_time=dt,
                                severity="None",
                                alert_type=parse_report_out["malware"],
                                # description=f"检测到威胁类型：",
                                file_path=path_f,
                                detect_reason="None",
                            )
                            data.append(alert)
                            return data
                        except Exception as e:
                            logger.error(f"解析Avira报告信息失败: {str(e)}")
                            return []
                else:
                    logger.warning(f"匹配文件失败: {line_filename}")
        except Exception as e:
            logger.error(f"获取Avira报告文件列表失败: {str(e)}")
            return []
