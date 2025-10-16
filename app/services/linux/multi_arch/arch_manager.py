"""
Multi-Architecture Manager for VMM Sandbox Analysis System

This module manages multiple CPU architectures and provides a unified interface
for analyzing malware across different platforms.
"""

import os
import subprocess
import shutil
import platform
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from elftools.elf.elffile import ELFFile
from loguru import logger

from app.core.config import get_settings
# 架构映射配置
SUPPORTED_ARCHITECTURES = {
    'x86_64': {
        'qemu_binary': 'qemu-system-x86_64',
        'machine': 'pc-q35-6.2',
        'cpu': 'qemu64',
        'acceleration': 'tcg',
        'description': 'x86_64 (AMD64) - 主流桌面和服务器架构',
        'iso_file': 'alpine-x86_64.iso',
        'vnc_port': 5901
    },
    'aarch64': {
        'qemu_binary': 'qemu-system-aarch64',
        'machine': 'virt',
        'cpu': 'cortex-a72',
        'acceleration': 'tcg',
        'description': 'ARM64 - IoT和移动设备架构',
        'iso_file': 'alpine-arm64.iso',
        'vnc_port': 5902
    },
    'mips64': {
        'qemu_binary': 'qemu-system-mips64',
        'machine': 'malta',
        'cpu': 'MIPS64R2-generic',
        'acceleration': 'tcg',
        'description': 'MIPS64 - 路由器和嵌入式设备',
        'iso_file': 'alpine-mips64.iso',
        'vnc_port': 5903
    },
    'mips': {
        'qemu_binary': 'qemu-system-mips',
        'machine': 'malta',
        'cpu': 'mips32r2-generic',
        'acceleration': 'tcg',
        'description': 'MIPS32 - 路由器和嵌入式设备',
        'iso_file': 'alpine-mips.iso',
        'vnc_port': 5904
    },
    'ppc64': {
        'qemu_binary': 'qemu-system-ppc64',
        'machine': 'pseries',
        'cpu': 'power8',
        'acceleration': 'tcg',
        'description': 'PowerPC64 - IBM服务器架构',
        'iso_file': 'alpine-ppc64.iso',
        'vnc_port': 5905
    }
}

# ELF架构映射 (ELF machine type -> 我们的架构名称)
ELF_ARCH_MAPPING = {
    0x3E: 'x86_64',      # EM_X86_64
    0xB7: 'aarch64',     # EM_AARCH64
    0x08: 'mips',        # EM_MIPS
    0x15: 'ppc64',       # EM_PPC64
    0x28: 'arm',         # EM_ARM (32-bit ARM)
}

# 条件导入 - Windows上不需要libvirt
try:
    from .qemu_controller import QEMUController
except ImportError as e:
    logger.warning(f"QEMUController import failed: {e}")
    QEMUController = None


