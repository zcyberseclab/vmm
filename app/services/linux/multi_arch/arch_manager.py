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
from loguru import logger

# 使用内置ELF解析器，不依赖外部库

from app.core.config import get_settings
# ELF架构映射 (ELF machine type -> 我们的架构名称)
ELF_ARCH_MAPPING = {
    0x3E: 'x86_64',      # EM_X86_64
    0xB7: 'aarch64',     # EM_AARCH64
    0x08: 'mips',        # EM_MIPS
    0x15: 'ppc64',       # EM_PPC64
    0x28: 'arm',         # EM_ARM (32-bit ARM)
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
            linux_config = getattr(self.settings, 'linux', None)
            behavioral_config = {}
            if linux_config and hasattr(linux_config, 'behavioral_analysis'):
                behavioral_config = linux_config.behavioral_analysis.__dict__ if linux_config.behavioral_analysis else {}

            # Get QEMU defaults from virtualization section
            virt_config = getattr(self.settings, 'virtualization', None)
            qemu_config = {}
            if virt_config and hasattr(virt_config, 'qemu'):
                qemu_config = virt_config.qemu.__dict__ if virt_config.qemu else {}

            # Load VM configurations
            self.vm_configs = {}
            vms = behavioral_config.get('vms', [])

            # If behavioral_config is from object, try to get vms attribute
            if not vms and linux_config and hasattr(linux_config, 'behavioral_analysis'):
                behavioral_analysis = linux_config.behavioral_analysis
                if behavioral_analysis and hasattr(behavioral_analysis, 'vms'):
                    vms = behavioral_analysis.vms

            for vm_config in vms:
                # Handle both dict and object VM configs
                if hasattr(vm_config, 'architecture'):
                    arch = vm_config.architecture
                    vm_dict = vm_config.__dict__
                    vm_name = getattr(vm_config, 'name', f'linux-{arch}')
                else:
                    arch = vm_config.get('architecture')
                    vm_dict = vm_config
                    vm_name = vm_config.get('name', f'linux-{arch}')

                if arch:
                    self.vm_configs[arch] = vm_dict
                    # Add to vm_templates
                    if arch not in self.vm_templates:
                        self.vm_templates[arch] = []
                    self.vm_templates[arch].append(vm_name)
                    logger.debug(f"Loaded {arch} configuration from Linux VMs")

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

            # If behavioral_config is from object, try to get analysis_settings attribute
            if not self.analysis_settings and linux_config and hasattr(linux_config, 'behavioral_analysis'):
                behavioral_analysis = linux_config.behavioral_analysis
                if behavioral_analysis and hasattr(behavioral_analysis, 'analysis_settings'):
                    analysis_settings = behavioral_analysis.analysis_settings
                    if analysis_settings:
                        self.analysis_settings = analysis_settings.__dict__ if hasattr(analysis_settings, '__dict__') else {}

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

        # 使用config.yaml中配置的VM来检查架构支持
        for arch_name, vm_config in self.vm_configs.items():
            qemu_binary = vm_config.get('qemu_binary', f'qemu-system-{arch_name}')

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
        total_count = len(self.vm_configs)
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
                for arch_name, vm_config in self.vm_configs.items():
                    qemu_binary = vm_config.get('qemu_binary', f'qemu-system-{arch_name}')

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
            # 使用内置解析器检测ELF架构
            return self._detect_with_builtin_parser(file_path)
        except Exception as e:
            logger.error(f"Failed to detect architecture for {file_path}: {e}")
            return None



    def _detect_with_builtin_parser(self, file_path: str) -> Optional[str]:
        """使用内置解析器检测ELF架构（不依赖外部库）"""
        try:
            with open(file_path, 'rb') as f:
                # 检查ELF魔数
                magic = f.read(4)
                if magic != b'\x7fELF':
                    logger.warning(f"File {file_path} is not an ELF file")
                    return None

                # 读取字节序信息
                f.seek(5)  # EI_DATA字段位置
                endian_byte = f.read(1)[0]
                endianness = 'little' if endian_byte == 1 else 'big'

                # 跳到machine type字段
                f.seek(18)  # e_machine字段位置
                machine_bytes = f.read(2)
                machine = int.from_bytes(machine_bytes, byteorder=endianness)

                architecture = ELF_ARCH_MAPPING.get(machine)
                if architecture:
                    logger.info(f"Detected architecture: {architecture} (machine type: 0x{machine:02x}) for {file_path}")
                    return architecture
                else:
                    logger.warning(f"Unknown architecture (machine type: 0x{machine:02x}) for {file_path}")
                    return None

        except Exception as e:
            logger.error(f"Built-in parser detection failed for {file_path}: {e}")
            return None
    
    def get_architecture_info(self, architecture: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an architecture"""
        if architecture not in self.vm_configs:
            return None

        arch_info = self.vm_configs[architecture].copy()
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
            arch_info = self.vm_configs.get(architecture, {})

            # Merge with user config
            vm_config = {
                'name': vm_name,
                'architecture': architecture,
                'qemu_binary': arch_info.get('qemu_binary', f'qemu-system-{architecture}'),
                'acceleration': arch_info.get('acceleration', 'tcg'),
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

    def analyze_file_compatibility(self, file_path: str) -> Dict[str, Any]:
        """分析文件兼容性"""
        try:
            # 检测文件架构
            detected_arch = self.detect_file_architecture(file_path)

            # 获取文件信息
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 创建分析结果
            analysis_result = {
                'file_path': file_path,
                'file_size': file_size,
                'primary_architecture': detected_arch,
                'compatible_architectures': [],
                'analysis_recommendations': []
            }

            if detected_arch:
                # 检查架构支持
                if self.is_architecture_supported(detected_arch):
                    analysis_result['compatible_architectures'].append(detected_arch)
                    analysis_result['analysis_recommendations'].append(
                        f"文件适合在 {detected_arch} 架构上分析"
                    )
                else:
                    analysis_result['analysis_recommendations'].append(
                        f"主要架构 {detected_arch} 不受支持 - 考虑模拟"
                    )

                # 添加动态分析建议
                analysis_result['analysis_recommendations'].append(
                    "建议进行动态分析以获取行为信息"
                )
            else:
                analysis_result['analysis_recommendations'].append(
                    "无法检测文件架构 - 可能不是有效的ELF文件"
                )

            return analysis_result

        except Exception as e:
            logger.error(f"文件兼容性分析失败: {file_path} - {e}")
            return {
                'file_path': file_path,
                'error': str(e),
                'analysis_recommendations': ['分析失败，请检查文件格式']
            }

    def build_qemu_command(self, architecture: str, vm_name: str = None,
                          memory: str = None, smp: str = None) -> List[str]:
        """构建正确的QEMU命令"""
        if architecture not in self.vm_configs:
            raise ValueError(f"不支持的架构: {architecture}")

        arch_config = self.vm_configs[architecture]

        # 使用配置的默认值
        memory = memory or self.qemu_defaults.get('default_memory', '512')
        smp = smp or self.qemu_defaults.get('default_smp', '1')

        # 基础命令
        cmd = [arch_config.get('qemu_binary', f'qemu-system-{architecture}')]

        # VM名称
        if vm_name:
            cmd.extend(['-name', vm_name])
        else:
            cmd.extend(['-name', f'vmm-{architecture}'])

        # 内存和CPU
        cmd.extend(['-m', memory])
        cmd.extend(['-smp', smp])

        # 架构特定配置
        if arch_config.get('machine'):
            cmd.extend(['-machine', arch_config['machine']])

        if arch_config.get('cpu'):
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
        if architecture not in self.vm_configs:
            return {}

        arch_config = self.vm_configs[architecture]
        iso_path = f"vm_images/{arch_config.get('iso_file', f'{architecture}.iso')}"

        return {
            'architecture': architecture,
            'qemu_binary': arch_config.get('qemu_binary', f'qemu-system-{architecture}'),
            'machine': arch_config.get('machine', 'default'),
            'cpu': arch_config.get('cpu', 'default'),
            'description': arch_config.get('description', f'{architecture} architecture'),
            'iso_file': arch_config.get('iso_file', f'{architecture}.iso'),
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

        for arch_name, vm_config in self.vm_configs.items():
            qemu_binary = vm_config.get('qemu_binary', f'qemu-system-{arch_name}')
            
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
            arch_info = self.vm_configs.get(arch_name, {})
            status = "✅" if available else "❌"
            vm_count = len(self.vm_templates.get(arch_name, []))
            description = arch_info.get('description', f'{arch_name} architecture')
            report.append(f"  {status} {arch_name:10} ({description}) - {vm_count} VMs")
        
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
    # 获取架构管理器实例来检查配置
    arch_manager = ArchManager()

    if architecture not in arch_manager.vm_configs:
        logger.error(f"Unknown architecture: {architecture}")
        return False

    arch_info = arch_manager.vm_configs[architecture]
    qemu_binary = arch_info.get('qemu_binary', f'qemu-system-{architecture}')
    
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
