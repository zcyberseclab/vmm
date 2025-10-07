# 🏗️ 多架构虚拟机设计方案

## 📋 架构支持概述

VMM沙箱分析系统将支持四种主要CPU架构的恶意软件分析：

| 架构 | 位数 | 主要用途 | QEMU模拟器 |
|------|------|----------|------------|
| **x86/x64** | 32/64位 | PC、服务器恶意软件 | qemu-system-x86_64 |
| **ARM64** | 64位 | 移动设备、IoT恶意软件 | qemu-system-aarch64 |
| **MIPS** | 32/64位 | 路由器、嵌入式设备 | qemu-system-mips64 |
| **PowerPC** | 32/64位 | 服务器、嵌入式系统 | qemu-system-ppc64 |

## 🎯 设计目标

### 核心目标
- 统一的多架构分析接口
- 架构特定的行为监控
- 跨架构的威胁检测能力
- 高效的资源管理和调度

### 技术目标
- QEMU全系统模拟
- 架构特定的Linux发行版支持
- 统一的监控数据格式
- 可扩展的架构插件系统

## 🏗️ 系统架构

### 整体架构图
```
┌─────────────────────────────────────────────────────────────┐
│                    VMM Multi-Arch Controller                │
├─────────────────────────────────────────────────────────────┤
│  Architecture Manager  │  Resource Scheduler  │  API Gateway │
├─────────────────────────────────────────────────────────────┤
│                    libvirt Unified Interface                │
├─────────────────────────────────────────────────────────────┤
│  x86_64 VMs  │  ARM64 VMs  │  MIPS VMs  │  PowerPC VMs     │
│  ┌─────────┐ │ ┌─────────┐ │ ┌────────┐ │ ┌──────────────┐  │
│  │Ubuntu   │ │ │Ubuntu   │ │ │Debian  │ │ │Debian        │  │
│  │CentOS   │ │ │Debian   │ │ │OpenWrt │ │ │Ubuntu        │  │
│  │Debian   │ │ │Alpine   │ │ │Buildroot│ │ │CentOS        │  │
│  └─────────┘ │ └─────────┘ │ └────────┘ │ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 架构特定配置

### x86/x64架构
```yaml
x86_64:
  qemu_binary: "qemu-system-x86_64"
  machine_type: "pc-q35-6.2"
  cpu_model: "host"  # 使用宿主机CPU特性
  acceleration: "kvm"  # 硬件加速
  supported_os:
    - ubuntu-20.04-x64
    - centos-8-x64
    - debian-11-x64
    - windows-10-x64
  memory_range: [1024, 8192]  # MB
  disk_formats: ["qcow2", "raw"]
  network_models: ["virtio-net", "e1000"]
```

### ARM64架构
```yaml
aarch64:
  qemu_binary: "qemu-system-aarch64"
  machine_type: "virt-6.2"
  cpu_model: "cortex-a72"
  acceleration: "tcg"  # 软件模拟
  firmware: "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
  supported_os:
    - ubuntu-20.04-arm64
    - debian-11-arm64
    - alpine-3.15-arm64
    - android-arm64
  memory_range: [512, 4096]  # MB
  disk_formats: ["qcow2"]
  network_models: ["virtio-net"]
```

### MIPS架构
```yaml
mips64:
  qemu_binary: "qemu-system-mips64"
  machine_type: "malta"
  cpu_model: "MIPS64R2-generic"
  acceleration: "tcg"
  supported_os:
    - debian-11-mips64
    - openwrt-mips
    - buildroot-mips64
  memory_range: [256, 2048]  # MB
  disk_formats: ["qcow2"]
  network_models: ["pcnet"]
  
mips:
  qemu_binary: "qemu-system-mips"
  machine_type: "malta"
  cpu_model: "24Kf"
  acceleration: "tcg"
  supported_os:
    - openwrt-mips
    - buildroot-mips
  memory_range: [128, 1024]  # MB
```

### PowerPC架构
```yaml
ppc64:
  qemu_binary: "qemu-system-ppc64"
  machine_type: "pseries"
  cpu_model: "power9_v2.0"
  acceleration: "tcg"
  supported_os:
    - debian-11-ppc64el
    - ubuntu-20.04-ppc64el
    - centos-8-ppc64le
  memory_range: [512, 4096]  # MB
  disk_formats: ["qcow2"]
  network_models: ["virtio-net"]