class ArchManager:
    """Multi-architecture management system"""

    def __init__(self):
        self.settings = get_settings()
        self.qemu_controller = QEMUController() if QEMUController else None
        self.available_architectures: Dict[str, bool] = {}
        self.vm_templates: Dict[str, List[str]] = {}
        self.is_windows = platform.system() == "Windows"

        # Load QEMU configuration from settings
        self._load_qemu_config()

        self._check_architecture_support()

    def _load_qemu_config(self):
        """Load QEMU configuration from settings"""
        try:
            # Get Linux behavioral analysis configuration
            linux_config = getattr(self.settings, 'linux', {})
            behavioral_config = linux_config.get('behavioral_analysis', {})

            # Get QEMU defaults from virtualization section
            virt_config = getattr(self.settings, 'virtualization', {})
            qemu_config = virt_config.get('qemu', {})

            # Load VM configurations
            self.vm_configs = {}
            vms = behavioral_config.get('vms', [])

            for vm_config in vms:
                arch = vm_config.get('architecture')
                if arch:
                    self.vm_configs[arch] = vm_config
                    # Update SUPPORTED_ARCHITECTURES with VM config
                    if arch in SUPPORTED_ARCHITECTURES:
                        SUPPORTED_ARCHITECTURES[arch].update({
                            'qemu_binary': vm_config.get('qemu_binary'),
                            'machine': vm_config.get('machine'),
                            'cpu': vm_config.get('cpu'),
                            'acceleration': vm_config.get('acceleration', 'tcg'),
                            'iso_file': vm_config.get('iso_file'),
                            'vnc_port': vm_config.get('vnc_port'),
                            'description': vm_config.get('description')
                        })
                        logger.debug(f"Updated {arch} configuration from Linux VMs")

            # Load default settings
            self.qemu_defaults = {
                'default_memory': qemu_config.get('default_memory', '512'),
                'default_smp': qemu_config.get('default_smp', '1'),
                'default_display': qemu_config.get('default_display', 'vnc'),
                'vnc_base_port': qemu_config.get('vnc_base_port', 5900),
                'vm_images_dir': qemu_config.get('vm_images_dir', './vm_images')
            }

            # Load analysis settings
            self.analysis_settings = behavioral_config.get('analysis_settings', {})

            logger.info(f"Loaded configuration for {len(self.vm_configs)} Linux VMs")

        except Exception as e:
            logger.warning(f"Failed to load QEMU config: {e}, using defaults")
            self.vm_configs = {}
            self.qemu_defaults = {
                'default_memory': '512',
                'default_smp': '1',
                'default_display': 'vnc',
                'vnc_base_port': 5900,
                'vm_images_dir': './vm_images'
            }
            self.analysis_settings = {}

    def _check_architecture_support(self):
        """Check which architectures are supported on this system"""
        logger.info("Checking multi-architecture support...")

        for arch_name, arch_info in SUPPORTED_ARCHITECTURES.items():
            qemu_binary = arch_info['qemu_binary']

            # Windows上QEMU二进制文件有.exe扩展名
            if self.is_windows and not qemu_binary.endswith('.exe'):
                qemu_binary += '.exe'

            # Check if QEMU binary exists
            if shutil.which(qemu_binary):
                self.available_architectures[arch_name] = True
                logger.info(f"✅ {arch_name} support available ({qemu_binary})")
            else:
                self.available_architectures[arch_name] = False
                logger.warning(f"❌ {arch_name} support missing ({qemu_binary} not found)")

        # 如果在Windows上没有找到QEMU，检查WSL2
        if self.is_windows and not any(self.available_architectures.values()):
            self._check_wsl2_qemu()

        # Log summary
        available_count = sum(self.available_architectures.values())
        total_count = len(SUPPORTED_ARCHITECTURES)
        logger.info(f"Architecture support: {available_count}/{total_count} available")
    
    def _check_wsl2_qemu(self):
        """Check QEMU availability in WSL2"""
        try:
            # 检查WSL2是否可用
            result = subprocess.run(['wsl', '--list', '--verbose'],
                                  capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and 'Ubuntu' in result.stdout:
                logger.info("WSL2 detected, checking QEMU in WSL...")

                # 在WSL中检查QEMU
                for arch_name, arch_info in SUPPORTED_ARCHITECTURES.items():
                    qemu_binary = arch_info['qemu_binary']

                    wsl_result = subprocess.run(
                        ['wsl', 'which', qemu_binary],
                        capture_output=True, text=True, timeout=5
                    )

                    if wsl_result.returncode == 0:
                        self.available_architectures[arch_name] = True
                        logger.info(f"✅ {arch_name} available in WSL2")

        except Exception as e:
            logger.warning(f"WSL2 check failed: {e}")

    def get_supported_architectures(self) -> List[str]:
        """Get list of supported architectures"""
        return [arch for arch, available in self.available_architectures.items() if available]
    
    def is_architecture_supported(self, architecture: str) -> bool:
        """Check if specific architecture is supported"""
        return self.available_architectures.get(architecture, False)
    
    def detect_file_architecture(self, file_path: str) -> Optional[str]:
        """Detect the target architecture of an ELF file"""
        try:
            with open(file_path, 'rb') as f:
                # Check if it's an ELF file
                magic = f.read(4)
                if magic != b'\x7fELF':
                    logger.warning(f"File {file_path} is not an ELF file")
                    return None
                
                # Reset and parse ELF
                f.seek(0)
                elffile = ELFFile(f)
                
                # Get machine type
                machine = elffile.header['e_machine']
                architecture = ELF_ARCH_MAPPING.get(machine)
                
                if architecture:
                    logger.info(f"Detected architecture: {architecture} for {file_path}")
                    return architecture
                else:
                    logger.warning(f"Unknown architecture (machine type: 0x{machine:02x}) for {file_path}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to detect architecture for {file_path}: {e}")
            return None
    
    def get_architecture_info(self, architecture: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an architecture"""
        if architecture not in SUPPORTED_ARCHITECTURES:
            return None
        
        arch_info = SUPPORTED_ARCHITECTURES[architecture].copy()
        arch_info['available'] = self.available_architectures.get(architecture, False)
        arch_info['vm_templates'] = self.vm_templates.get(architecture, [])
        
        return arch_info
    
    def create_vm_for_architecture(self, architecture: str, vm_name: str, config: Dict[str, Any]) -> bool:
        """Create a virtual machine for specific architecture"""
        if not self.is_architecture_supported(architecture):
            logger.error(f"Architecture {architecture} is not supported")
            return False
        
        try:
            # Get architecture-specific configuration
            arch_info = SUPPORTED_ARCHITECTURES[architecture]
            
            # Merge with user config
            vm_config = {
                'name': vm_name,
                'architecture': architecture,
                'qemu_binary': arch_info['qemu_binary'],
                'acceleration': arch_info['acceleration'],
                **config
            }
            
            # Create VM using QEMU controller
            success = self.qemu_controller.create_vm(vm_config)
            
            if success:
                logger.info(f"Created {architecture} VM: {vm_name}")
                # Add to templates list
                if architecture not in self.vm_templates:
                    self.vm_templates[architecture] = []
                self.vm_templates[architecture].append(vm_name)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to create {architecture} VM {vm_name}: {e}")
            return False
    
    def get_optimal_vm_for_file(self, file_path: str) -> Optional[Tuple[str, str]]:
        """Get optimal VM architecture and template for analyzing a file"""
        # Detect file architecture
        file_arch = self.detect_file_architecture(file_path)
        if not file_arch:
            return None

        # Check if we support this architecture
        if not self.is_architecture_supported(file_arch):
            logger.warning(f"File architecture {file_arch} is not supported")
            return None

        # Get available VMs for this architecture
        available_vms = self.vm_templates.get(file_arch, [])
        if not available_vms:
            logger.warning(f"No VMs available for architecture {file_arch}")
            return None

        # For now, return the first available VM
        # TODO: Implement more sophisticated VM selection logic
        selected_vm = available_vms[0]
        logger.info(f"Selected VM {selected_vm} ({file_arch}) for file {file_path}")

        return file_arch, selected_vm

    def build_qemu_command(self, architecture: str, vm_name: str = None,
                          memory: str = None, smp: str = None) -> List[str]:
        """构建正确的QEMU命令"""
        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ValueError(f"不支持的架构: {architecture}")

        arch_config = SUPPORTED_ARCHITECTURES[architecture]

        # 使用配置的默认值
        memory = memory or self.qemu_defaults.get('default_memory', '512')
        smp = smp or self.qemu_defaults.get('default_smp', '1')

        # 基础命令
        cmd = [arch_config['qemu_binary']]

        # VM名称
        if vm_name:
            cmd.extend(['-name', vm_name])
        else:
            cmd.extend(['-name', f'vmm-{architecture}'])

        # 内存和CPU
        cmd.extend(['-m', memory])
        cmd.extend(['-smp', smp])

        # 架构特定配置
        if 'machine' in arch_config:
            cmd.extend(['-machine', arch_config['machine']])

        if 'cpu' in arch_config:
            cmd.extend(['-cpu', arch_config['cpu']])

        # 加速器
        cmd.extend(['-accel', arch_config['acceleration']])

        # ISO文件 (如果存在)
        iso_path = f"vm_images/{arch_config['iso_file']}"
        if os.path.exists(iso_path):
            cmd.extend(['-cdrom', iso_path])

        # VNC显示
        vnc_port = arch_config.get('vnc_port', 5901)
        vnc_display = vnc_port - 5900  # VNC显示号
        cmd.extend(['-vnc', f':{vnc_display}'])

        # 监控接口
        cmd.extend(['-monitor', 'stdio'])

        return cmd

    def get_vm_info(self, architecture: str) -> Dict[str, Any]:
        """获取VM信息"""
        if architecture not in SUPPORTED_ARCHITECTURES:
            return {}

        arch_config = SUPPORTED_ARCHITECTURES[architecture]
        iso_path = f"vm_images/{arch_config['iso_file']}"

        return {
            'architecture': architecture,
            'qemu_binary': arch_config['qemu_binary'],
            'machine': arch_config.get('machine', 'default'),
            'cpu': arch_config.get('cpu', 'default'),
            'description': arch_config['description'],
            'iso_file': arch_config['iso_file'],
            'iso_exists': os.path.exists(iso_path),
            'iso_size_mb': os.path.getsize(iso_path) / (1024*1024) if os.path.exists(iso_path) else 0,
            'vnc_port': arch_config.get('vnc_port', 5901),
            'available': self.available_architectures.get(architecture, False)
        }
    
    def analyze_file_cross_architecture(self, file_path: str) -> Dict[str, Any]:
        """Analyze a file and determine cross-architecture compatibility"""
        analysis_result = {
            'file_path': file_path,
            'primary_architecture': None,
            'compatible_architectures': [],
            'analysis_recommendations': []
        }
        
        # Detect primary architecture
        primary_arch = self.detect_file_architecture(file_path)
        if primary_arch:
            analysis_result['primary_architecture'] = primary_arch
            
            # Check if primary architecture is supported
            if self.is_architecture_supported(primary_arch):
                analysis_result['compatible_architectures'].append(primary_arch)
                analysis_result['analysis_recommendations'].append(
                    f"Analyze on native {primary_arch} environment"
                )
            else:
                analysis_result['analysis_recommendations'].append(
                    f"Primary architecture {primary_arch} not supported - consider emulation"
                )
        
        # Check for cross-architecture analysis opportunities
        # For example, some ARM binaries might run on x86_64 with emulation
        if primary_arch in ['arm', 'aarch64'] and self.is_architecture_supported('x86_64'):
            analysis_result['compatible_architectures'].append('x86_64')
            analysis_result['analysis_recommendations'].append(
                "Consider x86_64 analysis with ARM emulation"
            )
        
        return analysis_result
    
    def get_system_capabilities(self) -> Dict[str, Any]:
        """Get comprehensive system capabilities for multi-architecture analysis"""
        capabilities = {
            'host_architecture': self._get_host_architecture(),
            'virtualization_support': self._check_virtualization_support(),
            'available_architectures': self.available_architectures,
            'qemu_versions': self._get_qemu_versions(),
            'total_vms': sum(len(vms) for vms in self.vm_templates.values()),
            'architecture_distribution': {
                arch: len(vms) for arch, vms in self.vm_templates.items()
            }
        }
        
        return capabilities
    
    def _get_host_architecture(self) -> str:
        """Get host system architecture"""
        try:
            if self.is_windows:
                # Windows上使用platform模块
                return platform.machine()
            else:
                result = subprocess.run(['uname', '-m'], capture_output=True, text=True)
                return result.stdout.strip()
        except Exception:
            return 'unknown'
    
    def _check_virtualization_support(self) -> Dict[str, bool]:
        """Check virtualization support capabilities"""
        support = {
            'kvm': False,
            'nested_virtualization': False,
            'hardware_acceleration': False
        }

        if self.is_windows:
            # Windows上检查Hyper-V和WHPX
            try:
                # 检查Hyper-V
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All | Select-Object State'],
                    capture_output=True, text=True, timeout=10
                )
                support['hyperv'] = 'Enabled' in result.stdout

                # 检查WHPX (Windows Hypervisor Platform)
                whpx_result = subprocess.run(
                    ['powershell', '-Command', 'Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform | Select-Object State'],
                    capture_output=True, text=True, timeout=10
                )
                support['whpx'] = 'Enabled' in whpx_result.stdout
                support['hardware_acceleration'] = support.get('whpx', False) or support.get('hyperv', False)

            except Exception as e:
                logger.warning(f"Failed to check Windows virtualization features: {e}")
        else:
            # Linux上检查KVM
            support['kvm'] = os.path.exists('/dev/kvm')

            # Check for nested virtualization
            try:
                with open('/sys/module/kvm_intel/parameters/nested', 'r') as f:
                    support['nested_virtualization'] = f.read().strip() == 'Y'
            except FileNotFoundError:
                try:
                    with open('/sys/module/kvm_amd/parameters/nested', 'r') as f:
                        support['nested_virtualization'] = f.read().strip() == '1'
                except FileNotFoundError:
                    pass

            # Check hardware acceleration
            support['hardware_acceleration'] = support['kvm']

        return support
    
    def _get_qemu_versions(self) -> Dict[str, str]:
        """Get versions of available QEMU binaries"""
        versions = {}
        
        for arch_name, arch_info in SUPPORTED_ARCHITECTURES.items():
            qemu_binary = arch_info['qemu_binary']
            
            try:
                result = subprocess.run(
                    [qemu_binary, '--version'], 
                    capture_output=True, 
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Extract version from output
                    version_line = result.stdout.split('\n')[0]
                    versions[arch_name] = version_line
                else:
                    versions[arch_name] = 'unknown'
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                versions[arch_name] = 'not_available'
        
        return versions
    
    def generate_architecture_report(self) -> str:
        """Generate a comprehensive architecture support report"""
        capabilities = self.get_system_capabilities()
        
        report = []
        report.append("=== VMM Multi-Architecture Support Report ===\n")
        
        # Host information
        report.append(f"Host Architecture: {capabilities['host_architecture']}")
        report.append(f"KVM Support: {'✅' if capabilities['virtualization_support']['kvm'] else '❌'}")
        report.append(f"Hardware Acceleration: {'✅' if capabilities['virtualization_support']['hardware_acceleration'] else '❌'}")
        report.append("")
        
        # Architecture support
        report.append("Architecture Support:")
        for arch_name, available in self.available_architectures.items():
            arch_info = SUPPORTED_ARCHITECTURES[arch_name]
            status = "✅" if available else "❌"
            vm_count = len(self.vm_templates.get(arch_name, []))
            report.append(f"  {status} {arch_name:10} ({arch_info['description']}) - {vm_count} VMs")
        
        report.append("")
        
        # QEMU versions
        report.append("QEMU Versions:")
        for arch_name, version in capabilities['qemu_versions'].items():
            if version != 'not_available':
                report.append(f"  {arch_name:10}: {version}")
        
        return "\n".join(report)


# Utility functions

def install_architecture_support(architecture: str) -> bool:
    """Install support for a specific architecture"""
    if architecture not in SUPPORTED_ARCHITECTURES:
        logger.error(f"Unknown architecture: {architecture}")
        return False
    
    arch_info = SUPPORTED_ARCHITECTURES[architecture]
    qemu_binary = arch_info['qemu_binary']
    
    # Check if already installed
    if shutil.which(qemu_binary):
        logger.info(f"Architecture {architecture} already supported")
        return True
    
    # Attempt to install via package manager
    package_map = {
        'qemu-system-x86_64': 'qemu-system-x86',
        'qemu-system-aarch64': 'qemu-system-arm', 
        'qemu-system-mips64': 'qemu-system-mips',
        'qemu-system-mips': 'qemu-system-mips',
        'qemu-system-ppc64': 'qemu-system-ppc'
    }
    
    package_name = package_map.get(qemu_binary, qemu_binary)
    
    try:
        logger.info(f"Installing {package_name}...")
        result = subprocess.run(
            ['sudo', 'apt-get', 'install', '-y', package_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully installed {architecture} support")
            return True
        else:
            logger.error(f"Failed to install {architecture} support: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error installing {architecture} support: {e}")
        return False
