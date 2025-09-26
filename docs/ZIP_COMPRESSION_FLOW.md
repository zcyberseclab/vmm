# ZIP压缩流程文档

## 概述

为了解决虚拟机中没有安装WinRAR和7-Zip的问题，系统已经修改为使用ZIP压缩格式，并使用PowerShell内置的`Expand-Archive`命令进行解压。

## 新的工作流程

### 1. 文件上传阶段

当用户通过API上传文件时：

1. **用户提交原始文件**（任何格式：.exe, .dll, .bin等）
2. **系统自动处理**：
   - 保存原始文件到本地存储
   - 自动创建ZIP压缩包，包含原始文件
   - 计算原始文件和ZIP文件的哈希值
   - 返回包含两个文件信息的响应

### 2. 文件信息结构

新的文件信息包含以下字段：

```json
{
    "path": "/uploads/abc123.zip",           // ZIP文件路径（用于上传到虚拟机）
    "original_path": "/uploads/abc123.exe",  // 原始文件路径
    "hash": "zip_file_sha256_hash",          // ZIP文件哈希
    "original_hash": "original_file_hash",   // 原始文件哈希
    "size": 1500,                           // ZIP文件大小
    "original_size": 1000,                  // 原始文件大小
    "original_name": "malware.exe",         // 原始文件名
    "is_compressed": true                   // 标识为压缩文件
}
```

### 3. 虚拟机分析阶段

在虚拟机中的处理流程：

1. **上传ZIP文件**到虚拟机桌面
2. **使用PowerShell解压**：
   ```powershell
   powershell -Command "Expand-Archive -Path 'C:\Users\user\Desktop\sample.zip' -DestinationPath 'C:\Users\user\Desktop' -Force"
   ```
3. **获取解压后的文件列表**
4. **选择可执行文件**（按优先级：.exe > .com > .scr > .bat > .cmd > .ps1 > .vbs > .js）
5. **执行选中的文件**

## 技术实现

### FileHandler类修改

- `save_uploaded_file()` 方法现在会：
  - 保存原始文件
  - 创建ZIP压缩包
  - 返回包含两个文件信息的字典

- 新增 `_create_zip_archive()` 方法：
  - 使用Python的zipfile模块
  - 压缩级别设置为6（平衡压缩率和速度）
  - 错误处理和清理机制

### AnalysisEngine类修改

- `_is_archive_file()` 方法：
  - 只识别.zip文件为压缩文件
  - 移除对.rar和.7z的支持

- `_extract_archive_in_vm()` 方法：
  - 专门使用PowerShell的Expand-Archive命令
  - 只支持ZIP格式
  - 改进的错误处理和日志记录

- `_upload_sample_to_vm()` 和 `_execute_sample_in_vm()` 方法：
  - 支持新的文件信息结构
  - 正确处理ZIP文件的上传和解压

### AnalysisTask模型扩展

新增字段：
- `original_file_hash`: 原始文件哈希
- `original_file_size`: 原始文件大小
- `original_file_path`: 原始文件路径
- `is_compressed`: 是否为压缩文件标识

## 优势

1. **兼容性**：PowerShell的Expand-Archive是Windows内置命令，无需额外安装
2. **可靠性**：ZIP格式是标准格式，支持良好
3. **安全性**：避免了依赖第三方解压软件
4. **维护性**：简化了虚拟机环境的配置要求

## 向后兼容性

系统保持向后兼容：
- 如果`is_compressed`为False，系统会按原来的方式处理文件
- 现有的API接口保持不变
- 现有的配置文件无需修改

## 测试覆盖

实现了完整的测试覆盖：

### 单元测试 (`test_zip_compression.py`)
- ZIP文件创建和验证
- 文件哈希计算
- 重复文件处理
- 解压逻辑测试
- 可执行文件选择测试

### 集成测试 (`test_integration_zip_flow.py`)
- 完整的文件处理流程
- 任务创建和信息传递
- PowerShell命令格式验证
- 错误处理测试

## 使用示例

### API调用示例

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@malware.exe" \
  -F "vm_names=windows10_vm" \
  -F "timeout=300"
```

### 响应示例

```json
{
    "task_id": "abc-123-def",
    "status": "pending",
    "message": "任务已成功提交，正在处理中"
}
```

## 故障排除

### 常见问题

1. **ZIP文件创建失败**
   - 检查磁盘空间
   - 检查文件权限
   - 查看日志中的详细错误信息

2. **虚拟机中解压失败**
   - 确认PowerShell版本支持Expand-Archive命令
   - 检查文件路径中的特殊字符
   - 验证ZIP文件完整性
   - **重要**：确保PowerShell命令使用正确的引号格式（外层双引号，路径使用单引号）

3. **PowerShell命令格式问题**
   - 正确格式：`powershell -Command "Expand-Archive -Path 'file.zip' -DestinationPath 'destination' -Force"`
   - 避免双重转义引号：不要使用 `\"`
   - 路径包含空格时使用单引号包围

4. **文件执行失败**
   - 检查解压后的文件权限
   - 确认文件类型识别正确
   - 查看虚拟机中的执行日志

### 日志关键字

监控以下日志关键字：
- "ZIP文件已创建"
- "使用PowerShell Expand-Archive解压ZIP文件"
- "解压后的文件"
- "将执行解压后的文件"

## 性能考虑

- ZIP压缩会增加少量处理时间（通常<1秒）
- 压缩后的文件通常比原始文件小，减少网络传输时间
- 解压时间取决于文件大小，通常在几秒内完成

## 安全考虑

- ZIP文件本身不会被执行，只有解压后的内容才会执行
- 使用Force参数确保覆盖现有文件，避免冲突
- 保留原始文件哈希用于完整性验证