```

## 📁 代码结构设计

```
app/services/linux/
├── __init__.py
├── multi_arch/
│   ├── __init__.py
│   ├── arch_manager.py          # 架构管理器
│   ├── qemu_controller.py       # QEMU控制器
│   ├── arch_configs/
│   │   ├── x86_64_config.py     # x86_64配置
│   │   ├── aarch64_config.py    # ARM64配置
│   │   ├── mips_config.py       # MIPS配置
│   │   └── ppc64_config.py      # PowerPC配置
│   ├── vm_templates/
│   │   ├── x86_64/              # x86_64虚拟机模板
│   │   ├── aarch64/             # ARM64虚拟机模板
│   │   ├── mips/                # MIPS虚拟机模板
│   │   └── ppc64/               # PowerPC虚拟机模板
│   └── monitors/
│       ├── x86_monitor.py       # x86特定监控
│       ├── arm_monitor.py       # ARM特定监控
│       ├── mips_monitor.py      # MIPS特定监控
│       └── ppc_monitor.py       # PowerPC特定监控
├── analyzers/
│   ├── elf_analyzer.py          # 通用ELF分析
│   ├── arch_specific/
│   │   ├── x86_analyzer.py      # x86指令分析
│   │   ├── arm_analyzer.py      # ARM指令分析
│   │   ├── mips_analyzer.py     # MIPS指令分析
│   │   └── ppc_analyzer.py      # PowerPC指令分析
│   └── cross_arch/
│       ├── signature_matcher.py # 跨架构签名匹配
│       └── behavior_correlator.py # 行为关联分析
```

## 🔍 架构检测和分析

### ELF文件架构检测
```python
def detect_architecture(elf_file: str) -> str:
    """检测ELF文件的目标架构"""
    arch_mapping = {
        'EM_X86_64': 'x86_64',
        'EM_386': 'x86',
        'EM_AARCH64': 'aarch64',
        'EM_ARM': 'arm',
        'EM_MIPS': 'mips',
        'EM_PPC64': 'ppc64',
        'EM_PPC': 'ppc'
    }
    
    with open(elf_file, 'rb') as f:
        elffile = ELFFile(f)
        machine = elffile.header['e_machine']
        return arch_mapping.get(machine, 'unknown')
```

### 架构特定分析器
```python
class ArchSpecificAnalyzer:
    """架构特定分析器基类"""
    
    def __init__(self, architecture: str):
        self.architecture = architecture
        self.disassembler = self._get_disassembler()
    
    def _get_disassembler(self):
        """获取架构特定的反汇编器"""
        arch_map = {
            'x86_64': capstone.CS_ARCH_X86,
            'aarch64': capstone.CS_ARCH_ARM64,
            'mips': capstone.CS_ARCH_MIPS,
            'ppc64': capstone.CS_ARCH_PPC
        }
        return capstone.Cs(arch_map[self.architecture])
    
    def analyze_instructions(self, code: bytes) -> List[Dict]:
        """分析指令序列"""
        instructions = []
        for insn in self.disassembler.disasm(code, 0x1000):
            instructions.append({
                'address': insn.address,
                'mnemonic': insn.mnemonic,
                'operands': insn.op_str,
                'bytes': insn.bytes
            })
        return instructions
```

## 🖥️ 虚拟机模板管理

### 模板配置示例
```yaml
# templates/aarch64/ubuntu-20.04-arm64.yaml
name: "ubuntu-20.04-arm64"
architecture: "aarch64"
os_type: "linux"
os_variant: "ubuntu20.04"

hardware:
  memory: 2048
  vcpus: 2
  machine: "virt-6.2"
  cpu: "cortex-a72"
  
storage:
  - type: "file"
    format: "qcow2"
    size: "20G"
    path: "/var/lib/libvirt/images/ubuntu-20.04-arm64.qcow2"

network:
  - type: "network"
    source: "isolated-arm64"
    model: "virtio"

