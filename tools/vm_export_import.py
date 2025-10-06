#!/usr/bin/env python3
"""
跨平台VirtualBox虚拟机导入导出工具
支持Windows和Linux，包含快照信息
使用方法:
  python vm_export_import.py export --all --dir ./vm_backup
  python vm_export_import.py import --dir ./vm_backup
"""

import os
import sys
import subprocess
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

class VMTool:
    def __init__(self):
        self.vboxmanage = self._find_vboxmanage()
        if not self.vboxmanage:
            print("❌ 未找到VirtualBox，请先安装VirtualBox")
            print("请确保VirtualBox已正确安装并添加到系统PATH中")
            sys.exit(1)
        
        print(f"✅ 找到VirtualBox: {self.vboxmanage}")
        
        # 启用Windows控制台颜色支持
        if os.name == 'nt':
            try:
                os.system('color')  # 启用ANSI颜色支持
            except:
                pass
    
    def _find_vboxmanage(self):
        """查找vboxmanage命令 - 跨平台"""
        # 常见的VirtualBox安装路径
        possible_paths = [
            'vboxmanage',
            'VBoxManage',
            'VBoxManage.exe'
        ]
        
        # Windows特定路径
        if os.name == 'nt':
            possible_paths.extend([
                r'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe',
                r'C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe',
            ])
        
        # Linux特定路径
        else:
            possible_paths.extend([
                '/usr/bin/vboxmanage',
                '/usr/local/bin/vboxmanage'
            ])
        
        # 首先尝试从PATH中查找
        for cmd in ['vboxmanage', 'VBoxManage']:
            if shutil.which(cmd):
                return cmd
        
        # 然后尝试具体路径
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                return path
        
        return None
    
    def run_cmd(self, cmd, capture_output=True, show_output=False):
        """运行命令 - 跨平台兼容"""
        if show_output:
            print(f"🔧 执行: {' '.join(str(c) for c in cmd)}")
        
        try:
            # 确保所有参数都是字符串
            cmd = [str(c) for c in cmd]
            
            result = subprocess.run(
                cmd, 
                capture_output=capture_output, 
                text=True, 
                check=True,
                encoding='utf-8',
                errors='replace'  # 处理编码问题
            )
            
            return result.stdout.strip() if capture_output else True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 命令执行失败: {' '.join(cmd)}")
            if e.stderr:
                print(f"错误: {e.stderr}")
            return None
        except Exception as e:
            print(f"❌ 执行异常: {str(e)}")
            return None
    
    def get_vm_list(self):
        """获取虚拟机列表"""
        print("🔍 获取虚拟机列表...")
        
        output = self.run_cmd([self.vboxmanage, 'list', 'vms'])
        if not output:
            return []
        
        vms = []
        for line in output.split('\n'):
            line = line.strip()
            if line and '{' in line and '}' in line:
                # 解析格式: "VM Name" {UUID}
                try:
                    name_end = line.rfind('" {')
                    if name_end > 0:
                        name = line[1:name_end]  # 去掉首尾引号
                        uuid_start = line.rfind('{') + 1
                        uuid_end = line.rfind('}')
                        uuid = line[uuid_start:uuid_end]
                        vms.append({'name': name, 'uuid': uuid})
                except:
                    continue
        
        return vms
    
    def get_vm_snapshots(self, vm_name):
        """获取虚拟机快照"""
        print(f"🔍 获取 {vm_name} 的快照...")
        
        output = self.run_cmd([self.vboxmanage, 'snapshot', vm_name, 'list'])
        if not output or 'does not have any snapshots' in output.lower():
            return []
        
        snapshots = []
        current_snapshot = None
        
        for line in output.split('\n'):
            line = line.strip()
            if 'Name:' in line:
                # 提取快照名称
                name_start = line.find('Name:') + 5
                name_end = line.find('(UUID:', name_start)
                if name_end == -1:
                    name_end = len(line)
                
                snapshot_name = line[name_start:name_end].strip()
                
                # 提取UUID
                uuid_start = line.find('UUID:')
                if uuid_start != -1:
                    uuid_start += 5
                    uuid_end = line.find(')', uuid_start)
                    if uuid_end == -1:
                        uuid_end = len(line)
                    uuid = line[uuid_start:uuid_end].strip()
                else:
                    uuid = ""
                
                # 检查是否为当前快照
                is_current = '*' in line or 'Current' in line
                
                snapshots.append({
                    'name': snapshot_name,
                    'uuid': uuid,
                    'is_current': is_current
                })
                
                if is_current:
                    current_snapshot = snapshot_name
        
        return snapshots
    
    def export_vm(self, vm_name, export_dir):
        """导出虚拟机"""
        print(f"📦 导出虚拟机: {vm_name}")
        
        # 创建导出目录
        vm_export_dir = Path(export_dir) / vm_name
        vm_export_dir.mkdir(parents=True, exist_ok=True)
        
        # 导出为OVA格式
        ova_path = vm_export_dir / f"{vm_name}.ova"
        print(f"  导出到: {ova_path}")
        
        # 执行导出命令
        success = self.run_cmd([
            self.vboxmanage, 'export', vm_name, 
            '--output', str(ova_path)
        ], capture_output=False, show_output=True)
        
        if not success:
            print(f"❌ 导出失败: {vm_name}")
            return False
        
        # 获取快照信息
        snapshots = self.get_vm_snapshots(vm_name)
        
        # 保存元数据
        metadata = {
            'vm_name': vm_name,
            'export_time': datetime.now().isoformat(),
            'snapshots': snapshots,
            'ova_file': f"{vm_name}.ova",
            'platform': os.name,
            'python_version': sys.version
        }
        
        metadata_path = vm_export_dir / 'vm_info.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ {vm_name} 导出完成")
        print(f"  - OVA文件: {ova_path}")
        print(f"  - 快照数量: {len(snapshots)}")
        
        return True
    
    def export_all(self, export_dir):
        """导出所有虚拟机"""
        print(f"🚀 导出所有虚拟机到: {export_dir}")
        
        # 创建导出目录
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        
        # 获取虚拟机列表
        vms = self.get_vm_list()
        if not vms:
            print("⚠️ 没有找到虚拟机")
            return
        
        print(f"找到 {len(vms)} 个虚拟机")
        
        # 导出每个虚拟机
        success_count = 0
        failed_vms = []
        
        for vm in vms:
            print(f"\n{'='*50}")
            if self.export_vm(vm['name'], export_dir):
                success_count += 1
            else:
                failed_vms.append(vm['name'])
        
        # 创建导出报告
        report = {
            'export_time': datetime.now().isoformat(),
            'total_vms': len(vms),
            'successful_exports': success_count,
            'failed_exports': len(failed_vms),
            'failed_vms': failed_vms,
            'exported_vms': [vm['name'] for vm in vms if vm['name'] not in failed_vms]
        }
        
        report_path = export_path / 'export_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 导出完成!")
        print(f"成功: {success_count}/{len(vms)} 个虚拟机")
        if failed_vms:
            print(f"失败: {', '.join(failed_vms)}")
        print(f"报告: {report_path}")
    
    def import_vm(self, ova_path, new_name=None):
        """导入虚拟机"""
        ova_file = Path(ova_path)
        if not ova_file.exists():
            print(f"❌ OVA文件不存在: {ova_path}")
            return False
        
        print(f"📥 导入虚拟机: {ova_file.name}")
        
        # 构建导入命令
        cmd = [self.vboxmanage, 'import', str(ova_file)]
        
        # 如果指定新名称
        if new_name:
            cmd.extend(['--vsys', '0', '--vmname', new_name])
            print(f"  重命名为: {new_name}")
        
        success = self.run_cmd(cmd, capture_output=False, show_output=True)
        
        if success:
            print(f"✅ 导入成功: {ova_file.name}")
            return True
        else:
            print(f"❌ 导入失败: {ova_file.name}")
            return False
    
    def import_from_dir(self, import_dir):
        """从目录导入所有虚拟机"""
        print(f"🚀 从目录导入: {import_dir}")
        
        import_path = Path(import_dir)
        if not import_path.exists():
            print(f"❌ 目录不存在: {import_dir}")
            return
        
        # 查找所有OVA文件
        ova_files = []
        for pattern in ['*.ova', '**/*.ova']:
            ova_files.extend(import_path.glob(pattern))
        
        if not ova_files:
            print("⚠️ 没有找到OVA文件")
            return
        
        print(f"找到 {len(ova_files)} 个OVA文件")
        
        # 导入每个文件
        success_count = 0
        for ova_file in ova_files:
            print(f"\n{'='*50}")
            if self.import_vm(ova_file):
                success_count += 1
        
        print(f"\n🎉 导入完成!")
        print(f"成功: {success_count}/{len(ova_files)} 个虚拟机")
    
    def list_vms(self):
        """列出虚拟机"""
        print("📋 虚拟机列表:")
        
        vms = self.get_vm_list()
        if not vms:
            print("⚠️ 没有找到虚拟机")
            return
        
        for i, vm in enumerate(vms, 1):
            print(f"\n{i}. {vm['name']}")
            print(f"   UUID: {vm['uuid']}")
            
            # 获取快照信息
            snapshots = self.get_vm_snapshots(vm['name'])
            if snapshots:
                print(f"   快照: {len(snapshots)} 个")
                for snap in snapshots:
                    current_mark = " (当前)" if snap.get('is_current') else ""
                    print(f"     - {snap['name']}{current_mark}")
            else:
                print("   快照: 无")

