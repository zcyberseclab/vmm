#!/usr/bin/env python3
"""
Multi-Architecture Support Test Script

This script tests the multi-architecture capabilities of the VMM sandbox system.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.services.linux.multi_arch import ArchManager, SUPPORTED_ARCHITECTURES
    from app.services.linux.multi_arch.arch_configs import get_arch_config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def test_architecture_detection():
    """Test architecture detection capabilities"""
    print("🔍 Testing Architecture Detection")
    print("=" * 50)
    
    arch_manager = ArchManager()
    
    # Test supported architectures
    supported = arch_manager.get_supported_architectures()
    print(f"Supported architectures: {supported}")
    
    # Test individual architecture support
    for arch_name in SUPPORTED_ARCHITECTURES.keys():
        is_supported = arch_manager.is_architecture_supported(arch_name)
        status = "✅" if is_supported else "❌"
        print(f"{status} {arch_name:10} - {SUPPORTED_ARCHITECTURES[arch_name]['description']}")
    
    print()


def test_qemu_availability():
    """Test QEMU binary availability"""
    print("🖥️  Testing QEMU Availability")
    print("=" * 50)
    
    for arch_name, arch_info in SUPPORTED_ARCHITECTURES.items():
        qemu_binary = arch_info['qemu_binary']
        
        try:
            # Check if binary exists
            result = subprocess.run(
                ['which', qemu_binary], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                # Get version
                version_result = subprocess.run(
                    [qemu_binary, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if version_result.returncode == 0:
                    version = version_result.stdout.split('\n')[0]
                    print(f"✅ {arch_name:10} - {version}")
                else:
                    print(f"⚠️  {arch_name:10} - Binary found but version check failed")
            else:
                print(f"❌ {arch_name:10} - {qemu_binary} not found")
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  {arch_name:10} - Version check timed out")
        except Exception as e:
            print(f"❌ {arch_name:10} - Error: {e}")
    
    print()


def test_architecture_configs():
    """Test architecture-specific configurations"""
    print("⚙️  Testing Architecture Configurations")
    print("=" * 50)
    
    for arch_name in SUPPORTED_ARCHITECTURES.keys():
        try:
            config = get_arch_config(arch_name)
            qemu_config = config.get_qemu_config()
            templates = config.get_vm_templates()
            
            print(f"✅ {arch_name:10} - Config loaded, {len(templates)} templates")
            
        except Exception as e:
            print(f"❌ {arch_name:10} - Config error: {e}")
    
    print()


def test_system_capabilities():
    """Test system virtualization capabilities"""
    print("🔧 Testing System Capabilities")
    print("=" * 50)
    
    arch_manager = ArchManager()
    capabilities = arch_manager.get_system_capabilities()
    
    print(f"Host Architecture: {capabilities['host_architecture']}")
    print(f"KVM Support: {'✅' if capabilities['virtualization_support']['kvm'] else '❌'}")
    print(f"Hardware Acceleration: {'✅' if capabilities['virtualization_support']['hardware_acceleration'] else '❌'}")
    print(f"Nested Virtualization: {'✅' if capabilities['virtualization_support']['nested_virtualization'] else '❌'}")
    
    print("\nQEMU Versions:")
    for arch, version in capabilities['qemu_versions'].items():
        if version != 'not_available':
            print(f"  {arch:10}: {version}")
    
    print()


def test_elf_detection():
    """Test ELF file architecture detection"""
    print("📄 Testing ELF Architecture Detection")
    print("=" * 50)
    
    arch_manager = ArchManager()
    
    # Test with system binaries if available
    test_files = [
        '/bin/ls',
        '/bin/cat', 
        '/usr/bin/python3',
        '/bin/bash'
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            detected_arch = arch_manager.detect_file_architecture(file_path)
            if detected_arch:
                print(f"✅ {file_path:20} - {detected_arch}")
            else:
                print(f"❌ {file_path:20} - Detection failed")
        else:
            print(f"⚠️  {file_path:20} - File not found")
    
    print()


def generate_installation_guide():
    """Generate installation guide for missing architectures"""
    print("📋 Installation Guide for Missing Architectures")
    print("=" * 50)
    
    arch_manager = ArchManager()
    
    missing_archs = []
    for arch_name, arch_info in SUPPORTED_ARCHITECTURES.items():
        if not arch_manager.is_architecture_supported(arch_name):
            missing_archs.append((arch_name, arch_info))
    
    if not missing_archs:
        print("✅ All architectures are supported!")
        return
    
    print("To install missing architecture support, run:")
    print()
    
    # Generate apt-get install command
    packages = set()
    for arch_name, arch_info in missing_archs:
        qemu_binary = arch_info['qemu_binary']
        
        # Map QEMU binaries to package names
        package_map = {
            'qemu-system-x86_64': 'qemu-system-x86',
            'qemu-system-aarch64': 'qemu-system-arm',
            'qemu-system-mips64': 'qemu-system-mips', 
            'qemu-system-mips': 'qemu-system-mips',
            'qemu-system-ppc64': 'qemu-system-ppc'
        }
        
        package = package_map.get(qemu_binary, qemu_binary)
        packages.add(package)
    
    if packages:
        package_list = ' '.join(sorted(packages))
        print(f"sudo apt-get update")
        print(f"sudo apt-get install -y {package_list}")
        print()
        
        # Additional packages
        print("Additional recommended packages:")
        print("sudo apt-get install -y libvirt-daemon-system libvirt-clients")
        print("sudo apt-get install -y qemu-efi-aarch64 qemu-efi-arm")
        print()
        
        # Enable libvirt
        print("Enable and start libvirt:")
        print("sudo systemctl enable libvirtd")
        print("sudo systemctl start libvirtd")
        print()


def main():
    """Main test function"""
    print("🛡️  VMM Multi-Architecture Support Test")
    print("=" * 60)
    print()
    
    # Run all tests
    test_architecture_detection()
    test_qemu_availability()
    test_architecture_configs()
    test_system_capabilities()
    test_elf_detection()
    generate_installation_guide()
    
    # Generate final report
    arch_manager = ArchManager()
    print("📊 Final Report")
    print("=" * 50)
    print(arch_manager.generate_architecture_report())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)
