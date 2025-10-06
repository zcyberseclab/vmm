# VirtualBox虚拟机导入导出工具

跨平台的VirtualBox虚拟机迁移工具，支持Windows和Linux系统。

## 🎯 功能特点

- ✅ **跨平台支持**：Windows和Linux都可以使用
- 📦 **完整导出**：导出虚拟机为OVA格式，包含快照信息
- 📥 **批量导入**：支持单个或批量导入虚拟机
- 📋 **详细信息**：显示虚拟机和快照详细信息
- 🔧 **自动检测**：自动查找VirtualBox安装路径

## 📋 系统要求

- Python 3.6+
- VirtualBox 6.0+ (已安装并添加到PATH)
- 足够的磁盘空间存储导出文件

## 🚀 使用方法

### 1. 查看虚拟机列表

```bash
# 查看当前所有虚拟机和快照
python vm_export_import.py list
```

### 2. 导出虚拟机

```bash
# 导出所有虚拟机到指定目录
python vm_export_import.py export --all --dir ./vm_backup

# 导出单个虚拟机
python vm_export_import.py export --vm "Windows 10" --dir ./vm_backup
```

### 3. 导入虚拟机

```bash
# 从目录导入所有虚拟机
python vm_export_import.py import --dir ./vm_backup

# 导入单个OVA文件
python vm_export_import.py import --ova ./vm_backup/Windows10/Windows10.ova

# 导入时重命名虚拟机
python vm_export_import.py import --ova ./vm_backup/Windows10/Windows10.ova --name "Windows 10 - Copy"
```

## 📁 导出文件结构

导出后的目录结构如下：

```
vm_backup/
├── export_report.json          # 导出报告
├── VM1/
│   ├── VM1.ova                # 虚拟机OVA文件
│   └── vm_info.json           # 虚拟机元数据（包含快照信息）
├── VM2/
│   ├── VM2.ova
│   └── vm_info.json
└── ...
```

## 📊 元数据信息

每个虚拟机的`vm_info.json`包含：

```json
{
  "vm_name": "Windows 10",
  "export_time": "2024-01-01T12:00:00",
  "snapshots": [
    {
      "name": "clean",
      "uuid": "12345678-1234-1234-1234-123456789abc",
      "is_current": true
    }
  ],
  "ova_file": "Windows 10.ova",
  "platform": "nt",
  "python_version": "3.11.0"
}
```

## 🔧 命令行参数

### 基本命令
- `list` - 列出所有虚拟机和快照
- `export` - 导出虚拟机
- `import` - 导入虚拟机

### 导出参数
- `--all` - 导出所有虚拟机
- `--vm <name>` - 导出指定虚拟机
- `--dir <path>` - 指定导出目录

### 导入参数
- `--dir <path>` - 从目录导入所有虚拟机
- `--ova <file>` - 导入指定OVA文件
- `--name <name>` - 导入时重命名虚拟机

## 💡 使用示例

### 完整迁移流程

**在源机器上（Windows）：**
```bash
# 1. 查看当前虚拟机
python vm_export_import.py list

# 2. 导出所有虚拟机
python vm_export_import.py export --all --dir D:\vm_backup

# 3. 将vm_backup目录复制到目标机器
```

**在目标机器上（Ubuntu）：**
```bash
# 1. 导入所有虚拟机
python3 vm_export_import.py import --dir ./vm_backup

# 2. 验证导入结果
python3 vm_export_import.py list
```

### 选择性导出

```bash
# 只导出特定虚拟机
python vm_export_import.py export --vm "Ubuntu Server" --dir ./backup
python vm_export_import.py export --vm "Windows 10 EDR" --dir ./backup
```

### 重命名导入

```bash
# 导入时重命名，避免冲突
python vm_export_import.py import --ova ./backup/Ubuntu/Ubuntu.ova --name "Ubuntu-Test"
```

## ⚠️ 注意事项

1. **磁盘空间**：确保有足够空间存储OVA文件（通常与虚拟机磁盘大小相当）

2. **VirtualBox版本**：建议源和目标机器使用相同或兼容的VirtualBox版本

3. **快照限制**：OVA格式不包含快照，只导出当前状态。快照信息保存在元数据中供参考

4. **网络设置**：导入后可能需要重新配置网络适配器

5. **路径问题**：Windows下路径包含空格时请使用引号

## 🐛 故障排除

### VirtualBox未找到
```bash
# 确保VirtualBox已安装并添加到PATH
# Windows: 添加 C:\Program Files\Oracle\VirtualBox 到PATH
# Linux: sudo apt install virtualbox
```

### 导出失败
- 确保虚拟机已关闭
- 检查磁盘空间是否充足
- 确认虚拟机名称正确（区分大小写）

### 导入失败
- 检查OVA文件是否完整
- 确认虚拟机名称不冲突
- 检查VirtualBox版本兼容性

### 编码问题
- 虚拟机名称包含特殊字符时可能出现编码问题
- 建议使用英文名称或重命名后导出

## 📞 技术支持

如遇问题，请检查：
1. Python版本是否支持
2. VirtualBox是否正确安装
3. 命令行参数是否正确
4. 系统权限是否充足

---

**提示**：首次使用建议先用测试虚拟机验证功能，确认无误后再进行重要虚拟机的迁移。