def main():
    parser = argparse.ArgumentParser(description='VirtualBox虚拟机导入导出工具')
    parser.add_argument('action', choices=['export', 'import', 'list'], 
                       help='操作: export(导出) | import(导入) | list(列表)')
    
    # 导出选项
    parser.add_argument('--all', action='store_true', help='导出所有虚拟机')
    parser.add_argument('--vm', help='指定虚拟机名称')
    
    # 通用选项
    parser.add_argument('--dir', help='导出/导入目录')
    parser.add_argument('--ova', help='OVA文件路径')
    parser.add_argument('--name', help='导入时的新名称')
    
    args = parser.parse_args()
    
    # 创建工具实例
    tool = VMTool()
    
    if args.action == 'list':
        tool.list_vms()
    
    elif args.action == 'export':
        if not args.dir:
            print("❌ 请指定导出目录: --dir")
            sys.exit(1)
        
        if args.all:
            tool.export_all(args.dir)
        elif args.vm:
            tool.export_vm(args.vm, args.dir)
        else:
            print("❌ 请指定 --all 或 --vm")
            sys.exit(1)
    
    elif args.action == 'import':
        if args.ova:
            tool.import_vm(args.ova, args.name)
        elif args.dir:
            tool.import_from_dir(args.dir)
        else:
            print("❌ 请指定 --ova 或 --dir")
            sys.exit(1)

if __name__ == "__main__":
    main()
