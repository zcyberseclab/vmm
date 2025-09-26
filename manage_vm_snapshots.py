#!/usr/bin/env python3
"""
VirtualBox虚拟机快照管理脚本
用于EDR样本分析系统的快照操作
"""
import asyncio
import sys
import os
import subprocess
import time
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vm_controller import VBoxManageController


async def list_snapshots(vm_name: str):
    """列出虚拟机的所有快照"""
    print(f"虚拟机快照列表: {vm_name}")
    print("=" * 50)
    
    try:
        controller = VBoxManageController()
        
        # 列出快照
        cmd = [controller.vboxmanage_path, "snapshot", vm_name, "list"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            if result.stdout.strip():
                print("✓ 快照列表:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f"  {line}")
                return True
            else:
                print("✓ 未找到快照")
                return True
        else:
            print(f"✗ 获取快照列表失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ 列出快照失败: {str(e)}")
        return False


async def create_snapshot(vm_name: str, snapshot_name: str, description: str = ""):
    """创建快照"""
    print(f"创建快照: {snapshot_name}")
    print("=" * 30)
    
    try:
        controller = VBoxManageController()
        
        # 1. 检查虚拟机状态
        print(f"1. 检查虚拟机状态...")
        status = await controller.get_status(vm_name)
        
        if "error" in status:
            print(f"✗ 虚拟机不存在: {status['error']}")
            return False
        
        current_state = status.get('power_state', '').lower()
        print(f"✓ 当前状态: {current_state}")
        
        # 2. 如果虚拟机正在运行，询问是否关闭
        if current_state not in ['poweroff', 'aborted', 'saved']:
            choice = input("虚拟机正在运行，是否关闭后创建快照？(Y/n): ").strip().lower()
            
            if choice != 'n':
                print("关闭虚拟机...")
                success = await controller.power_off(vm_name)
                if success:
                    print("✓ 虚拟机已关闭")
                    await asyncio.sleep(3)
                else:
                    print("✗ 虚拟机关闭失败")
                    return False
            else:
                print("在运行状态下创建快照...")
        
        # 3. 创建快照
        print(f"2. 创建快照: {snapshot_name}")
        
        if not description:
            description = f"Snapshot created at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        cmd = [
            controller.vboxmanage_path, "snapshot", vm_name, "take", snapshot_name,
            "--description", description
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✓ 快照创建成功")
            return True
        else:
            print(f"✗ 快照创建失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 快照创建超时")
        return False
    except Exception as e:
        print(f"✗ 创建快照失败: {str(e)}")
        return False


async def restore_snapshot(vm_name: str, snapshot_name: str):
    """恢复快照"""
    print(f"恢复快照: {snapshot_name}")
    print("=" * 30)
    
    try:
        controller = VBoxManageController()
        
        # 1. 检查虚拟机状态
        print(f"1. 检查虚拟机状态...")
        status = await controller.get_status(vm_name)
        
        if "error" in status:
            print(f"✗ 虚拟机不存在: {status['error']}")
            return False
        
        current_state = status.get('power_state', '').lower()
        print(f"✓ 当前状态: {current_state}")
        
        # 2. 如果虚拟机正在运行，先关闭
        if current_state not in ['poweroff', 'aborted', 'saved']:
            print("关闭虚拟机...")
            success = await controller.power_off(vm_name)
            if success:
                print("✓ 虚拟机已关闭")
                await asyncio.sleep(3)
            else:
                print("✗ 虚拟机关闭失败")
                return False
        
        # 3. 恢复快照
        print(f"2. 恢复快照...")
        success = await controller.revert_snapshot(vm_name, snapshot_name)
        
        if success:
            print("✓ 快照恢复成功")
            return True
        else:
            print("✗ 快照恢复失败")
            return False
            
    except Exception as e:
        print(f"✗ 恢复快照失败: {str(e)}")
        return False


async def delete_snapshot(vm_name: str, snapshot_name: str):
    """删除快照"""
    print(f"删除快照: {snapshot_name}")
    print("=" * 30)
    
    try:
        controller = VBoxManageController()
        
        # 确认删除
        choice = input(f"确认删除快照 '{snapshot_name}'？(y/N): ").strip().lower()
        
        if choice != 'y':
            print("删除操作已取消")
            return False
        
        # 删除快照
        cmd = [controller.vboxmanage_path, "snapshot", vm_name, "delete", snapshot_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✓ 快照删除成功")
            return True
        else:
            print(f"✗ 快照删除失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 快照删除超时")
        return False
    except Exception as e:
        print(f"✗ 删除快照失败: {str(e)}")
        return False


async def test_snapshot_workflow(vm_name: str):
    """测试完整的快照工作流程"""
    print(f"测试快照工作流程: {vm_name}")
    print("=" * 50)
    
    try:
        # 1. 列出现有快照
        print("1. 列出现有快照...")
        await list_snapshots(vm_name)
        
        # 2. 创建测试快照
        test_snapshot = f"test_workflow_{int(time.time())}"
        print(f"\n2. 创建测试快照: {test_snapshot}")
        
        success = await create_snapshot(vm_name, test_snapshot, "Test workflow snapshot")
        if not success:
            return False
        
        # 3. 启动虚拟机
        print(f"\n3. 启动虚拟机...")
        controller = VBoxManageController()
        success = await controller.power_on(vm_name)
        
        if success:
            print("✓ 虚拟机启动成功")
            print("等待虚拟机完全启动...")
            await asyncio.sleep(15)
        else:
            print("✗ 虚拟机启动失败")
            return False
        
        # 4. 模拟一些操作（等待）
        print(f"\n4. 模拟样本分析过程...")
        print("虚拟机正在运行，模拟EDR分析...")
        await asyncio.sleep(10)
        
        # 5. 恢复快照
        print(f"\n5. 恢复到清洁状态...")
        success = await restore_snapshot(vm_name, test_snapshot)
        
        if not success:
            return False
        
        # 6. 再次启动验证
        print(f"\n6. 验证恢复结果...")
        success = await controller.power_on(vm_name)
        
        if success:
            print("✓ 快照恢复后虚拟机启动成功")
            await asyncio.sleep(10)
            
            # 关闭虚拟机
            await controller.power_off(vm_name)
            print("✓ 虚拟机已关闭")
        else:
            print("✗ 快照恢复后虚拟机启动失败")
        
        # 7. 清理测试快照
        print(f"\n7. 清理测试快照...")
        await delete_snapshot(vm_name, test_snapshot)
        
        print(f"\n✅ 快照工作流程测试完成！")
        return True
        
    except Exception as e:
        print(f"✗ 快照工作流程测试失败: {str(e)}")
        return False


async def main():
    """主函数"""
    print("VirtualBox快照管理工具")
    print("=" * 50)
    
    # 获取虚拟机列表
    try:
        controller = VBoxManageController()
        cmd = [controller.vboxmanage_path, "list", "vms"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0 or not result.stdout.strip():
            print("✗ 未找到虚拟机")
            return
        
        # 显示虚拟机列表
        print("可用的虚拟机:")
        vms = []
        for line in result.stdout.strip().split('\n'):
            if '"' in line:
                vm_name = line.split('"')[1]
                vms.append(vm_name)
                print(f"  {len(vms)}. {vm_name}")
        
        if not vms:
            print("✗ 未找到虚拟机")
            return
        
        # 选择虚拟机
        if len(vms) == 1:
            selected_vm = vms[0]
            print(f"\n自动选择虚拟机: {selected_vm}")
        else:
            while True:
                try:
                    choice = input(f"\n请选择虚拟机 (1-{len(vms)}): ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(vms):
                        selected_vm = vms[int(choice) - 1]
                        break
                    else:
                        print("无效选择，请重试")
                except KeyboardInterrupt:
                    print("\n操作已取消")
                    return
        
        # 显示操作菜单
        while True:
            print(f"\n快照管理菜单 - {selected_vm}")
            print("=" * 40)
            print("1. 列出快照")
            print("2. 创建快照")
            print("3. 恢复快照")
            print("4. 删除快照")
            print("5. 测试快照工作流程")
            print("6. 退出")
            
            try:
                choice = input("\n请选择操作 (1-6): ").strip()
                
                if choice == '1':
                    await list_snapshots(selected_vm)
                
                elif choice == '2':
                    snapshot_name = input("输入快照名称: ").strip()
                    if snapshot_name:
                        description = input("输入快照描述 (可选): ").strip()
                        await create_snapshot(selected_vm, snapshot_name, description)
                    else:
                        print("快照名称不能为空")
                
                elif choice == '3':
                    # 先列出快照
                    await list_snapshots(selected_vm)
                    snapshot_name = input("输入要恢复的快照名称: ").strip()
                    if snapshot_name:
                        await restore_snapshot(selected_vm, snapshot_name)
                    else:
                        print("快照名称不能为空")
                
                elif choice == '4':
                    # 先列出快照
                    await list_snapshots(selected_vm)
                    snapshot_name = input("输入要删除的快照名称: ").strip()
                    if snapshot_name:
                        await delete_snapshot(selected_vm, snapshot_name)
                    else:
                        print("快照名称不能为空")
                
                elif choice == '5':
                    await test_snapshot_workflow(selected_vm)
                
                elif choice == '6':
                    print("退出快照管理工具")
                    break
                
                else:
                    print("无效选择，请重试")
                    
            except KeyboardInterrupt:
                print("\n操作已取消")
                break
        
    except Exception as e:
        print(f"\n❌ 快照管理过程中发生异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
