"""
x86_64 Architecture Configuration

Configuration for Intel/AMD 64-bit architecture analysis
"""

from typing import Dict, List, Any


class X86_64Config:
    """Configuration for x86_64 architecture"""
    
    def __init__(self):
        self.architecture = "x86_64"
        self.description = "Intel/AMD 64-bit"
        self.endianness = "little"
        self.word_size = 64
        
    def get_qemu_config(self) -> Dict[str, Any]:
        """Get QEMU-specific configuration"""
        return {
            'qemu_binary': 'qemu-system-x86_64',
            'machine_types': ['pc-q35-6.2', 'pc-i440fx-6.2', 'microvm'],
            'cpu_models': [
                'host',           # Use host CPU features (KVM only)
                'qemu64',         # Default QEMU CPU
                'Skylake-Client', # Intel Skylake
                'EPYC',          # AMD EPYC
                'Haswell',       # Intel Haswell
                'Broadwell'      # Intel Broadwell
            ],
            'acceleration': ['kvm', 'tcg'],
            'max_memory': 65536,  # 64GB
            'max_vcpus': 32
        }
    
    def get_vm_templates(self) -> List[Dict[str, Any]]:
        """Get predefined VM templates"""
        return [
            {
                'name': 'ubuntu-20.04-x64',
                'os_type': 'linux',
                'os_variant': 'ubuntu20.04',
                'memory': 2048,
                'vcpus': 2,
                'disk_size': '20G',
                'machine': 'pc-q35-6.2',
                'cpu': 'host',
                'network': 'isolated'
            },
            {
                'name': 'centos-8-x64',
                'os_type': 'linux', 
                'os_variant': 'centos8',
                'memory': 2048,
                'vcpus': 2,
                'disk_size': '20G',
                'machine': 'pc-q35-6.2',
                'cpu': 'host',
                'network': 'isolated'
            },
            {
                'name': 'debian-11-x64',
                'os_type': 'linux',
                'os_variant': 'debian11',
                'memory': 1024,
                'vcpus': 1,
                'disk_size': '15G',
                'machine': 'pc-q35-6.2',
                'cpu': 'qemu64',
                'network': 'isolated'
            },
            {
                'name': 'windows-10-x64',
                'os_type': 'windows',
                'os_variant': 'win10',
                'memory': 4096,
                'vcpus': 2,
                'disk_size': '40G',
                'machine': 'pc-q35-6.2',
                'cpu': 'host',
                'network': 'isolated',
                'features': ['acpi', 'apic', 'hyperv']
            }
        ]
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return {
            'syscall_monitoring': {
                'tool': 'auditd',
                'rules_file': '/etc/audit/rules.d/vmm-x86_64.rules',
                'events': [
                    'execve', 'open', 'openat', 'read', 'write',
                    'socket', 'connect', 'bind', 'listen',
                    'mmap', 'mprotect', 'clone', 'fork'
                ]
            },
            'process_monitoring': {
                'tool': 'sysdig',
                'filters': [
                    'proc.name != systemd',
                    'proc.name != kthreadd',
                    'fd.type=file or fd.type=ipv4 or fd.type=ipv6'
                ]
            },
            'network_monitoring': {
                'capture_interface': 'any',
                'protocols': ['tcp', 'udp', 'icmp'],
                'ports': 'all'
            }
        }
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get analysis configuration"""
        return {
            'disassembler': {
                'engine': 'capstone',
                'arch': 'CS_ARCH_X86',
                'mode': 'CS_MODE_64'
            },
            'static_analysis': {
                'tools': ['objdump', 'readelf', 'strings', 'file'],
                'signatures': ['yara', 'clamav'],
                'entropy_analysis': True,
                'packer_detection': True
            },
            'dynamic_analysis': {
                'timeout': 300,  # 5 minutes
                'snapshot_interval': 30,  # 30 seconds
                'memory_dumps': True,
                'network_capture': True
            },
            'emulation': {
                'engine': 'unicorn',
                'timeout': 60,
                'max_instructions': 100000
            }
        }
    
    def get_syscall_table(self) -> Dict[int, str]:
        """Get x86_64 system call table"""
        return {
            0: 'read',
            1: 'write', 
            2: 'open',
            3: 'close',
            4: 'stat',
            5: 'fstat',
            6: 'lstat',
            7: 'poll',
            8: 'lseek',
            9: 'mmap',
            10: 'mprotect',
            11: 'munmap',
            12: 'brk',
            13: 'rt_sigaction',
            14: 'rt_sigprocmask',
            15: 'rt_sigreturn',
            16: 'ioctl',
            17: 'pread64',
            18: 'pwrite64',
            19: 'readv',
            20: 'writev',
            21: 'access',
            22: 'pipe',
            23: 'select',
            24: 'sched_yield',
            25: 'mremap',
            26: 'msync',
            27: 'mincore',
            28: 'madvise',
            29: 'shmget',
            30: 'shmat',
            31: 'shmctl',
            32: 'dup',
            33: 'dup2',
            34: 'pause',
            35: 'nanosleep',
            36: 'getitimer',
            37: 'alarm',
            38: 'setitimer',
            39: 'getpid',
            40: 'sendfile',
            41: 'socket',
            42: 'connect',
            43: 'accept',
            44: 'sendto',
            45: 'recvfrom',
            46: 'sendmsg',
            47: 'recvmsg',
            48: 'shutdown',
            49: 'bind',
            50: 'listen',
            51: 'getsockname',
            52: 'getpeername',
            53: 'socketpair',
            54: 'setsockopt',
            55: 'getsockopt',
            56: 'clone',
            57: 'fork',
            58: 'vfork',
            59: 'execve',
            60: 'exit',
            61: 'wait4',
            62: 'kill',
            63: 'uname',
            # ... more syscalls can be added
        }
    
    def get_register_names(self) -> List[str]:
        """Get x86_64 register names"""
        return [
            # 64-bit general purpose registers
            'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
            'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15',
            
            # 32-bit general purpose registers
            'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp', 'esp',
            'r8d', 'r9d', 'r10d', 'r11d', 'r12d', 'r13d', 'r14d', 'r15d',
            
            # 16-bit general purpose registers
            'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
            'r8w', 'r9w', 'r10w', 'r11w', 'r12w', 'r13w', 'r14w', 'r15w',
            
            # 8-bit general purpose registers
            'al', 'bl', 'cl', 'dl', 'sil', 'dil', 'bpl', 'spl',
            'r8b', 'r9b', 'r10b', 'r11b', 'r12b', 'r13b', 'r14b', 'r15b',
            'ah', 'bh', 'ch', 'dh',
            
            # Special registers
            'rip', 'rflags',
            
            # Segment registers
            'cs', 'ds', 'es', 'fs', 'gs', 'ss',
            
            # Control registers
            'cr0', 'cr2', 'cr3', 'cr4', 'cr8',
            
            # Debug registers
            'dr0', 'dr1', 'dr2', 'dr3', 'dr6', 'dr7',
            
            # XMM registers
            'xmm0', 'xmm1', 'xmm2', 'xmm3', 'xmm4', 'xmm5', 'xmm6', 'xmm7',
            'xmm8', 'xmm9', 'xmm10', 'xmm11', 'xmm12', 'xmm13', 'xmm14', 'xmm15'
        ]
    
    def get_common_malware_patterns(self) -> List[Dict[str, Any]]:
        """Get common x86_64 malware patterns"""
        return [
            {
                'name': 'process_injection',
                'description': 'Process injection techniques',
                'patterns': [
                    'CreateRemoteThread',
                    'WriteProcessMemory',
                    'VirtualAllocEx',
                    'SetThreadContext'
                ]
            },
            {
                'name': 'persistence',
                'description': 'Persistence mechanisms',
                'patterns': [
                    '/etc/crontab',
                    '~/.bashrc',
                    '/etc/systemd/system/',
                    '/etc/init.d/'
                ]
            },
            {
                'name': 'network_communication',
                'description': 'Network communication patterns',
                'patterns': [
                    'socket(AF_INET',
                    'connect(',
                    'send(',
                    'recv('
                ]
            },
            {
                'name': 'file_operations',
                'description': 'Suspicious file operations',
                'patterns': [
                    '/tmp/',
                    '/var/tmp/',
                    'chmod +x',
                    'rm -rf'
                ]
            }
        ]
