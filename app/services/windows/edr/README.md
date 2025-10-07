# EDR Client Architecture

This directory contains the EDR (Endpoint Detection and Response) client implementations for the VMM system. The architecture is designed to be modular and extensible, making it easy to add support for new EDR/antivirus solutions.

## Architecture Overview

```
app/services/windows/edr/
├── __init__.py              # Package exports and version info
├── base.py                  # Abstract base class for all EDR clients
├── windows_defender.py      # Windows Defender implementation
├── windows_kaspersky.py     # Kaspersky implementation
├── windows_mcafee.py        # McAfee implementation
├── windows_avira.py         # Avira implementation
├── windows_trend.py         # Trend Micro implementation
├── manager.py              # EDR manager for coordinating multiple clients
└── README.md               # This documentation
```

## Core Components

### 1. EDRClient (base.py)
Abstract base class that defines the interface all EDR clients must implement:
- `get_alerts()`: Main method for retrieving alerts from the EDR system
- Common initialization parameters (vm_name, vm_controller, credentials)

### 2. WindowsDefenderEDRClient (windows_defender.py)
Complete implementation for Windows Defender:
- Queries quarantine information using MpCmdRun.exe
- Parses threat detection data
- Converts to standardized EDRAlert objects

### 3. Other EDR Clients
Template implementations showing how to add new EDR clients:
- Demonstrates the required method structure
- Includes implementation for various antivirus solutions
- Shows data conversion patterns

### 4. EDRManager (manager.py)
Factory and coordinator class:
- Creates appropriate EDR client instances based on configuration
- Manages multiple VM configurations
- Provides unified interface for alert collection

## Adding a New EDR Client

To add support for a new EDR/antivirus solution, follow these steps:

### Step 1: Create the Implementation File
Create a new file `app/services/windows/edr/your_edr.py`:

```python
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
from app.models.task import EDRAlert
from .base import EDRClient

class YourEDRClient(EDRClient):
    async def get_alerts(self, start_time: datetime, end_time: Optional[datetime] = None,
                        file_hash: Optional[str] = None, file_name: Optional[str] = None) -> List[EDRAlert]:
        # Implement your EDR-specific alert retrieval logic
        pass
```

### Step 2: Update the Manager
Add your client to `manager.py`:

```python
# Import your client
from .your_edr import YourEDRClient

# Add to _create_edr_client method
elif antivirus_type == 'your_edr':
    return YourEDRClient(vm_name, self.vm_controller, username, password)

# Update supported types
def get_supported_antivirus_types(self) -> List[str]:
    return ['defender', 'kaspersky', 'mcafee', 'avira', 'trend', 'your_edr']
```

### Step 3: Update Package Exports
Add your client to `__init__.py`:

```python
from .your_edr import YourEDRClient

__all__ = [
    'EDRClient',
    'WindowsDefenderEDRClient',
    'KasperskyEDRClient',
    'McafeeEDRClient',
    'AviraEDRClient',
    'TrendMicroEDRClient',
    'YourEDRClient',  # Add this
    'EDRManager',
    'create_edr_manager'
]
```

### Step 4: Update Configuration
Add your EDR type to the VM configuration in `config.yaml`:

```yaml
edr_analysis:
  vms:
    - name: "win10-64-your-edr"
      antivirus: "your_edr"  # Use your EDR type here
      username: "vboxuser"
      password: "123456"
      baseline_snapshot: "edr-baseline"
```

## Implementation Guidelines

### Required Methods
Every EDR client must implement:
- `get_alerts()`: Main entry point for alert retrieval
- Handle exceptions gracefully and return empty list on failure
- Log operations for debugging

### Optional Helper Methods
Common patterns include:
- `get_[edr]_data()`: Retrieve raw data from EDR system
- `_parse_[edr]_output()`: Parse EDR-specific output formats
- `_convert_[edr]_to_alerts()`: Convert to EDRAlert objects

### Data Conversion
Convert EDR-specific data to `EDRAlert` objects with:
- `alert_id`: Unique identifier for the alert
- `timestamp`: When the threat was detected
- `severity`: Threat severity level
- `alert_type`: Type/category of the alert
- `description`: Human-readable description
- `additional_data`: Raw EDR data for reference

### Error Handling
- Log errors with appropriate detail level
- Return empty list instead of raising exceptions
- Use try-catch blocks around external commands
- Validate data before processing

## Usage Examples

### Basic Usage
```python
from app.services.windows.edr import EDRManager, create_edr_manager

# Create manager with VM configurations
vm_configs = [
    {
        'name': 'win10-defender',
        'antivirus': 'defender',
        'username': 'vboxuser',
        'password': '123456'
    }
]

edr_manager = create_edr_manager(vm_controller, vm_configs)

# Collect alerts
alerts = await edr_manager.collect_alerts_from_vm(
    'win10-defender', 
    start_time, 
    file_name='malware.exe'
)
```

### Direct Client Usage
```python
from app.services.windows.edr import WindowsDefenderEDRClient

client = WindowsDefenderEDRClient('win10-vm', vm_controller)
alerts = await client.get_alerts(start_time, file_name='sample.exe')
```

## Testing

When implementing a new EDR client:
1. Test with known malware samples
2. Verify alert parsing with various threat types
3. Test error handling with invalid inputs
4. Validate time range filtering
5. Check file name/hash filtering functionality

## Troubleshooting

Common issues and solutions:
- **No alerts returned**: Check EDR command execution and output parsing
- **Import errors**: Verify all imports are added to `__init__.py`
- **Configuration issues**: Ensure antivirus type matches manager mapping
- **Command timeouts**: Adjust timeout values for slow EDR operations
