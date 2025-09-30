"""
Sysmon Analysis Service
This service handles malware analysis using Sysmon-enabled virtual machines.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from app.core.config import get_settings
from app.services.vm_controller import create_vm_controller
from app.services.vm_pool_manager import get_vm_pool_manager
from tools.sysmon.sysmon_manager import SysmonManager, SysmonConfigType, SysmonStatus


class SysmonAnalysisEngine:
    """Sysmon-based malware analysis engine"""
    
    def __init__(self):
        self.settings = get_settings()
        self.vm_controller = create_vm_controller()
        self.sysmon_manager = SysmonManager(self.vm_controller)
        self.vm_pool_manager = None
        
    async def initialize(self):
        """Initialize the analysis engine"""
        self.vm_pool_manager = await get_vm_pool_manager()
        logger.info("Sysmon Analysis Engine initialized")
    
    async def analyze_sample(
        self,
        sample_path: str,
        sample_hash: str,
        analysis_timeout: int = 300,
        config_type: str = "light"
    ) -> Dict[str, Any]:
        """
        Analyze a malware sample using Sysmon

        Args:
            sample_path: Path to the sample file
            sample_hash: SHA256 hash of the sample
            analysis_timeout: Analysis timeout in seconds
            config_type: Sysmon configuration type ("light", "full", "custom")

        Returns:
            Analysis results dictionary
        """
        logger.info(f"🔍 SysmonAnalysisEngine.analyze_sample() called")
        logger.info(f"   - Sample: {sample_path}")
        logger.info(f"   - Hash: {sample_hash}")
        logger.info(f"   - Config: {config_type}")
        logger.info(f"   - Timeout: {analysis_timeout}s")

        if not self.settings.sysmon_analysis.enabled:
            raise Exception("Sysmon analysis is disabled in configuration")

        # Get Sysmon VM configuration
        vm_config = self.settings.sysmon_analysis.vm
        vm_name = vm_config.name

        logger.info(f"🚀 Starting Sysmon analysis for sample {sample_hash} on VM {vm_name}")

        analysis_id = f"sysmon_{sample_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"📋 Analysis ID: {analysis_id}")
        
        try:
            # Prepare VM
            await self._prepare_sysmon_vm(vm_name, config_type)
            
            # Execute sample and collect events
            events = await self._execute_and_monitor(
                vm_name, sample_path, analysis_timeout, vm_config
            )
            
            # Analyze collected events
            analysis_results = await self._analyze_events(events, sample_hash)
            
            # Generate final report
            report = await self._generate_report(
                analysis_id, sample_hash, sample_path, events, analysis_results
            )
            
            logger.info(f"Sysmon analysis completed for sample {sample_hash}")
            return report
            
        except Exception as e:
            logger.error(f"Sysmon analysis failed for sample {sample_hash}: {str(e)}")
            raise
        finally:
            # Cleanup VM
            await self._cleanup_vm(vm_name, vm_config)
    
    async def _prepare_sysmon_vm(self, vm_name: str, config_type: str):
        """Prepare VM for Sysmon analysis"""
        logger.info(f"Preparing Sysmon VM: {vm_name}")
        
        # Get VM configuration
        vm_config = self.settings.sysmon_analysis.vm
        
        # Stop VM if running
        await self._ensure_vm_stopped(vm_name)
        
        # Restore baseline snapshot
        logger.info(f"Restoring snapshot: {vm_config.baseline_snapshot}")
        if not await self.vm_controller.revert_snapshot(vm_name, vm_config.baseline_snapshot):
            raise Exception(f"Failed to restore snapshot for VM {vm_name}")
        
        # Start VM
        if not await self.vm_controller.power_on(vm_name):
            raise Exception(f"Failed to start VM {vm_name}")
        
        # Wait for VM to be ready
        await asyncio.sleep(30)
        
        # Check if Sysmon is installed and running
        status, details = await self.sysmon_manager.get_sysmon_status(
            vm_name, vm_config.username, vm_config.password
        )
        
        if status == SysmonStatus.NOT_INSTALLED:
            # Install Sysmon
            logger.info(f"Installing Sysmon on VM {vm_name}")
            sysmon_config_type = SysmonConfigType(config_type)
            success, message = await self.sysmon_manager.install_sysmon(
                vm_name, vm_config.username, vm_config.password, sysmon_config_type
            )
            if not success:
                raise Exception(f"Failed to install Sysmon: {message}")
        elif status in [SysmonStatus.STOPPED, SysmonStatus.ERROR]:
            # Try to restart or reinstall Sysmon
            logger.warning(f"Sysmon status is {status}, attempting to reinstall")
            sysmon_config_type = SysmonConfigType(config_type)
            success, message = await self.sysmon_manager.install_sysmon(
                vm_name, vm_config.username, vm_config.password, 
                sysmon_config_type, force_reinstall=True
            )
            if not success:
                raise Exception(f"Failed to reinstall Sysmon: {message}")
        
        # Verify Sysmon is working
        await asyncio.sleep(5)
        status, details = await self.sysmon_manager.get_sysmon_status(
            vm_name, vm_config.username, vm_config.password
        )
        
        if status not in [SysmonStatus.RUNNING, SysmonStatus.INSTALLED]:
            raise Exception(f"Sysmon is not running properly: {status} - {details}")
        
        logger.info(f"Sysmon VM {vm_name} is ready for analysis")
    
    async def _execute_and_monitor(
        self, 
        vm_name: str, 
        sample_path: str, 
        timeout: int,
        vm_config: Any
    ) -> List[Dict]:
        """Execute sample and monitor with Sysmon"""
        logger.info(f"Executing sample and monitoring with Sysmon")
        
        # Copy sample to VM
        vm_sample_path = f"{vm_config.desktop_path}\\sample.exe"
        success = await self.vm_controller.copy_file_to_vm(
            vm_name, sample_path, vm_sample_path, 
            vm_config.username, vm_config.password
        )
        
        if not success:
            raise Exception("Failed to copy sample to VM")
        
        # Clear existing Sysmon events (optional)
        clear_cmd = 'wevtutil cl "Microsoft-Windows-Sysmon/Operational"'
        await self.vm_controller.execute_command_in_vm(
            vm_name, clear_cmd, vm_config.username, vm_config.password, timeout=30
        )
        
        # Wait before execution
        pre_delay = self.settings.sysmon_analysis.analysis_settings.pre_execution_delay
        await asyncio.sleep(pre_delay)
        
        # Execute sample
        logger.info("Executing sample in VM")
        execute_cmd = f'Start-Process -FilePath "{vm_sample_path}" -WindowStyle Hidden'
        success, output = await self.vm_controller.execute_command_in_vm(
            vm_name, execute_cmd, vm_config.username, vm_config.password, timeout=30
        )
        
        if not success:
            logger.warning(f"Sample execution may have failed: {output}")
        
        # Monitor for specified time
        post_delay = self.settings.sysmon_analysis.analysis_settings.post_execution_delay
        logger.info(f"Monitoring system activity for {post_delay} seconds")
        await asyncio.sleep(post_delay)
        
        # Collect Sysmon events
        max_events = self.settings.sysmon_analysis.event_collection.max_events
        success, events = await self.sysmon_manager.get_sysmon_events(
            vm_name, max_events, vm_config.username, vm_config.password
        )
        
        if not success:
            logger.warning("Failed to collect Sysmon events")
            return []
        
        logger.info(f"Collected {len(events)} Sysmon events")
        return events
    
    async def _analyze_events(self, events: List[Dict], sample_hash: str) -> Dict[str, Any]:
        """Analyze collected Sysmon events"""
        logger.info(f"Analyzing {len(events)} Sysmon events")
        
        analysis = {
            "total_events": len(events),
            "event_types": {},
            "processes": {},
            "network_connections": [],
            "file_operations": [],
            "registry_operations": [],
            "suspicious_activities": [],
            "detailed_events": []  # 新增：详细事件信息
        }
        
        for event in events:
            event_id = event.get("Id", 0)

            # Count event types
            if event_id not in analysis["event_types"]:
                analysis["event_types"][event_id] = 0
            analysis["event_types"][event_id] += 1

            # 解析详细事件信息
            detailed_event = self._parse_detailed_event(event)
            if detailed_event:
                analysis["detailed_events"].append(detailed_event)

            # Analyze specific event types
            if event_id == 1:  # Process creation
                self._analyze_process_creation(event, analysis)
            elif event_id == 3:  # Network connection
                self._analyze_network_connection(event, analysis)
            elif event_id == 11:  # File create
                self._analyze_file_operation(event, analysis)
            elif event_id in [12, 13, 14]:  # Registry events
                self._analyze_registry_operation(event, analysis)
        
        return analysis
    
    def _analyze_process_creation(self, event: Dict, analysis: Dict):
        """Analyze process creation event"""
        message = event.get("Message", "")
        # Extract process information from message
        # This is a simplified implementation
        if "Image:" in message:
            lines = message.split('\n')
            for line in lines:
                if line.startswith("Image:"):
                    image = line.split(":", 1)[1].strip()
                    if image not in analysis["processes"]:
                        analysis["processes"][image] = 0
                    analysis["processes"][image] += 1
                    break
    
    def _analyze_network_connection(self, event: Dict, analysis: Dict):
        """Analyze network connection event"""
        message = event.get("Message", "")
        # Extract network information
        connection_info = {"timestamp": event.get("TimeCreated"), "details": message}
        analysis["network_connections"].append(connection_info)
    
    def _analyze_file_operation(self, event: Dict, analysis: Dict):
        """Analyze file operation event"""
        message = event.get("Message", "")
        file_info = {"timestamp": event.get("TimeCreated"), "details": message}
        analysis["file_operations"].append(file_info)
    
    def _analyze_registry_operation(self, event: Dict, analysis: Dict):
        """Analyze registry operation event"""
        message = event.get("Message", "")
        registry_info = {"timestamp": event.get("TimeCreated"), "details": message}
        analysis["registry_operations"].append(registry_info)

    def _parse_detailed_event(self, event: Dict) -> Dict[str, Any]:
        """解析详细的Sysmon事件信息"""
        try:
            event_id = event.get("Id", 0)
            message = event.get("Message", "")
            time_created = event.get("TimeCreated", "")

            # 解析消息中的键值对
            parsed_fields = self._parse_sysmon_message(message)

            detailed_event = {
                "event_id": event_id,
                "timestamp": time_created,
                "level": event.get("LevelDisplayName", ""),
                "raw_message": message,
                "parsed_fields": parsed_fields
            }

            # 根据事件类型添加特定信息
            if event_id == 1:  # Process Creation
                detailed_event.update({
                    "event_type": "Process Creation",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "command_line": parsed_fields.get("CommandLine", ""),
                    "parent_image": parsed_fields.get("ParentImage", ""),
                    "parent_process_id": parsed_fields.get("ParentProcessId", ""),
                    "user": parsed_fields.get("User", "")
                })
            elif event_id == 3:  # Network Connection
                detailed_event.update({
                    "event_type": "Network Connection",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "protocol": parsed_fields.get("Protocol", ""),
                    "source_ip": parsed_fields.get("SourceIp", ""),
                    "source_port": parsed_fields.get("SourcePort", ""),
                    "destination_ip": parsed_fields.get("DestinationIp", ""),
                    "destination_port": parsed_fields.get("DestinationPort", ""),
                    "user": parsed_fields.get("User", "")
                })
            elif event_id == 5:  # Process Terminated
                detailed_event.update({
                    "event_type": "Process Terminated",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "user": parsed_fields.get("User", "")
                })
            elif event_id == 7:  # Image Loaded
                detailed_event.update({
                    "event_type": "Image Loaded",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "image_loaded": parsed_fields.get("ImageLoaded", ""),
                    "signed": parsed_fields.get("Signed", ""),
                    "signature": parsed_fields.get("Signature", "")
                })
            elif event_id == 10:  # Process Access
                detailed_event.update({
                    "event_type": "Process Access",
                    "source_process_guid": parsed_fields.get("SourceProcessGuid", ""),
                    "source_process_id": parsed_fields.get("SourceProcessId", ""),
                    "source_image": parsed_fields.get("SourceImage", ""),
                    "target_process_guid": parsed_fields.get("TargetProcessGuid", ""),
                    "target_process_id": parsed_fields.get("TargetProcessId", ""),
                    "target_image": parsed_fields.get("TargetImage", ""),
                    "granted_access": parsed_fields.get("GrantedAccess", ""),
                    "call_trace": parsed_fields.get("CallTrace", "")
                })
            elif event_id == 11:  # File Create
                detailed_event.update({
                    "event_type": "File Create",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "target_filename": parsed_fields.get("TargetFilename", ""),
                    "creation_utc_time": parsed_fields.get("CreationUtcTime", "")
                })
            elif event_id == 22:  # DNS Query
                detailed_event.update({
                    "event_type": "DNS Query",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "query_name": parsed_fields.get("QueryName", ""),
                    "query_status": parsed_fields.get("QueryStatus", ""),
                    "query_results": parsed_fields.get("QueryResults", "")
                })
            elif event_id == 23:  # File Delete
                detailed_event.update({
                    "event_type": "File Delete",
                    "process_guid": parsed_fields.get("ProcessGuid", ""),
                    "process_id": parsed_fields.get("ProcessId", ""),
                    "image": parsed_fields.get("Image", ""),
                    "target_filename": parsed_fields.get("TargetFilename", ""),
                    "archived": parsed_fields.get("Archived", "")
                })

            return detailed_event

        except Exception as e:
            logger.warning(f"Error parsing detailed event: {str(e)}")
            return None

    def _parse_sysmon_message(self, message: str) -> Dict[str, str]:
        """解析Sysmon消息中的键值对"""
        parsed = {}
        try:
            lines = message.split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line and not line.startswith('RuleName'):
                    # 分割键值对
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        parsed[key] = value
        except Exception as e:
            logger.warning(f"Error parsing Sysmon message: {str(e)}")

        return parsed
    
    async def _generate_report(
        self, 
        analysis_id: str, 
        sample_hash: str, 
        sample_path: str,
        events: List[Dict], 
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate final analysis report"""
        report = {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "sample_info": {
                "hash": sample_hash,
                "path": sample_path,
                "size": os.path.getsize(sample_path) if os.path.exists(sample_path) else 0
            },
            "sysmon_analysis": analysis,
            "raw_events_count": len(events),
            "analysis_engine": "sysmon",
            "configuration": {
                "config_type": self.settings.sysmon_analysis.config_type,
                "vm_name": self.settings.sysmon_analysis.vm.name,
                "timeout": self.settings.sysmon_analysis.analysis_settings.post_execution_delay
            }
        }
        
        # Save raw events if configured
        if self.settings.sysmon_analysis.output_settings.save_raw_events:
            report["raw_events"] = events
        
        return report
    
    async def _ensure_vm_stopped(self, vm_name: str):
        """Ensure VM is stopped"""
        try:
            status_info = await self.vm_controller.get_status(vm_name)
            power_state = status_info.get("power_state", "unknown").lower()
            
            if power_state in ['running', 'paused', 'stuck']:
                logger.info(f"Stopping VM: {vm_name}")
                await self.vm_controller.power_off(vm_name)
                await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"Error ensuring VM stopped: {str(e)}")
    
    async def _cleanup_vm(self, vm_name: str, vm_config: Any):
        """Cleanup VM after analysis"""
        logger.info(f"Cleaning up VM: {vm_name}")
        try:
            # Always stop/sleep the VM after analysis
            logger.info(f"Stopping VM {vm_name} after analysis")
            await self._ensure_vm_stopped(vm_name)

            # Optionally restore snapshot for next use
            if self.settings.task_settings.cleanup_after_analysis:
                logger.info("Restoring baseline snapshot for cleanup")
                success = await self.vm_controller.revert_snapshot(vm_name, vm_config.baseline_snapshot)
                if success:
                    logger.info(f"Successfully restored baseline snapshot for {vm_name}")
                else:
                    logger.warning(f"Failed to restore baseline snapshot for {vm_name}")

            logger.info(f"VM {vm_name} cleanup completed - VM is now stopped/sleeping")

        except Exception as e:
            logger.error(f"VM cleanup failed: {str(e)}")
            # Ensure VM is stopped even if other cleanup fails
            try:
                await self._ensure_vm_stopped(vm_name)
                logger.info(f"VM {vm_name} forced to stop after cleanup error")
            except Exception as stop_error:
                logger.error(f"Failed to force stop VM {vm_name}: {str(stop_error)}")


# Global instance
sysmon_engine = SysmonAnalysisEngine()


async def get_sysmon_engine() -> SysmonAnalysisEngine:
    """Get initialized Sysmon analysis engine"""
    await sysmon_engine.initialize()
    return sysmon_engine
