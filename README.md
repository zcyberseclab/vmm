# 🛡️ VirtualBox EDR Malware Analysis System

[![Release](https://img.shields.io/github/v/release/zcyberseclab/vmm)](https://github.com/zcyberseclab/vmm/releases)
[![License](https://img.shields.io/github/license/zcyberseclab/vmm)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![VirtualBox](https://img.shields.io/badge/VirtualBox-7.0+-orange.svg)](https://www.virtualbox.org/)

A comprehensive VirtualBox-based malware analysis platform supporting multiple EDR solutions and parallel processing with Sysmon behavioral analysis. This system provides automated malware analysis capabilities with real-time monitoring, intelligent scheduling, and detailed behavioral analysis.

## 🌟 Key Features

- **🔍 Multi-EDR Analysis**: Support for 5 mainstream EDR solutions (Windows Defender, McAfee, Kaspersky, Avira, Trend Micro)
- **⚡ Parallel Processing**: Simultaneous analysis with 40%+ time savings and 1.7x speed improvement
- **📊 Behavioral Analysis**: Comprehensive Sysmon-based behavioral monitoring and process tree construction
- **🚀 RESTful API**: Complete API interface for integration and automation
- **📈 Real-time Monitoring**: Performance tracking, task status, and system health monitoring
- **🔧 Intelligent Management**: Automatic VM snapshot management and resource optimization

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Web Server                       │
│                     (Port: 8000)                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                  Task Manager                               │
│              (Parallel Analysis Scheduler)                  │
└─────────────┬───────────────────────┬───────────────────────┘
              │                       │
    ┌─────────┴─────────┐   ┌─────────┴─────────┐
    │  Sysmon Analysis  │   │   EDR Analysis    │
    │ (Behavior Monitor)│   │ (5 Parallel VMs)  │
    └─────────┬─────────┘   └─────────┬─────────┘
              │                       │
    ┌─────────┴─────────┐   ┌─────────┴─────────┐
    │ win10-64-sysmon   │   │ VM Pool Manager   │
    │                   │   │ ┌───────────────┐ │
    └───────────────────┘   │ │ win10-64-*    │ │
                            │ │ - defender    │ │
                            │ │ - mcafee      │ │
                            │ │ - kaspersky   │ │
                            │ │ - avira       │ │
                            │ │ - trend       │ │
                            │ └───────────────┘ │
                            └───────────────────┘
```

### Technology Stack

- **Backend Framework**: FastAPI + Python 3.11
- **Virtualization Platform**: Oracle VirtualBox
- **Async Processing**: asyncio + Parallel Task Queue
- **Performance Monitoring**: psutil + Custom Performance Monitor
- **Logging System**: loguru
- **Configuration Management**: YAML Configuration Files

## ✨ Supported Features

### 🔍 Malware Analysis

- **Multi-Engine Detection**: Support for 5 mainstream EDR solutions
  - Windows Defender
  - McAfee
  - Kaspersky
  - Avira
  - Trend Micro

- **Behavioral Analysis**: Detailed behavioral monitoring based on Sysmon
  - Process creation and termination
  - File system operations
  - Network connections
  - Registry modifications
  - Process tree construction

### ⚡ Parallel Processing Architecture

- **Intelligent Scheduling**: Sysmon and EDR analysis run simultaneously
- **Resource Pooling**: Dynamic VM resource allocation and management
- **Performance Optimization**: 40%+ time savings, 1.7x speed improvement
- **Error Isolation**: Single analysis failure doesn't affect other analyses

### 📊 Real-time Monitoring

- **Performance Monitoring**: Real-time tracking of CPU, memory, disk usage
- **Task Status**: Detailed task execution status and progress
- **Alert Statistics**: Real-time alert count and type statistics
- **System Health**: VM status and resource usage monitoring

### 🔧 Advanced Features

- **Intelligent File Processing**: Automatic file type detection and validation
- **Snapshot Management**: Automatic VM snapshot restoration and cleanup
- **Time Unification**: All timestamps unified to local time format
- **Alert Deduplication**: Intelligent alert deduplication and aggregation
- **API Interface**: Complete RESTful API

## 🚀 Usage

### System Requirements

- Windows 10/11 (Recommended)
- Oracle VirtualBox 7.0+
- Python 3.11+
- At least 16GB RAM
- 100GB+ available disk space

### 📦 Installation

#### Option 1: Download Release (Recommended)

1. **Download Latest Release**
   ```bash
   # Download from GitHub releases
   wget https://github.com/zcyberseclab/vmm/releases/latest/download/vmm-latest.tar.gz
   tar -xzf vmm-latest.tar.gz
   cd vmm-*
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

#### Option 2: Clone from Source

1. **Clone the Repository**
   ```bash
   git clone https://github.com/zcyberseclab/vmm.git
   cd vmm
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### ⚙️ Configuration

1. **Copy Configuration Template**
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **Configure Windows Defender Exclusions**
   ```powershell
   Add-MpPreference -ExclusionPath "C:\path\to\vmm\uploads"
   ```

3. **Prepare Virtual Machines**
   - Create 6 Windows 10 virtual machines
   - Install corresponding EDR software on each VM
   - Create `edr-baseline` snapshots for each VM

4. **Edit Configuration File**
   ```bash
   # Edit config.yaml file
   # Configure VM names, usernames, passwords, API keys, etc.
   ```

### 🚀 Start the Service

```bash
# Start production server
python main.py

# Or start development server with auto-reload
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be available at `http://localhost:8000` (or the port specified in your config.yaml).

### 📡 API Usage Examples

1. **Submit Sample for Analysis**
   ```bash
   curl -X POST "http://localhost:8000/api/analyze" \
        -H "X-API-Key: your-api-key" \
        -F "file=@malware.exe" \
        -F "filename=test_malware.exe"
   ```

2. **Query Task Status**
   ```bash
   curl -H "X-API-Key: your-api-key" \
        "http://localhost:8000/api/task/{task_id}"
   ```

3. **Get Analysis Results**
   ```bash
   curl -H "X-API-Key: your-api-key" \
        "http://localhost:8000/api/result/{task_id}"
   ```

4. **System Health Check**
   ```bash
   curl "http://localhost:8000/api/health"
   ```

5. **Interactive API Documentation**
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

## 📈 Performance Statistics

### System Performance Metrics

Performance statistics based on actual test data:

| Metric | Value | Description |
|--------|-------|-------------|
| **Parallel Analysis Time** | 390.7 seconds | 5 EDR + Sysmon simultaneous analysis |
| **Performance Improvement** | 40.2% | Time savings compared to serial analysis |
| **Speed Multiplier** | 1.7x | Parallel vs serial analysis speed |
| **CPU Usage** | 7.5% → 11.2% | CPU usage change during analysis |
| **Memory Usage** | 28.2% → 29.8% | Memory usage change during analysis |
| **Event Collection** | 530 events | Single Sysmon event count |
| **Alert Generation** | 5 alerts | 5 EDR engine detection results |

### Virtual Machine Startup Times

Startup and ready time statistics for each virtual machine:

| Virtual Machine | Startup Time | System Ready Time | Total |
|--------|----------|--------------|------|
| **win10-64-sysmon** | ~31 sec | ~5 sec | ~36 sec |
| **win10-64-defender** | ~44 sec | ~30 sec | ~74 sec |
| **win10-64-mcafee** | ~28 sec | ~25 sec | ~53 sec |
| **win10-64-kaspersky** | ~33 sec | ~28 sec | ~61 sec |
| **win10-64-avira** | ~51 sec | ~32 sec | ~83 sec |
| **win10-64-trend** | ~64 sec | ~35 sec | ~99 sec |

### Analysis Phase Duration

| Phase | Average Duration | Description |
|-------|------------------|-------------|
| **VM Startup** | 30-100 sec | Varies by different EDR software |
| **Sample Upload** | 2-5 sec | File transfer to virtual machine |
| **Sample Execution** | 5-10 sec | Malware execution time |
| **EDR Detection** | 10-25 sec | Wait for EDR detection and quarantine |
| **Log Collection** | 5-15 sec | Collect EDR alert logs |
| **VM Cleanup** | 10-20 sec | Snapshot restoration and resource cleanup |
| **Sysmon Analysis** | 60-90 sec | Event collection and analysis |

### Concurrent Processing Capability

| Configuration Item | Current Value | Maximum Value | Description |
|--------------------|---------------|---------------|-------------|
| **Concurrent Tasks** | 10 | Configurable | Simultaneous analysis tasks |
| **Queue Size** | 100 | Configurable | Maximum queued task count |
| **VM Pool Size** | 6 VMs | Scalable | Available virtual machines |
| **File Size Limit** | 100MB | Configurable | Single sample file size |

## 🔧 Configuration

The main configuration file `config.yaml` contains the following sections:

- **Server Configuration**: Port, upload directory, file size limits
- **Virtual Machine Configuration**: VM names, credentials, snapshot names
- **Analysis Configuration**: Timeout settings, monitoring time, concurrency limits
- **Sysmon Configuration**: Event types, collection count, analysis options

Please refer to the comments in the `config.yaml` file for detailed configuration.

## 📝 Important Notes

1. **Resource Requirements**: The system needs sufficient CPU and memory to run multiple virtual machines simultaneously
2. **Network Isolation**: Recommended to run in an isolated network environment to prevent malware propagation
3. **Snapshot Management**: Regularly update virtual machine snapshots to keep the system clean
4. **Log Monitoring**: Monitor log file sizes and clean up old logs regularly
5. **Security Protection**: Ensure the host system has appropriate security protection measures

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

## 🐛 Troubleshooting

### Common Issues

1. **VirtualBox not found**
   - Ensure VirtualBox is installed and `VBoxManage` is in your PATH
   - On Windows, check `C:\Program Files\Oracle\VirtualBox\`

2. **VM startup timeout**
   - Increase `vm_startup_timeout` in config.yaml
   - Check VM has sufficient resources allocated

3. **API key authentication failed**
   - Verify the API key in config.yaml matches the X-API-Key header
   - Check for typos in the API key

4. **File upload fails**
   - Check file size limits in config.yaml
   - Ensure upload directory has write permissions

For more issues and solutions, please check the [Issues](https://github.com/zcyberseclab/vmm/issues) page.

## 📚 Documentation

- [API Documentation](docs/API.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [VM Setup Guide](docs/VM_SETUP.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## 🔗 Related Projects

- [Sysmon](https://docs.microsoft.com/en-us/sysinternals/downloads/sysmon) - System Monitor for Windows
- [VirtualBox](https://www.virtualbox.org/) - Virtualization platform
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Microsoft Sysinternals team for Sysmon
- Oracle for VirtualBox
- FastAPI team for the excellent web framework
- All contributors who helped improve this project

## 📞 Support

- 📧 Email: [support@zcyberseclab.com](mailto:support@zcyberseclab.com)
- 🐛 Issues: [GitHub Issues](https://github.com/zcyberseclab/vmm/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/zcyberseclab/vmm/discussions)

---

⭐ If you find this project useful, please consider giving it a star on GitHub!
