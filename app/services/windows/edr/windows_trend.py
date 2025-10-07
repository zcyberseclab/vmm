 

import os
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pytz
from loguru import logger
import xml.etree.ElementTree as ET
from app.models.task import EDRAlert
from .base import EDRClient


class TrendMicroEDRClient(EDRClient):
    async def get_alerts(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        file_hash: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[EDRAlert]:
        # 如果没有查杀病毒，没有report_path目录和文件
        # 获取Trend Micro EDR report文件内容命令
        report_path = "'C:\\ProgramData\\Trend Micro\\AMSP\\report\\10009\\'"
        data = []
        try:
            program_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            arguments = [
                "-Command",
                f"Get-ChildItem {report_path} -File -Filter '*.xml' | Select-Object -ExpandProperty Name",
            ]

            success_get_path, output_path = (
                await self.vm_controller.execute_program_in_vm(
                    self.vm_name,
                    program_path,
                    arguments,
                    self.username,
                    self.password,
                    timeout=self.timeouts.file_list_timeout,  # 使用配置的文件列表超时
                )
            )
            # get_report_path = f"Get-ChildItem {report_path} -File -Filter '*.xml' | Select-Object -ExpandProperty Name"
            # success_get_path, output_path = await self.vm_controller.execute_command_in_vm(
            #     self.vm_name,
            #     get_report_path,
            #     self.username,
            #     self.password,
            #     timeout=180,
            # )
        except Exception as e:
            logger.error(f"获取Trend Micro报告文件列表失败: {str(e)}")
            return []
        for line_filename in output_path.splitlines():
            print(line_filename)  # 文件名
            if line_filename.startswith("rca") and line_filename.endswith(".xml"):
                report_path_temp = f"'C:\\ProgramData\\Trend Micro\\AMSP\\report\\10009\\{line_filename}'"
                print(f"匹配到文件: {report_path_temp}")
                get_report_cmd = (
                    f"powershell.exe -Command Get-Content {report_path_temp}"
                )
                program_path = (
                    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                )
                get_report_cmd = [
                    "-Command",
                    f"Get-Content {report_path_temp}",
                ]

                success, output = await self.vm_controller.execute_program_in_vm(
                    self.vm_name,
                    program_path,
                    get_report_cmd,
                    self.username,
                    self.password,
                    timeout=self.timeouts.file_read_timeout,  # 使用配置的文件读取超时
                )
                if success and output.strip():
                    try:

                        xml_json_result = self.parse_rca_xml(output)
                        VirusName = xml_json_result["RcaReport"]["Trigger"]["Items"][
                            "VirusName"
                        ]
                        FileName = xml_json_result["RcaReport"]["Trigger"]["Items"][
                            "FileName"
                        ]
                        TriggerTime = xml_json_result["RcaReport"]["Summary"][
                            "TriggerTime"
                        ]
                        dt = datetime.fromtimestamp(int(TriggerTime)).strftime(
                            "%Y-%m-%dT%H:%M:%S"
                        )  # 本地时间
                        print(
                            f"病毒名称: {VirusName}, 文件名称: {FileName}",
                            f"触发时间: {dt}",
                        )
                        logger.info(f"xml 结果：{xml_json_result}")
                        alert_hash = str(
                            abs(hash(str(xml_json_result["RcaReport@attrib"])))
                        )
                        alert = EDRAlert(
                            severity="Critical",
                            alert_type=VirusName,
                            detect_reason="Log",
                            detection_time=dt,
                            file_path=FileName,
                            source="Trend",
                        )
                        data.append(alert)
                        return data
                    except Exception as e:
                        logger.error(f"解析Trend Micro报告信息失败: {str(e)}")
                        return []
                else:
                    logger.warning("Trend Micro命令执行失败或无输出")
            else:
                logger.warning(f"匹配文件失败: {line_filename}")
        return []

    def xml_to_dict(self, elem):
        """
        递归将 XML Element 转换为 dict
        - 普通节点 → {tag: {...}}
        - <Item> 节点特殊处理 → {name: value}
        - 同名子节点自动合并为 list
        """

        # ---------- 特殊处理 <Item> ----------
        if elem.tag == "Item":
            name = elem.attrib.get("name")
            value = elem.attrib.get("value")
            return {name: value}
        elif elem.tag == "Pattern":
            name = elem.attrib.get("type")
            value = elem.attrib.get("version")
            return {name: value}
        elif elem.tag == "Engine":
            name = elem.attrib.get("type")
            value = elem.attrib.get("version")
            return {name: value}
        elif elem.tag == "Link":
            id = elem.attrib.get("id")
            src = elem.attrib.get("src")
            dst = elem.attrib.get("dst")
            type = elem.attrib.get("type")
            return {"id": id, "src": src, "dst": dst, "type": type}
        node_dict = {}
        # ---------- 保存属性 ----------
        if elem.attrib:
            node_dict[elem.tag + "@attrib"] = elem.attrib

        # ---------- 递归解析子节点 ----------
        children = list(elem)
        if children:
            child_dict = {}
            for child in children:
                child_data = self.xml_to_dict(child)

                # 如果 child_data 是 dict，取第一个 key
                if isinstance(child_data, dict) and len(child_data) == 1:
                    key, value = next(iter(child_data.items()))
                    # print(key, value)
                else:
                    key, value = child.tag, child_data
                    # print(key, value)

                # Item 的情况已经直接展开，不需要 key = "Item"
                if child.tag == "Item":
                    if isinstance(value, dict):
                        child_dict.update(value)
                    else:
                        child_dict.update(child_data)
                else:
                    # 处理重复子节点
                    if key in child_dict:
                        if not isinstance(child_dict[key], list):
                            child_dict[key] = [child_dict[key]]
                        child_dict[key].append(value)
                    else:
                        child_dict[key] = value

            node_dict[elem.tag] = child_dict
        else:
            # ---------- 叶子节点 ----------
            text = elem.text.strip() if elem.text else ""
            node_dict[elem.tag] = text

        return node_dict

    def parse_rca_xml(self, xml_input):
        """输入 XML 字符串或文件路径，输出 JSON 对象"""
        try:
            if isinstance(xml_input, str) and xml_input.strip().startswith("<"):
                root = ET.fromstring(xml_input)  # 输入是字符串
            else:
                tree = ET.parse(xml_input)  # 输入是文件路径
                root = tree.getroot()
        except Exception as e:
            raise ValueError(f"解析 XML 出错: {e}")

        return self.xml_to_dict(root)