firmware:
  loader: "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
  nvram_template: "/usr/share/qemu-efi-aarch64/QEMU_VARS.fd"

monitoring:
  agents:
    - "qemu-guest-agent"
    - "auditd"
  syscall_trace: true
  network_capture: true
```

## 🔧 QEMU命令生成

### 架构特定QEMU命令
```python
class QEMUCommandBuilder:
    """QEMU命令构建器"""
    
    def build_command(self, vm_config: Dict, architecture: str) -> List[str]:
        """构建架构特定的QEMU命令"""
        
        base_cmd = [self._get_qemu_binary(architecture)]
        
        # 通用参数
        base_cmd.extend([
            "-name", vm_config['name'],
            "-m", str(vm_config['memory']),
            "-smp", str(vm_config['vcpus']),
            "-machine", vm_config['machine'],
            "-cpu", vm_config['cpu']
        ])
        
        # 架构特定参数
        if architecture == "aarch64":
            base_cmd.extend([
                "-bios", vm_config['firmware']['loader'],
                "-device", "virtio-gpu-pci",
                "-device", "nec-usb-xhci",
                "-device", "usb-kbd",
                "-device", "usb-mouse"
            ])
        elif architecture == "mips64":
            base_cmd.extend([
                "-device", "piix3-ide,id=ide",
                "-device", "pcnet,netdev=net0",
                "-netdev", "user,id=net0"
            ])
        elif architecture == "ppc64":
            base_cmd.extend([
                "-device", "spapr-vscsi,id=scsi0",
                "-device", "virtio-net-pci,netdev=net0",
                "-netdev", "user,id=net0"
            ])
        
        return base_cmd
```

## 📊 监控数据统一化

### 跨架构事件格式
```python
class UnifiedEvent:
    """统一的跨架构事件格式"""
    
    def __init__(self):
        self.timestamp: float
        self.architecture: str
        self.event_type: str
        self.process_info: Dict
        self.syscall_info: Dict
        self.file_info: Dict
        self.network_info: Dict
        self.raw_data: Dict
    
    def normalize_syscall(self, raw_syscall: Dict) -> Dict:
        """标准化系统调用信息"""
        # 不同架构的系统调用号映射
        syscall_map = {
            'x86_64': X86_64_SYSCALLS,
            'aarch64': ARM64_SYSCALLS,
            'mips64': MIPS64_SYSCALLS,
            'ppc64': PPC64_SYSCALLS
        }
        
        syscall_table = syscall_map.get(self.architecture, {})
        syscall_name = syscall_table.get(raw_syscall['number'], 'unknown')
        
        return {
            'name': syscall_name,
            'number': raw_syscall['number'],
            'args': raw_syscall['args'],
            'return_value': raw_syscall['ret'],
            'architecture': self.architecture
        }
```

## 🚀 部署和管理

### 多架构环境准备
```bash
#!/bin/bash
# setup_multi_arch.sh

# 安装QEMU多架构支持
sudo apt-get update
sudo apt-get install -y \
    qemu-system-x86 \
    qemu-system-arm \
    qemu-system-mips \
    qemu-system-ppc \
    qemu-efi-aarch64 \
    qemu-efi-arm \
    libvirt-daemon-system \
    libvirt-clients

# 启用libvirt服务
sudo systemctl enable libvirtd
sudo systemctl start libvirtd

# 创建架构特定的网络
virsh net-define networks/isolated-x86.xml
virsh net-define networks/isolated-arm64.xml
virsh net-define networks/isolated-mips.xml
virsh net-define networks/isolated-ppc64.xml

# 启动网络
virsh net-start isolated-x86
virsh net-start isolated-arm64
virsh net-start isolated-mips
virsh net-start isolated-ppc64
```

## 📈 性能优化

### 架构特定优化
- **x86_64**: 使用KVM硬件加速
- **ARM64**: 优化TCG翻译缓存
- **MIPS**: 减少内存占用
- **PowerPC**: 优化I/O性能

### 资源调度策略
- 根据架构复杂度分配CPU时间
- 动态调整内存分配
- 优先级队列管理
- 负载均衡算法

这个多架构设计方案为VMM沙箱提供了全面的跨架构恶意软件分析能力！
