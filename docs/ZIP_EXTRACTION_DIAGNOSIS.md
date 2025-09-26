# ZIP解压诊断和备用方法改进

## 问题描述

用户反馈在虚拟机中能看到ZIP压缩文件，但解压似乎没有成功。这表明：

1. **文件上传成功**: ZIP文件已经成功上传到虚拟机
2. **解压可能失败**: PowerShell的`Expand-Archive`命令可能遇到问题
3. **缺乏诊断信息**: 原有代码缺少详细的诊断步骤来确定失败原因

## 解决方案

### 1. 增强的诊断流程

添加了完整的诊断步骤来识别解压失败的具体原因：

#### 步骤1: ZIP文件存在性检查
```powershell
Test-Path 'C:\Desktop\sample.zip'
```
- 验证ZIP文件是否真的存在于虚拟机中
- 排除文件上传失败的可能性

#### 步骤2: 目标目录检查和创建
```powershell
Test-Path 'C:\Desktop'
New-Item -ItemType Directory -Path 'C:\Desktop' -Force
```
- 确保解压目标目录存在
- 如果不存在则自动创建

#### 步骤3: 详细解压命令
```powershell
try { 
    Expand-Archive -Path 'sample.zip' -DestinationPath 'C:\Desktop' -Force; 
    Write-Host 'Extract Success' 
} catch { 
    Write-Host 'Extract Failed:' $_.Exception.Message 
}
```
- 使用try-catch捕获详细的错误信息
- 明确显示解压成功或失败的原因

### 2. 多重备用解压方法

如果PowerShell的`Expand-Archive`失败，系统会自动尝试备用方法：

#### 方法1: .NET ZipFile类
```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem;
[System.IO.Compression.ZipFile]::ExtractToDirectory('sample.zip', 'C:\Desktop');
```
- 使用.NET Framework的原生ZIP支持
- 通常比PowerShell命令更可靠

#### 方法2: COM Shell对象
```powershell
$shell = New-Object -ComObject Shell.Application;
$zip = $shell.Namespace('sample.zip');
$dest = $shell.Namespace('C:\Desktop');
$dest.CopyHere($zip.Items(), 4);
```
- 使用Windows Shell的COM接口
- 最传统但最兼容的方法

### 3. 详细日志记录

每个步骤都有详细的日志记录：

```
INFO | 使用PowerShell Expand-Archive解压ZIP文件: C:\Desktop\sample.zip
INFO | 解压命令: powershell -Command "Expand-Archive..."
INFO | 解压命令执行结果: success=True, output=''
INFO | ZIP文件解压命令执行成功，验证解压结果
INFO | ZIP文件存在检查: True, 结果: 'True'
INFO | 目标目录存在检查: True, 结果: 'True'
INFO | 详细解压命令: powershell -Command "try { Expand-Archive..."
INFO | 详细解压结果: success=True, output='Extract Success'
INFO | 获取文件列表命令: powershell -Command "Get-ChildItem..."
INFO | 文件列表命令执行结果: success=True, output='malware.exe\nconfig.txt'
INFO | 解压后的文件: ['malware.exe', 'config.txt']
```

## 实现细节

### 主要改进的方法

#### `_extract_archive_in_vm()` 方法增强

```python
async def _extract_archive_in_vm(self, vm_config, archive_path: str, extract_to: str) -> list:
    # 1. 执行初始解压命令
    success, output = await self.vm_controller.execute_command_in_vm(...)
    logger.info(f"解压命令执行结果: success={success}, output='{output}'")
    
    if success:
        # 2. 验证ZIP文件存在
        verify_zip_cmd = f"powershell -Command \"Test-Path '{archive_path}'\""
        zip_exists, zip_check = await self.vm_controller.execute_command_in_vm(...)
        
        if not zip_exists or 'True' not in zip_check:
            logger.error(f"ZIP文件不存在: {archive_path}")
            return []
        
        # 3. 检查并创建目标目录
        check_dir_cmd = f"powershell -Command \"Test-Path '{extract_to}'\""
        dir_exists, dir_check = await self.vm_controller.execute_command_in_vm(...)
        
        if 'False' in dir_check:
            create_dir_cmd = f"powershell -Command \"New-Item -ItemType Directory -Path '{extract_to}' -Force\""
            await self.vm_controller.execute_command_in_vm(...)
        
        # 4. 执行详细解压命令
        detailed_extract_cmd = f"powershell -Command \"try {{ Expand-Archive -Path '{archive_path}' -DestinationPath '{extract_to}' -Force; Write-Host 'Extract Success' }} catch {{ Write-Host 'Extract Failed:' $_.Exception.Message }}\""
        detailed_success, detailed_output = await self.vm_controller.execute_command_in_vm(...)
        
        # 5. 获取文件列表
        files = await self._get_extracted_files(vm_config, extract_to)
        
        if not files:
            # 6. 如果主方法失败，尝试备用方法
            return await self._try_alternative_extract(vm_config, archive_path, extract_to)
        
        return files
```

