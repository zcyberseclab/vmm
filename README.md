# 🛡️ Malware Sandbox Analysis System

[![Release](https://img.shields.io/github/v/release/zcyberseclab/vmm)](https://github.com/zcyberseclab/vmm/releases)
[![License](https://img.shields.io/github/license/zcyberseclab/vmm)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Sandbox](https://img.shields.io/badge/Sandbox-Analysis-green.svg)](https://github.com/zcyberseclab/vmm)

A comprehensive automated malware sandbox analysis platform with parallel processing and behavioral monitoring capabilities. This system provides intelligent malware analysis with real-time monitoring, advanced scheduling, and detailed behavioral insights for security research and threat detection.

## 🌟 Key Features

- **🔍 Multi-Engine Analysis**: Support for multiple security analysis engines with comprehensive threat detection
- **⚡ Parallel Processing**: Simultaneous analysis with 40%+ time savings and 1.7x speed improvement
- **📊 Behavioral Analysis**: Deep behavioral monitoring with process tree construction and system activity tracking
- **🚀 RESTful API**: Complete API interface for integration and automation
- **📈 Real-time Monitoring**: Performance tracking, task status, and system health monitoring
- **🔧 Intelligent Management**: Automatic sandbox management and resource optimization
- **🛡️ Isolated Environment**: Secure sandbox execution with snapshot-based recovery
- **📋 Detailed Reports**: Comprehensive analysis reports with behavioral insights and threat indicators

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
    │ Behavioral Engine │   │ Security Engines  │
    │ (Activity Monitor)│   │ (5 Parallel VMs)  │
    └─────────┬─────────┘   └─────────┬─────────┘
              │                       │
    ┌─────────┴─────────┐   ┌─────────┴─────────┐
    │ Sandbox Monitor   │   │ Analysis Pool     │
    │                   │   │ ┌───────────────┐ │
    └───────────────────┘   │ │ Sandbox VMs   │ │
                            │ │ - engine-1    │ │
                            │ │ - engine-2    │ │
                            │ │ - engine-3    │ │
                            │ │ - engine-4    │ │
                            │ │ - engine-5    │ │
                            │ └───────────────┘ │
                            └───────────────────┘
```

### Technology Stack

- **Backend Framework**: FastAPI + Python 3.11
- **Sandbox Environment**: Isolated virtual machine execution
- **Async Processing**: asyncio + Parallel Task Queue
- **Performance Monitoring**: psutil + Custom Performance Monitor
- **Logging System**: loguru
- **Configuration Management**: YAML Configuration Files

## ✨ Supported Features

### 🔍 Malware Analysis

- **Multi-Engine Detection**: Support for multiple security analysis engines
  - Static analysis capabilities
  - Dynamic behavior analysis
  - Signature-based detection
  - Heuristic analysis
  - Machine learning detection

- **Behavioral Analysis**: Comprehensive behavioral monitoring and tracking
  - Process creation and termination
  - File system operations
  - Network connections
  - Registry modifications
  - Process tree construction
  - System call monitoring

### ⚡ Parallel Processing Architecture

- **Intelligent Scheduling**: Multiple analysis engines run simultaneously
- **Resource Pooling**: Dynamic sandbox resource allocation and management
- **Performance Optimization**: 40%+ time savings, 1.7x speed improvement
- **Error Isolation**: Single analysis failure doesn't affect other analyses

### 📊 Real-time Monitoring

- **Performance Monitoring**: Real-time tracking of CPU, memory, disk usage
- **Task Status**: Detailed task execution status and progress
- **Threat Detection**: Real-time threat detection and classification
- **System Health**: Sandbox status and resource usage monitoring

### 🔧 Advanced Features

- **Intelligent File Processing**: Automatic file type detection and validation
- **Sandbox Management**: Automatic snapshot restoration and cleanup
- **Time Unification**: All timestamps unified to local time format
- **Threat Intelligence**: Intelligent threat classification and reporting
- **Report Generation**: Comprehensive analysis reports with actionable insights
- **API Interface**: Complete RESTful API

## 🚀 Usage

### System Requirements

- Windows 10/11 (Recommended)
- Virtualization platform (for sandbox environment)
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

2. **Configure Security Exclusions**
   ```powershell
   # Add exclusions for analysis directory
   Add-MpPreference -ExclusionPath "C:\path\to\vmm\uploads"
   ```

3. **Prepare Sandbox Environment**
   - Create multiple Windows sandbox virtual machines
   - Install security analysis engines on each VM
   - Create baseline snapshots for each sandbox

4. **Edit Configuration File**
   ```bash
   # Edit config.yaml file
   # Configure sandbox names, credentials, analysis settings, etc.
   ```

### 🚀 Start the Service

```bash
# Start production server
uvicorn main:app --host 0.0.0.0 --port 8000

# Or start development server with auto-reload
python main.py
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
| **Parallel Analysis Time** | 390.7 seconds | Multi-engine simultaneous analysis |
| **Performance Improvement** | 40.2% | Time savings compared to serial analysis |
| **Speed Multiplier** | 1.7x | Parallel vs serial analysis speed |
| **CPU Usage** | 7.5% → 11.2% | CPU usage change during analysis |
| **Memory Usage** | 28.2% → 29.8% | Memory usage change during analysis |
| **Event Collection** | 530+ events | Behavioral monitoring event count |
| **Threat Detection** | 5+ engines | Multiple security engine results |

### Sandbox Startup Times

Startup and ready time statistics for each sandbox environment:

| Sandbox Environment | Startup Time | System Ready Time | Total |
|--------|----------|--------------|------|
| **Behavioral Monitor** | ~31 sec | ~5 sec | ~36 sec |
| **Security Engine 1** | ~44 sec | ~30 sec | ~74 sec |
| **Security Engine 2** | ~28 sec | ~25 sec | ~53 sec |
| **Security Engine 3** | ~33 sec | ~28 sec | ~61 sec |
| **Security Engine 4** | ~51 sec | ~32 sec | ~83 sec |
| **Security Engine 5** | ~64 sec | ~35 sec | ~99 sec |

### Analysis Phase Duration

| Phase | Average Duration | Description |
|-------|------------------|-------------|
| **Sandbox Startup** | 30-100 sec | Varies by different security engines |
| **Sample Upload** | 2-5 sec | File transfer to sandbox environment |
| **Sample Execution** | 5-10 sec | Malware execution time |
| **Threat Detection** | 10-25 sec | Wait for security engine detection |
| **Log Collection** | 5-15 sec | Collect analysis logs and reports |
| **Sandbox Cleanup** | 10-20 sec | Snapshot restoration and resource cleanup |
| **Behavioral Analysis** | 60-90 sec | Event collection and behavioral analysis |

### Concurrent Processing Capability

| Configuration Item | Current Value | Maximum Value | Description |
|--------------------|---------------|---------------|-------------|
| **Concurrent Tasks** | 10 | Configurable | Simultaneous analysis tasks |
| **Queue Size** | 100 | Configurable | Maximum queued task count |
| **Sandbox Pool Size** | 6 Sandboxes | Scalable | Available sandbox environments |
| **File Size Limit** | 100MB | Configurable | Single sample file size |

## 🔧 Configuration

The main configuration file `config.yaml` contains the following sections:

- **Server Configuration**: Port, upload directory, file size limits
- **Sandbox Configuration**: Sandbox names, credentials, snapshot names
- **Analysis Configuration**: Timeout settings, monitoring time, concurrency limits
- **Behavioral Monitoring**: Event types, collection count, analysis options

Please refer to the comments in the `config.yaml` file for detailed configuration.

## 📝 Important Notes

1. **Resource Requirements**: The system needs sufficient CPU and memory to run multiple sandbox environments simultaneously
2. **Network Isolation**: Recommended to run in an isolated network environment to prevent malware propagation
3. **Snapshot Management**: Regularly update sandbox snapshots to keep the analysis environment clean
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

1. **Virtualization platform not found**
   - Ensure virtualization software is properly installed
   - Check that virtualization commands are accessible from PATH

2. **Sandbox startup timeout**
   - Increase `vm_startup_timeout` in config.yaml
   - Check sandbox environments have sufficient resources allocated

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
- [Sandbox Setup Guide](docs/SANDBOX_SETUP.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## 🔗 Related Projects

- [System Monitor Tools](https://docs.microsoft.com/en-us/sysinternals/) - System monitoring and analysis tools
- [Virtualization Platforms](https://www.virtualbox.org/) - Sandbox virtualization solutions
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Microsoft Sysinternals team for system monitoring tools
- Virtualization platform developers for sandbox technologies
- FastAPI team for the excellent web framework
- Security research community for threat analysis methodologies
- All contributors who helped improve this project

## 📞 Support

- 📧 Email: [support@zcyberseclab.com](mailto:support@zcyberseclab.com)
- 🐛 Issues: [GitHub Issues](https://github.com/zcyberseclab/vmm/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/zcyberseclab/vmm/discussions)

---

⭐ If you find this project useful, please consider giving it a star on GitHub!
