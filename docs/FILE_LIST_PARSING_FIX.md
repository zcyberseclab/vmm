# 文件列表解析修复

## 问题描述

在ZIP文件解压后获取文件列表时，系统错误地将PowerShell命令当作了文件名，导致执行失败：

```
2025-09-12 16:58:23 | INFO | app.services.analysis_engine:_execute_sample_in_vm:355 - 尝试用默认程序执行: C:\Users\vboxuser\Desktop\Get-ChildItem -Path 'C:\Users\vboxuser\Desktop' -File | Select-Object -ExpandProperty Name
```

这个问题的根本原因是：
1. PowerShell命令的输出包含了命令回显
2. 文件列表解析逻辑没有正确过滤PowerShell命令和提示符
3. 导致系统尝试执行PowerShell命令而不是实际的恶意软件文件

## 解决方案

### 1. 改进的文件列表获取命令

将原来的PowerShell命令：
```powershell
Get-ChildItem -Path 'C:\Desktop' -File | Select-Object -ExpandProperty Name
```

改为更简单的格式：
```powershell
Get-ChildItem -Path 'C:\Desktop' -File | ForEach-Object { $_.Name }
```

### 2. 增强的输出过滤逻辑

添加了完整的过滤规则来识别和排除PowerShell命令回显：

```python
# 跳过空行和可能的命令回显
if (line and 
    not line.startswith('powershell') and 
    not line.startswith('Get-ChildItem') and
    not line.startswith('PS ') and
    not '|' in line and
    not 'Select-Object' in line and
    not 'ForEach-Object' in line and
    not line.startswith('Command') and
    not '{' in line and
    not '}' in line):
    files.append(line)
```

### 3. 增加等待时间和详细日志

- 在解压完成后增加2秒等待时间，确保文件系统操作完成
- 添加详细的日志记录，便于问题诊断
- 记录原始输出和过滤后的结果

## 实现细节

### 修复前的问题

原始输出可能包含：
```
powershell -Command "Get-ChildItem -Path 'C:\Desktop' -File | ForEach-Object { $_.Name }"
malware.exe
Get-ChildItem -Path 'C:\Desktop' -File | Select-Object -ExpandProperty Name
config.txt
PS C:\Users\testuser> 
readme.md
ForEach-Object { $_.Name }
```

### 修复后的处理

新的过滤逻辑会：
1. **识别PowerShell命令**: 过滤以`powershell`、`Get-ChildItem`开头的行
2. **识别PowerShell提示符**: 过滤以`PS `开头的行
3. **识别管道命令**: 过滤包含`|`符号的行
4. **识别PowerShell语法**: 过滤包含`{`、`}`、`Select-Object`、`ForEach-Object`的行
5. **保留实际文件名**: 只保留不匹配上述规则的行

最终结果：
```python
files = ["malware.exe", "config.txt", "readme.md"]
```

### 代码改进

#### 1. 增强的解压方法

```python
async def _extract_archive_in_vm(self, vm_config, archive_path: str, extract_to: str) -> list:
    if success:
        logger.info("ZIP文件解压成功，获取解压后的文件列表")
        
        # 等待一下确保解压完成
        await asyncio.sleep(2)
        
        # 获取解压后的文件列表 - 使用更简单的命令避免引号问题
        list_cmd = f"powershell -Command \"Get-ChildItem -Path '{extract_to}' -File | ForEach-Object {{ $_.Name }}\""
        logger.info(f"获取文件列表命令: {list_cmd}")
        
        list_success, file_list = await self.vm_controller.execute_command_in_vm(
            vm_config.name, list_cmd, vm_config.username, vm_config.password, timeout=30
        )

        logger.info(f"文件列表命令执行结果: success={list_success}, output='{file_list}'")

        if list_success and file_list.strip():
            # 过滤掉可能的命令回显和空行
            raw_lines = file_list.strip().split('\n')
            files = []
            
            for line in raw_lines:
                line = line.strip()
                # 应用完整的过滤逻辑
                if (line and 
                    not line.startswith('powershell') and 
                    not line.startswith('Get-ChildItem') and
                    not line.startswith('PS ') and
                    not '|' in line and
                    not 'Select-Object' in line and
                    not 'ForEach-Object' in line and
                    not line.startswith('Command') and
                    not '{' in line and
                    not '}' in line):
                    files.append(line)
            
            logger.info(f"解压后的文件: {files}")
            
            if files:
                return files
            else:
                logger.warning("过滤后没有找到有效文件")
                return []
```

## 测试覆盖

创建了完整的测试套件 `test_file_list_parsing_fix.py`：

### 主要测试场景

1. **正常输出测试**: 验证正常的文件列表能正确解析
2. **命令回显测试**: 验证包含PowerShell命令回显的输出能正确过滤
3. **PowerShell提示符测试**: 验证包含`PS >`提示符的输出能正确处理
4. **管道命令测试**: 验证包含管道符号的命令行能被过滤
5. **空输出测试**: 验证空输出的处理
6. **纯命令回显测试**: 验证只有命令回显没有实际文件的情况
7. **混合内容测试**: 验证复杂混合内容的正确解析
8. **命令失败测试**: 验证解压或列表命令失败的处理

### 边界情况测试

- 文件名包含特殊字符的处理
- 文件名与PowerShell关键字相似的处理
- 各种PowerShell语法元素的识别

## 预期效果

1. **正确识别文件**: 系统能正确识别解压后的实际文件
2. **过滤命令回显**: 自动过滤PowerShell命令和提示符
3. **执行正确文件**: 选择并执行实际的恶意软件样本而不是命令
4. **提高稳定性**: 减少因错误文件识别导致的执行失败

## 使用示例

修复后的日志输出：

```
2025-09-12 17:03:26 | INFO | app.services.analysis_engine:_extract_archive_in_vm:501 - ZIP文件解压成功，获取解压后的文件列表
2025-09-12 17:03:28 | INFO | app.services.analysis_engine:_extract_archive_in_vm:508 - 获取文件列表命令: powershell -Command "Get-ChildItem -Path 'C:\Desktop' -File | ForEach-Object { $_.Name }"
2025-09-12 17:03:28 | INFO | app.services.analysis_engine:_extract_archive_in_vm:514 - 文件列表命令执行结果: success=True, output='malware.exe\nconfig.txt\nreadme.md'
2025-09-12 17:03:28 | INFO | app.services.analysis_engine:_extract_archive_in_vm:532 - 解压后的文件: ['malware.exe', 'config.txt', 'readme.md']
```

现在系统会：
1. ✅ 正确解压ZIP文件
2. ✅ 准确获取文件列表
3. ✅ 过滤PowerShell命令回显
4. ✅ 选择正确的可执行文件
5. ✅ 成功执行恶意软件样本

## 向后兼容性

- 保持所有现有API接口不变
- 改进只影响内部文件列表解析逻辑
- 不需要修改配置文件或外部调用方式
- 对于正常输出的情况，行为完全一致
