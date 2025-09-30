 
### Basic Usage

```bash
# Install Sysmon with light configuration (recommended)
python tools\sysmon\scripts\sysmon_cli.py install win10-64-sysmon

# Install Sysmon with full configuration
python tools\sysmon\scripts\sysmon_cli.py install win10-64-sysmon --config full

# Check Sysmon status
python tools\sysmon\scripts\sysmon_cli.py status win10-64-sysmon

# Get recent Sysmon events
python tools\sysmon\scripts\sysmon_cli.py events win10-64-sysmon --max-events 50

# Update Sysmon configuration
python tools\sysmon\scripts\sysmon_cli.py update-config win10-64-sysmon --config full

# Uninstall Sysmon
python tools\sysmon\scripts\sysmon_cli.py uninstall win10-64-sysmon
```
 