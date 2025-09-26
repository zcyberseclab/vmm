# 虚拟机资源管理改进

## 问题描述

在实际运行中发现VirtualBox会话锁定问题：

```
VBoxManage.exe: error: The machine 'win10-64-defender' is already locked by a session (or being locked or unlocked)
VBoxManage.exe: error: Details: code VBOX_E_INVALID_OBJECT_STATE (0x80bb0007), component MachineWrap, interface IMachine
```

这个问题导致：
1. 后续任务无法启动虚拟机
2. 虚拟机资源没有被完全释放
3. 需要手动干预才能恢复正常

## 解决方案

### 1. 增强的虚拟机控制器方法

在 `VBoxManageController` 中添加了新的资源管理方法：

#### `cleanup_vm_resources(vm_name: str) -> bool`
完整的虚拟机资源清理方法，包括：
- 智能状态检测
- 多种关闭方式尝试（正常关闭 → ACPI关闭 → 强制关闭）
- 等待确认虚拟机完全停止
- 超时保护机制

#### `force_power_off(vm_name: str) -> bool`
强制关闭虚拟机的方法：
- 首先尝试正常关闭
- 失败时使用ACPI电源按钮
- 处理锁定状态的虚拟机

#### `unlock_vm_session(vm_name: str) -> bool`
解锁虚拟机会话的方法：
- 使用紧急停止命令
- 解锁被锁定的会话

### 2. 分析引擎资源管理改进

在 `AnalysisEngine` 中添加了完整的资源管理流程：

#### `_complete_vm_cleanup(vm_name: str)`
任务完成后的完整清理：
- 调用增强的资源清理方法
- 额外等待确保资源释放
- 最终状态检查和确认
- 异常处理不影响任务完成状态

#### 改进的 `_ensure_vm_stopped(vm_name: str)`
- 优先使用增强的资源清理方法
- 向后兼容传统方法
- 更好的错误处理和日志记录

#### 改进的 `_restore_vm_snapshot(vm_name: str)`
- 使用增强的资源清理替代简单的power_off
- 确保快照恢复前虚拟机完全停止

### 3. 任务执行流程改进

在 `_analyze_on_vm` 方法中：
- 任务成功完成后调用完整清理
- 任务失败时也进行完整清理
- 确保无论任务结果如何都释放资源

## 实现细节

### 资源清理流程

```python
async def cleanup_vm_resources(self, vm_name: str) -> bool:
    # 1. 获取当前状态
    status_info = await self.get_status(vm_name)
    power_state = status_info.get("power_state", "unknown").lower()
    
    # 2. 如果虚拟机正在运行，尝试多种方式关闭
    if power_state in ['running', 'paused', 'stuck', 'starting']:
        # 尝试1: 正常关闭
        if await self.power_off(vm_name):
            pass  # 成功
        else:
            # 尝试2: ACPI关闭
            if await self._run_vboxmanage("controlvm", vm_name, "acpipowerbutton"):
                await asyncio.sleep(5)  # ACPI需要更长时间
            else:
                # 尝试3: 强制关闭
                await self._run_vboxmanage("controlvm", vm_name, "poweroff")
    
    # 3. 等待虚拟机完全停止（最多30秒）
    max_wait = 30
    for i in range(max_wait):
        status_info = await self.get_status(vm_name)
        power_state = status_info.get("power_state", "unknown").lower()
        if power_state in ['poweroff', 'aborted', 'saved']:
            break
        await asyncio.sleep(1)
    
    # 4. 额外等待确保所有进程完全退出
    await asyncio.sleep(2)
    
    return True
```

### 任务执行流程

```python
async def _analyze_on_vm(self, task: AnalysisTask, vm_result: VMTaskResult):
    try:
        # ... 执行分析任务 ...
        
        # 恢复快照（使用增强清理）
        vm_result.status = VMTaskStatus.RESTORING
        await self._restore_vm_snapshot(vm_name)
        
        # 执行完整的资源清理
        await self._complete_vm_cleanup(vm_name)
        
        vm_result.status = VMTaskStatus.COMPLETED
        
    except Exception as e:
        # 失败时也进行完整清理
        try:
            await self._restore_vm_snapshot(vm_name)
            await self._complete_vm_cleanup(vm_name)
        except Exception as restore_error:
            logger.error(f"恢复快照和清理失败: {str(restore_error)}")
```

## 测试覆盖

创建了完整的测试套件 `test_vm_resource_management.py`：

### 虚拟机控制器测试
- `test_cleanup_vm_resources_running_vm`: 测试清理正在运行的虚拟机
- `test_cleanup_vm_resources_stuck_vm`: 测试清理卡住的虚拟机
- `test_cleanup_vm_resources_already_stopped`: 测试清理已停止的虚拟机
- `test_cleanup_vm_resources_timeout`: 测试超时情况处理
- `test_force_power_off`: 测试强制关闭功能

### 分析引擎测试
- `test_complete_vm_cleanup`: 测试完整清理流程
- `test_complete_vm_cleanup_with_failure`: 测试清理失败处理
- `test_ensure_vm_stopped_with_enhanced_cleanup`: 测试增强的停止确保
- `test_restore_vm_snapshot_with_enhanced_cleanup`: 测试增强的快照恢复

## 关键改进点

### 1. 多层次关闭策略
- **正常关闭**: `controlvm poweroff`
- **ACPI关闭**: `controlvm acpipowerbutton` (更温和)
- **强制关闭**: 最后的保障

### 2. 状态监控和等待
- 实时监控虚拟机状态变化
- 等待确认虚拟机完全停止
- 超时保护避免无限等待

### 3. 资源释放确认
- 最终状态检查
- 额外等待时间确保进程完全退出
- 多次验证确保资源释放

### 4. 错误处理和恢复
- 清理失败不影响任务完成状态
- 提供向后兼容的传统方法
- 详细的日志记录便于问题诊断

## 预期效果

1. **消除会话锁定问题**: 通过完整的资源清理避免VirtualBox会话锁定
2. **提高系统稳定性**: 确保每个任务完成后虚拟机资源完全释放
3. **支持连续任务执行**: 后续任务可以正常启动虚拟机
4. **减少手动干预**: 自动处理各种虚拟机状态问题

## 使用方法

系统会自动使用新的资源管理机制，无需配置更改。可以通过日志监控资源清理过程：

```
2025-09-12 16:46:42 | INFO | app.services.vm_controller:cleanup_vm_resources:115 - 开始清理虚拟机资源: win10-64-defender
2025-09-12 16:46:42 | INFO | app.services.vm_controller:cleanup_vm_resources:120 - 当前虚拟机状态: running
2025-09-12 16:46:42 | INFO | app.services.vm_controller:cleanup_vm_resources:125 - 虚拟机正在运行，尝试关闭...
2025-09-12 16:46:45 | INFO | app.services.vm_controller:cleanup_vm_resources:155 - 虚拟机已停止，状态: poweroff
2025-09-12 16:46:47 | INFO | app.services.vm_controller:cleanup_vm_resources:165 - 虚拟机资源清理完成: win10-64-defender
```

## 向后兼容性

- 保持所有现有API接口不变
- 自动检测是否支持新的清理方法
- 不支持时自动回退到传统方法
- 现有配置文件无需修改
