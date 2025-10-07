# VMM：跨平台恶意软件沙箱分析系统

## 项目概述

本项目是一个基于硬件虚拟化技术构建的自动化恶意软件分析沙箱系统。其核心目标是提供一个安全、隔离且具备深度可观测性的动态分析环境，用于对Windows与Linux平台上的潜在恶意样本进行行为分析、威胁指标提取及EDR能力验证。

项目设计的最初是用来对标cape。

## 核心功能

### 1. 硬件虚拟化隔离环境

利用Intel VT-x/AMD-V硬件虚拟化扩展，构建强隔离的分析容器

确保恶意代码的执行被严格限制在隔离环境中，防止其对宿主机造成损害并增强反检测能力

### 2. 系统行为监控

在内核层面实现全面的行为监控与捕获，记录样本的所有关键操作（28种事件）：

#### 进程与执行监控

| 事件ID | 监控类型 | 描述 |
|--------|----------|------|
| 1 | Process creation | 进程创建 |
| 5 | Process terminated | 进程终止 |
| 8 | CreateRemoteThread | 远程线程创建（线程注入） |
| 10 | ProcessAccess | 进程访问（进程内存访问） |
| 25 | ProcessTampering | 进程篡改（进程映像更改） |

#### 文件系统活动

| 事件ID | 监控类型 | 描述 |
|--------|----------|------|
| 2 | File creation time changed | 文件创建时间更改 |
| 11 | FileCreate | 文件创建 |
| 15 | FileCreateStreamHash | NTFS数据流创建 |
| 23 | FileDelete | 文件删除检测 |
| 26 | FileDeleteDetected | 文件删除记录 |
| 27 | FileBlockExecutable | 可执行文件阻止 |
| 28 | FileBlockShredding | 文件粉碎阻止 |

#### 注册表操作

| 事件ID | 监控类型 | 描述 |
|--------|----------|------|
| 12 | RegistryEvent (Object create and delete) | 注册表事件（对象创建和删除） |
| 13 | RegistryEvent (Value Set) | 注册表事件（值设置）- 包含启动项 |
| 14 | RegistryEvent (Key and Value Rename) | 注册表事件（键和值重命名） |

#### 网络活动

| 事件ID | 监控类型 | 描述 |
|--------|----------|------|
| 3 | Network connection (TCP/UDP) | 网络连接（TCP/UDP） |
| 22 | DNSEvent | DNS查询 |

#### 系统与服务监控

| 事件ID | 监控类型 | 描述 |
|--------|----------|------|
| 4 | Sysmon service state changed | Sysmon服务状态更改 |
| 6 | Driver loaded | 驱动加载 |
| 7 | Image loaded | 镜像加载 |
| 9 | RawAccessRead | 原始访问读取（原始磁盘访问） |
| 16 | ServiceConfigurationChange | 服务配置变更 |
| 17 | PipeEvent | 命名管道创建 |
| 18 | PipeEvent | 命名管道连接 |
| 19 | WmiEvent | WMI过滤器 |
| 20 | WmiEvent | WMI消费者 |
| 21 | WmiEvent | WMI消费者过滤器 |
| 24 | ClipboardChange | 剪贴板内容变更 |

### 3. EDR报警分析

目前集成了5个杀软的报警检测，包括windows defender、avira、kaspersky、mcafee、trend

### 4. 跨平台分析支持

系统架构支持对Windows和Linux两大平台的恶意软件进行分析

通过统一的监控框架，对两套不同系统的行为进行一致化建模与日志记录

### 5. 自动化分析与报告生成

实现从样本投递、环境配置、监控执行到结果收集的全流程自动化

输出结构化的分析报告（如JSON格式），包含详尽的行为日志、提取的IOC（入侵指标）及系统变化快照，便于集成与后续分析
