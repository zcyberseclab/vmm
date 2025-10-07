"""
KVM Virtual Machine Controller for Linux Analysis

This module provides KVM/QEMU virtual machine management capabilities
for Linux malware analysis in isolated environments.
"""

import os
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from pathlib import Path
import libvirt
from loguru import logger

from app.core.config import get_settings


class KVMController:
    """KVM virtual machine controller for Linux analysis"""
    
    def __init__(self):
        self.settings = get_settings()
        self.connection: Optional[libvirt.virConnect] = None
        self.domains: Dict[str, libvirt.virDomain] = {}
        
    def connect(self) -> bool:
        """Connect to KVM hypervisor"""
        try:
            # Connect to local KVM
            self.connection = libvirt.open('qemu:///system')
            if self.connection is None:
                logger.error("Failed to connect to KVM hypervisor")
                return False
            
            logger.info(f"Connected to KVM hypervisor: {self.connection.getHostname()}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"KVM connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from KVM hypervisor"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from KVM hypervisor")
    
    def list_domains(self) -> List[str]:
        """List all available domains"""
        if not self.connection:
            return []
        
        try:
            domain_names = []
            # Get running domains
            for domain_id in self.connection.listDomainsID():
                domain = self.connection.lookupByID(domain_id)
                domain_names.append(domain.name())
            
            # Get inactive domains
            for domain_name in self.connection.listDefinedDomains():
                domain_names.append(domain_name)
            
            return domain_names
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to list domains: {e}")
            return []
    
    def get_domain(self, name: str) -> Optional[libvirt.virDomain]:
        """Get domain by name"""
        if not self.connection:
            return None
        
        try:
            if name in self.domains:
                return self.domains[name]
            
            domain = self.connection.lookupByName(name)
            self.domains[name] = domain
            return domain
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get domain {name}: {e}")
            return None
    
    def start_domain(self, name: str) -> bool:
        """Start a domain"""
        domain = self.get_domain(name)
        if not domain:
            return False
        
        try:
            if domain.isActive():
                logger.info(f"Domain {name} is already running")
                return True
            
            domain.create()
            logger.info(f"Started domain: {name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to start domain {name}: {e}")
            return False
    
    def stop_domain(self, name: str, force: bool = False) -> bool:
        """Stop a domain"""
        domain = self.get_domain(name)
        if not domain:
            return False
        
        try:
            if not domain.isActive():
                logger.info(f"Domain {name} is already stopped")
                return True
            
            if force:
                domain.destroy()  # Force stop
            else:
                domain.shutdown()  # Graceful shutdown
            
            logger.info(f"Stopped domain: {name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to stop domain {name}: {e}")
            return False
    
    def revert_to_snapshot(self, domain_name: str, snapshot_name: str) -> bool:
        """Revert domain to snapshot"""
        domain = self.get_domain(domain_name)
        if not domain:
            return False
        
        try:
            snapshot = domain.snapshotLookupByName(snapshot_name)
            domain.revertToSnapshot(snapshot)
            logger.info(f"Reverted {domain_name} to snapshot {snapshot_name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to revert {domain_name} to snapshot {snapshot_name}: {e}")
            return False
    
    def create_snapshot(self, domain_name: str, snapshot_name: str, description: str = "") -> bool:
        """Create domain snapshot"""
        domain = self.get_domain(domain_name)
        if not domain:
            return False
        
        try:
            # Create snapshot XML
            snapshot_xml = f"""
            <domainsnapshot>
                <name>{snapshot_name}</name>
                <description>{description}</description>
            </domainsnapshot>
            """
            
            domain.snapshotCreateXML(snapshot_xml)
            logger.info(f"Created snapshot {snapshot_name} for {domain_name}")
            return True
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to create snapshot {snapshot_name} for {domain_name}: {e}")
            return False
    
    def get_domain_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get domain information"""
        domain = self.get_domain(name)
        if not domain:
            return None
        
        try:
            info = domain.info()
            return {
                'name': domain.name(),
                'uuid': domain.UUIDString(),
                'state': info[0],
                'max_memory': info[1],
                'memory': info[2],
                'vcpus': info[3],
                'cpu_time': info[4],
                'active': domain.isActive()
            }
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get info for domain {name}: {e}")
            return None
    
    def execute_command(self, domain_name: str, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute command in domain via guest agent"""
        domain = self.get_domain(domain_name)
        if not domain:
            return {'success': False, 'error': 'Domain not found'}
        
        try:
            # This requires QEMU guest agent to be installed and running
            # in the guest VM
            result = domain.qemuAgentCommand(
                f'{{"execute": "guest-exec", "arguments": {{"path": "/bin/sh", "arg": ["-c", "{command}"]}}}}',
                timeout,
                0
            )
            
            logger.info(f"Executed command in {domain_name}: {command}")
            return {'success': True, 'result': result}
            
        except libvirt.libvirtError as e:
            logger.error(f"Failed to execute command in {domain_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def copy_file_to_domain(self, domain_name: str, local_path: str, remote_path: str) -> bool:
        """Copy file to domain"""
        # This would typically use guest agent or SSH
        # For now, we'll use a placeholder implementation
        logger.warning("copy_file_to_domain not fully implemented yet")
        return False
    
    def copy_file_from_domain(self, domain_name: str, remote_path: str, local_path: str) -> bool:
        """Copy file from domain"""
        # This would typically use guest agent or SSH
        # For now, we'll use a placeholder implementation
        logger.warning("copy_file_from_domain not fully implemented yet")
        return False
    
    def get_network_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """Get domain network information"""
        domain = self.get_domain(domain_name)
        if not domain:
            return None
        
        try:
            # Get domain XML to parse network interfaces
            xml_desc = domain.XMLDesc()
            root = ET.fromstring(xml_desc)
            
            interfaces = []
            for interface in root.findall('.//interface'):
                iface_info = {
                    'type': interface.get('type'),
                    'mac': interface.find('mac').get('address') if interface.find('mac') is not None else None,
                    'source': interface.find('source').get('network') if interface.find('source') is not None else None
                }
                interfaces.append(iface_info)
            
            return {'interfaces': interfaces}
            
        except (libvirt.libvirtError, ET.ParseError) as e:
            logger.error(f"Failed to get network info for {domain_name}: {e}")
            return None
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Utility functions
def check_kvm_support() -> bool:
    """Check if KVM is supported and available"""
    try:
        # Check if KVM module is loaded
        with open('/proc/modules', 'r') as f:
            modules = f.read()
            if 'kvm' not in modules:
                return False
        
        # Check if /dev/kvm exists
        return os.path.exists('/dev/kvm')
        
    except Exception as e:
        logger.error(f"Failed to check KVM support: {e}")
        return False


def get_libvirt_version() -> Optional[str]:
    """Get libvirt version"""
    try:
        version = libvirt.getVersion()
        return f"{version // 1000000}.{(version % 1000000) // 1000}.{version % 1000}"
    except Exception as e:
        logger.error(f"Failed to get libvirt version: {e}")
        return None
