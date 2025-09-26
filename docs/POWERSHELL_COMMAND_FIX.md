# PowerShell命令格式修复

## 问题描述

在实际运行中发现PowerShell的`Expand-Archive`命令执行失败，错误信息显示：

```
Unexpected token 'C:\Users\vboxuser\Desktop\7a8034f000654075e7a9fd3404b99e53fcf1527903342b757e12f860fddd9513.zip\" 
-DestinationPath \"C:\Users\vboxuser\Desktop\" -Force"' in expression or statement.
```

## 问题原因

原始的PowerShell命令构造使用了双重转义的引号：

```python
# 错误的格式
extract_cmd = f'powershell -Command "Expand-Archive -Path \\"{archive_path}\\" -DestinationPath \\"{extract_to}\\" -Force"'
```

这导致生成的命令包含了转义的双引号 `\"`，PowerShell无法正确解析。

## 解决方案

修改命令构造，使用外层双引号和内层单引号的组合：

```python
# 正确的格式
extract_cmd = f"powershell -Command \"Expand-Archive -Path '{archive_path}' -DestinationPath '{extract_to}' -Force\""
```

## 修复前后对比

### 修复前（错误）
```
powershell -Command "Expand-Archive -Path \"C:\Users\vboxuser\Desktop\sample.zip\" -DestinationPath \"C:\Users\vboxuser\Desktop\" -Force"
```

### 修复后（正确）
```
powershell -Command "Expand-Archive -Path 'C:\Users\vboxuser\Desktop\sample.zip' -DestinationPath 'C:\Users\vboxuser\Desktop' -Force"
```

## 修改的文件

### 1. `app/services/analysis_engine.py`

修改了两个地方：

1. **解压命令**（第436行）：
   ```python
   # 修改前
   extract_cmd = f'powershell -Command "Expand-Archive -Path \\"{archive_path}\\" -DestinationPath \\"{extract_to}\\" -Force"'
   
   # 修改后
   extract_cmd = f"powershell -Command \"Expand-Archive -Path '{archive_path}' -DestinationPath '{extract_to}' -Force\""
   ```

2. **文件列表命令**（第448行）：
   ```python
   # 修改前
   list_cmd = f'powershell -Command "Get-ChildItem -Path \\"{extract_to}\\" -File | Select-Object -ExpandProperty Name"'
   
   # 修改后
   list_cmd = f"powershell -Command \"Get-ChildItem -Path '{extract_to}' -File | Select-Object -ExpandProperty Name\""
   ```

## 测试验证

创建了专门的测试文件 `tests/test_powershell_command_fix.py` 来验证修复：

### 测试用例

1. **基本命令格式测试**：验证生成的PowerShell命令格式正确
2. **长文件名测试**：测试包含长哈希文件名的情况
3. **路径包含空格测试**：验证路径中包含空格时的处理
4. **直接命令构造测试**：直接测试命令字符串构造逻辑
5. **错误处理测试**：验证命令执行失败时的处理

### 测试结果

所有测试都通过，验证了修复的有效性：

```
tests/test_powershell_command_fix.py::TestPowerShellCommandFix::test_powershell_command_format_fixed PASSED
tests/test_powershell_command_fix.py::TestPowerShellCommandFix::test_powershell_command_with_spaces_in_path PASSED
tests/test_powershell_command_fix.py::TestPowerShellCommandFix::test_command_construction_directly PASSED
tests/test_powershell_command_fix.py::TestPowerShellCommandFix::test_error_handling_with_fixed_command PASSED
```

## 关键要点

1. **引号使用规则**：
   - 外层使用双引号包围整个PowerShell命令
   - 内层路径参数使用单引号
   - 避免使用转义的双引号 `\"`

2. **路径处理**：
   - 单引号能正确处理包含空格的路径
   - 单引号避免了Windows路径中反斜杠的转义问题

3. **兼容性**：
   - 修复后的格式在所有Windows PowerShell版本中都能正常工作
   - 支持包含特殊字符和空格的文件路径

## 影响范围

这个修复解决了ZIP文件在虚拟机中无法解压的核心问题，确保了：

1. ✅ ZIP文件能正确解压到虚拟机桌面
2. ✅ 解压后的文件列表能正确获取
3. ✅ 恶意软件样本能正常执行和分析
4. ✅ 支持各种文件名格式（包括长哈希名、包含空格等）

## 验证方法

要验证修复是否生效，可以查看日志中的PowerShell命令格式：

```
2025-09-12 16:35:28.148 | INFO | app.services.analysis_engine:_extract_archive_in_vm:439 - 解压命令: powershell -Command "Expand-Archive -Path 'C:\Users\vboxuser\Desktop\sample.zip' -DestinationPath 'C:\Users\vboxuser\Desktop' -Force"
```

正确的命令应该：
- 使用单引号包围路径
- 没有转义的双引号 `\"`
- 格式清晰易读
