"""
QEMU Multi-Architecture Controller

This module provides QEMU-based virtual machine control for multiple architectures
including x86_64, ARM64, MIPS, and PowerPC.

Note: This module works on both Windows and Linux, with platform-specific optimizations.
"""

import os
import subprocess
import json
import time
import socket
import platform
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.core.config import get_settings


class QEMUController:
    """QEMU virtual machine controller for multi-architecture support"""

    def __init__(self):
        self.settings = get_settings()
        self.running_vms: Dict[str, Dict[str, Any]] = {}
        self.qmp_connections: Dict[str, socket.socket] = {}
        self.is_windows = platform.system() == "Windows"
    
    def create_vm(self, vm_config: Dict[str, Any]) -> bool:
        """Create a virtual machine with architecture-specific configuration"""
        vm_name = vm_config['name']
        architecture = vm_config['architecture']
        
        try:
            # Build QEMU command
            qemu_cmd = self._build_qemu_command(vm_config)
            
            # Start VM process
            if self.is_windows:
                # Windows上不使用preexec_fn
                process = subprocess.Popen(
                    qemu_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Linux上使用preexec_fn
                process = subprocess.Popen(
                    qemu_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Create new process group
                )
            
            # Store VM information
            self.running_vms[vm_name] = {
                'process': process,
                'config': vm_config,
                'architecture': architecture,
                'start_time': time.time(),
                'status': 'starting'
            }
            
            # Wait a moment and check if process is still running
            time.sleep(2)
            if process.poll() is None:
                self.running_vms[vm_name]['status'] = 'running'
                return True
            else:
                # Process died, get error output
                stdout, stderr = process.communicate()
                raise Exception(f"QEMU process died: {stderr.decode()}")
                
        except Exception as e:
            if vm_name in self.running_vms:
                del self.running_vms[vm_name]
            raise Exception(f"Failed to create VM {vm_name}: {e}")
    
    def _build_qemu_command(self, vm_config: Dict[str, Any]) -> List[str]:
        """Build QEMU command line for specific architecture"""
        architecture = vm_config['architecture']

        # Base command - Windows上添加.exe扩展名
        qemu_binary = vm_config.get('qemu_binary', f'qemu-system-{architecture}')
        if self.is_windows and not qemu_binary.endswith('.exe'):
            qemu_binary += '.exe'

        cmd = [qemu_binary]
        
        # Common parameters
        cmd.extend([
            '-name', vm_config['name'],
            '-m', str(vm_config.get('memory', 1024)),
            '-smp', str(vm_config.get('vcpus', 1)),
            '-machine', vm_config.get('machine', self._get_default_machine(architecture)),
            '-cpu', vm_config.get('cpu', self._get_default_cpu(architecture))
        ])
        
        # Acceleration
        if self.is_windows:
            # Windows上使用WHPX或TCG
            if architecture == 'x86_64':
                # 使用正确的QEMU语法
                cmd.extend(['-accel', 'whpx'])
            else:
                cmd.extend(['-accel', 'tcg'])
        else:
            # Linux上使用KVM或TCG
            acceleration = vm_config.get('acceleration', 'tcg')
            if acceleration == 'kvm' and os.path.exists('/dev/kvm'):
                cmd.extend(['-accel', 'kvm'])
            else:
                cmd.extend(['-accel', 'tcg'])
        
        # Architecture-specific configuration
        cmd.extend(self._get_arch_specific_params(architecture, vm_config))
        
        # Storage
        if 'disk' in vm_config:
            cmd.extend(['-drive', f"file={vm_config['disk']},format=qcow2"])
        
        # Network
        network_config = vm_config.get('network', 'user')
        if network_config == 'user':
            cmd.extend(['-netdev', 'user,id=net0'])
        elif network_config == 'bridge':
            cmd.extend(['-netdev', 'bridge,id=net0,br=virbr0'])
        
        # Add network device
        cmd.extend(['-device', self._get_network_device(architecture)])
        
        # Monitor and management
        if self.is_windows:
            # Windows上使用TCP端口而不是Unix socket
            qmp_port = 4444 + hash(vm_config['name']) % 1000  # 生成唯一端口
            cmd.extend(['-qmp', f'tcp:localhost:{qmp_port},server,nowait'])
        else:
            # Linux上使用Unix socket
            qmp_socket = f"/tmp/qmp-{vm_config['name']}.sock"
            cmd.extend(['-qmp', f'unix:{qmp_socket},server,nowait'])
        
        # VNC display (for debugging)
        cmd.extend(['-vnc', ':1'])
        
        # No graphics by default
        cmd.extend(['-nographic'])
        
        return cmd
    
    def _get_default_machine(self, architecture: str) -> str:
        """Get default machine type for architecture"""
        machine_map = {
            'x86_64': 'pc-q35-6.2',
            'aarch64': 'virt-6.2',
            'mips64': 'malta',
            'mips': 'malta',
            'ppc64': 'pseries'
        }
        return machine_map.get(architecture, 'pc')
    
    def _get_default_cpu(self, architecture: str) -> str:
        """Get default CPU model for architecture"""
        cpu_map = {
            'x86_64': 'qemu64',
            'aarch64': 'cortex-a72',
            'mips64': 'MIPS64R2-generic',
            'mips': '24Kf',
            'ppc64': 'power9_v2.0'
        }
        return cpu_map.get(architecture, 'qemu64')
    
    def _get_arch_specific_params(self, architecture: str, vm_config: Dict[str, Any]) -> List[str]:
        """Get architecture-specific QEMU parameters"""
        params = []
        
        if architecture == 'aarch64':
            # ARM64 specific parameters
            params.extend([
                '-device', 'virtio-gpu-pci',
                '-device', 'nec-usb-xhci',
                '-device', 'usb-kbd',
                '-device', 'usb-mouse'
            ])
            
            # UEFI firmware if specified
            if 'firmware' in vm_config:
                params.extend(['-bios', vm_config['firmware']])
            
        elif architecture in ['mips64', 'mips']:
            # MIPS specific parameters
            params.extend([
                '-device', 'piix3-ide,id=ide'
            ])
            
        elif architecture == 'ppc64':
            # PowerPC specific parameters
            params.extend([
                '-device', 'spapr-vscsi,id=scsi0'
            ])
        
        return params
    
    def _get_network_device(self, architecture: str) -> str:
        """Get appropriate network device for architecture"""
        device_map = {
            'x86_64': 'virtio-net-pci,netdev=net0',
            'aarch64': 'virtio-net-pci,netdev=net0',
            'mips64': 'pcnet,netdev=net0',
            'mips': 'pcnet,netdev=net0',
            'ppc64': 'virtio-net-pci,netdev=net0'
        }
        return device_map.get(architecture, 'virtio-net-pci,netdev=net0')
    
    def stop_vm(self, vm_name: str, force: bool = False) -> bool:
        """Stop a running virtual machine"""
        if vm_name not in self.running_vms:
            return False
        
        vm_info = self.running_vms[vm_name]
        process = vm_info['process']
        
        try:
            if force:
                # Force kill
                process.kill()
            else:
                # Graceful shutdown via QMP
                if self._send_qmp_command(vm_name, {'execute': 'system_powerdown'}):
                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful shutdown fails
                        process.kill()
                else:
                    # QMP failed, force kill
                    process.kill()
            
            # Clean up
            del self.running_vms[vm_name]
            if vm_name in self.qmp_connections:
                self.qmp_connections[vm_name].close()
                del self.qmp_connections[vm_name]
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to stop VM {vm_name}: {e}")
    
    def get_vm_status(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a virtual machine"""
        if vm_name not in self.running_vms:
            return None
        
        vm_info = self.running_vms[vm_name]
        process = vm_info['process']
        
        # Check if process is still running
        if process.poll() is None:
            status = 'running'
        else:
            status = 'stopped'
            vm_info['status'] = status
        
        return {
            'name': vm_name,
            'status': status,
            'architecture': vm_info['architecture'],
            'start_time': vm_info['start_time'],
            'uptime': time.time() - vm_info['start_time'] if status == 'running' else 0,
            'pid': process.pid if status == 'running' else None
        }
    
    def list_running_vms(self) -> List[Dict[str, Any]]:
        """List all running virtual machines"""
        vms = []
        for vm_name in list(self.running_vms.keys()):
            vm_status = self.get_vm_status(vm_name)
            if vm_status:
                vms.append(vm_status)
        return vms
    
    def _send_qmp_command(self, vm_name: str, command: Dict[str, Any]) -> bool:
        """Send QMP command to virtual machine"""
        try:
            # Connect to QMP socket if not already connected
            if vm_name not in self.qmp_connections:
                qmp_socket = f"/tmp/qmp-{vm_name}.sock"
                if not os.path.exists(qmp_socket):
                    return False
                
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(qmp_socket)
                
                # Read QMP greeting
                greeting = sock.recv(1024)
                
                # Send qmp_capabilities
                capabilities_cmd = json.dumps({'execute': 'qmp_capabilities'}) + '\n'
                sock.send(capabilities_cmd.encode())
                
                # Read response
                response = sock.recv(1024)
                
                self.qmp_connections[vm_name] = sock
            
            # Send command
            sock = self.qmp_connections[vm_name]
            cmd_str = json.dumps(command) + '\n'
            sock.send(cmd_str.encode())
            
            # Read response
            response = sock.recv(1024)
            return True
            
        except Exception:
            return False
    
    def execute_command_in_vm(self, vm_name: str, command: str) -> Dict[str, Any]:
        """Execute command in virtual machine via guest agent"""
        if vm_name not in self.running_vms:
            return {'success': False, 'error': 'VM not found'}
        
        # This would require QEMU guest agent
        # For now, return a placeholder
        return {
            'success': False,
            'error': 'Guest agent execution not implemented yet'
        }
    
    def create_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """Create VM snapshot"""
        if vm_name not in self.running_vms:
            return False
        
        command = {
            'execute': 'blockdev-snapshot-sync',
            'arguments': {
                'device': 'drive0',
                'snapshot-file': f'/tmp/{vm_name}-{snapshot_name}.qcow2'
            }
        }
        
        return self._send_qmp_command(vm_name, command)
    
    def restore_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """Restore VM from snapshot"""
        # This would require stopping the VM and restarting with snapshot
        # Implementation depends on specific requirements
        return False
    
    def get_vm_info(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed VM information"""
        if vm_name not in self.running_vms:
            return None
        
        vm_info = self.running_vms[vm_name]
        status = self.get_vm_status(vm_name)
        
        return {
            **status,
            'config': vm_info['config'],
            'qemu_version': self._get_qemu_version(vm_info['config']['architecture'])
        }
    
    def _get_qemu_version(self, architecture: str) -> str:
        """Get QEMU version for specific architecture"""
        try:
            qemu_binary = f'qemu-system-{architecture}'
            if self.is_windows:
                qemu_binary += '.exe'

            result = subprocess.run(
                [qemu_binary, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.split('\n')[0]
            else:
                return 'unknown'
                
        except Exception:
            return 'unknown'
