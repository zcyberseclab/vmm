# VirtualBox EDR Malware Analysis System

A VirtualBox-based malware analysis platform supporting multiple EDR solutions and parallel processing with Sysmon behavioral analysis.

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

### Installation Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd vmm
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Windows Defender Exclusions**
   ```powershell
   Add-MpPreference -ExclusionPath "path to upload test samples"
   ```

4. **Prepare Virtual Machines**
   - Create 6 Windows 10 virtual machines
   - Install corresponding EDR software
   - Create `edr-baseline` snapshots

5. **Modify Configuration**
   ```bash
   # Edit config.yaml file
   # Configure VM names, usernames, passwords, etc.
   ```

### Start the Service

```bash
# Start development server
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Or use the port from config file
python main.py
```

### API Usage Examples

1. **Submit Sample for Analysis**
   ```bash
   curl -X POST "http://localhost:8002/api/analyze" \
        -F "file=@malware.exe" \
        -F "filename=test_malware.exe"
   ```

2. **Query Task Status**
   ```bash
   curl "http://localhost:8002/api/task/{task_id}"
   ```

3. **Get Analysis Results**
   ```bash
   curl "http://localhost:8002/api/result/{task_id}"
   ```

4. **System Health Check**
   ```bash
   curl "http://localhost:8002/api/health"
   ```

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

## 🐛 Troubleshooting

For common issues and solutions, please check the project Wiki or submit an Issue.

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