#### 新增备用解压方法

```python
async def _try_alternative_extract(self, vm_config, archive_path: str, extract_to: str) -> list:
    # 方法1: .NET ZipFile类
    dotnet_extract_cmd = f"""powershell -Command "
    Add-Type -AssemblyName System.IO.Compression.FileSystem;
    try {{
        [System.IO.Compression.ZipFile]::ExtractToDirectory('{archive_path}', '{extract_to}');
        Write-Host 'DotNet Extract Success'
    }} catch {{
        Write-Host 'DotNet Extract Failed:' $_.Exception.Message
    }}
    " """
    
    dotnet_success, dotnet_output = await self.vm_controller.execute_command_in_vm(...)
    files = await self._get_extracted_files(vm_config, extract_to)
    if files:
        return files
    
    # 方法2: COM Shell对象
    com_extract_cmd = f"""powershell -Command "
    try {{
        $shell = New-Object -ComObject Shell.Application;
        $zip = $shell.Namespace('{archive_path}');
        $dest = $shell.Namespace('{extract_to}');
        $dest.CopyHere($zip.Items(), 4);
        Write-Host 'COM Extract Success'
    }} catch {{
        Write-Host 'COM Extract Failed:' $_.Exception.Message
    }}
    " """
    
    com_success, com_output = await self.vm_controller.execute_command_in_vm(...)
    return await self._get_extracted_files(vm_config, extract_to)
```

#### 独立的文件列表获取方法

```python
async def _get_extracted_files(self, vm_config, extract_to: str) -> list:
    list_cmd = f"powershell -Command \"Get-ChildItem -Path '{extract_to}' -File | ForEach-Object {{ $_.Name }}\""
    list_success, file_list = await self.vm_controller.execute_command_in_vm(...)
    
    if list_success and file_list.strip():
        # 应用过滤逻辑移除命令回显
        raw_lines = file_list.strip().split('\n')
        files = []
        
        for line in raw_lines:
            line = line.strip()
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
        
        return files
    
    return []
```

## 测试覆盖

创建了完整的测试套件 `test_zip_extraction_diagnosis.py`：

### 诊断功能测试
- ✅ 带详细诊断的解压过程
- ✅ ZIP文件不存在的处理
- ✅ 目标目录创建过程
- ✅ 各种解压失败情况

### 备用方法测试
- ✅ .NET方法成功解压
- ✅ COM方法备用解压
- ✅ 所有方法都失败的处理
- ✅ 独立文件列表获取方法

### 集成测试
- ✅ 完整解压工作流程
- ✅ 多步骤诊断验证

## 故障排除指南

### 常见问题和解决方案

1. **ZIP文件不存在**
   - 检查文件上传是否成功
   - 验证文件路径是否正确
   - 确认虚拟机中的文件权限

2. **目标目录问题**
   - 系统会自动创建不存在的目录
   - 检查目录权限设置
   - 验证路径格式是否正确

3. **PowerShell权限问题**
   - 系统会自动尝试备用的.NET方法
   - COM方法作为最后的备选
   - 详细错误信息会记录在日志中

4. **文件列表为空**
   - 检查解压是否真的成功
   - 验证文件是否被解压到正确位置
   - 查看详细的错误信息

### 日志分析

通过日志可以准确定位问题：

- `ZIP文件存在检查: False` → 文件上传问题
- `Extract Failed: Access denied` → 权限问题
- `DotNet Extract Success` → 备用方法成功
- `解压后的文件: []` → 解压失败或文件列表获取问题

## 预期效果

1. **准确诊断**: 能够准确识别解压失败的具体原因
2. **自动恢复**: 主方法失败时自动尝试备用方法
3. **详细日志**: 提供完整的诊断信息便于问题排查
4. **提高成功率**: 多种解压方法确保更高的成功率

现在系统能够：
- ✅ 详细诊断ZIP解压过程的每个步骤
- ✅ 自动检测和修复常见问题（如目录不存在）
- ✅ 提供多种备用解压方法
- ✅ 记录详细的诊断信息便于问题排查
- ✅ 在主方法失败时自动尝试备用方案
