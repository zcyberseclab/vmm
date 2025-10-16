#!/usr/bin/env python3
"""
Sysmon CLI Tool for EDR Analysis VMs
Command-line interface for managing Sysmon on virtual machines.
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path
from typing import Optional

# Add parent directories to path to import modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from app.services.windows.sysmon.manager import SysmonManager, SysmonConfigType, SysmonStatus
from loguru import logger

# Try to import VM controller, create one if available
try:
    from app.services.vm_controller import create_vm_controller
    VM_CONTROLLER_AVAILABLE = True
except ImportError:
    VM_CONTROLLER_AVAILABLE = False
    create_vm_controller = None


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    logger.remove()  # Remove default handler
    
    if verbose:
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    else:
        logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def create_sysmon_manager():
    """Create SysmonManager with VM controller if available"""
    if VM_CONTROLLER_AVAILABLE:
        try:
            vm_controller = create_vm_controller('virtualbox')
            return SysmonManager(vm_controller)
        except Exception as e:
            print(f"⚠️  Warning: Failed to create VM controller: {str(e)}")
            print("Continuing without VM controller (limited functionality)")
            return SysmonManager()
    else:
        print("⚠️  Warning: VM controller not available (limited functionality)")
        return SysmonManager()


async def install_command(args):
    """Handle install command"""
    sysmon_manager = create_sysmon_manager()
    
    # Determine config type
    config_type = SysmonConfigType.LIGHT
    if args.config == "full":
        config_type = SysmonConfigType.FULL
    elif args.config == "custom":
        config_type = SysmonConfigType.CUSTOM
    
    success, message = await sysmon_manager.install_sysmon(
        vm_name=args.vm_name,
        username=args.username,
        password=args.password,
        config_type=config_type,
        custom_config_path=args.custom_config,
        force_reinstall=args.force
    )
    
    if success:
        print(f"✅ Success: {message}")
        return 0
    else:
        print(f"❌ Error: {message}")
        return 1


async def uninstall_command(args):
    """Handle uninstall command"""
    sysmon_manager = create_sysmon_manager()
    
    success, message = await sysmon_manager.uninstall_sysmon(
        vm_name=args.vm_name,
        username=args.username,
        password=args.password
    )
    
    if success:
        print(f"✅ Success: {message}")
        return 0
    else:
        print(f"❌ Error: {message}")
        return 1


async def status_command(args):
    """Handle status command"""
    sysmon_manager = create_sysmon_manager()
    
    status, details = await sysmon_manager.get_sysmon_status(
        vm_name=args.vm_name,
        username=args.username,
        password=args.password
    )
    
    # Status icons
    status_icons = {
        SysmonStatus.NOT_INSTALLED: "❌",
        SysmonStatus.INSTALLED: "⚠️",
        SysmonStatus.RUNNING: "✅",
        SysmonStatus.STOPPED: "🛑",
        SysmonStatus.ERROR: "💥"
    }
    
    icon = status_icons.get(status, "❓")
    print(f"{icon} Sysmon Status: {status.value}")
    print(f"Details: {details}")
    
    if args.json:
        result = {
            "vm_name": args.vm_name,
            "status": status.value,
            "details": details
        }
        print(json.dumps(result, indent=2))
    
    return 0


async def update_config_command(args):
    """Handle update-config command"""
    sysmon_manager = create_sysmon_manager()
    
    # Determine config type
    config_type = SysmonConfigType.LIGHT
    if args.config == "full":
        config_type = SysmonConfigType.FULL
    elif args.config == "custom":
        config_type = SysmonConfigType.CUSTOM
    
    success, message = await sysmon_manager.update_sysmon_config(
        vm_name=args.vm_name,
        config_type=config_type,
        custom_config_path=args.custom_config,
        username=args.username,
        password=args.password
    )
    
    if success:
        print(f"✅ Success: {message}")
        return 0
    else:
        print(f"❌ Error: {message}")
        return 1


async def events_command(args):
    """Handle events command"""
    sysmon_manager = create_sysmon_manager()
    
    success, events = await sysmon_manager.get_sysmon_events(
        vm_name=args.vm_name,
        max_events=args.max_events,
        username=args.username,
        password=args.password
    )
    
    if not success:
        print("❌ Error: Failed to retrieve Sysmon events")
        return 1
    
    if not events:
        print("ℹ️  No Sysmon events found")
        return 0
    
    print(f"📊 Found {len(events)} Sysmon events:")
    print()
    
    if args.json:
        print(json.dumps(events, indent=2, default=str))
    else:
        for i, event in enumerate(events[:args.max_events], 1):
            print(f"Event {i}:")
            print(f"  Time: {event.get('TimeCreated', 'Unknown')}")
            print(f"  ID: {event.get('Id', 'Unknown')}")
            print(f"  Level: {event.get('LevelDisplayName', 'Unknown')}")
            print(f"  Message: {event.get('Message', 'No message')[:200]}...")
            print()
    
    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Sysmon CLI Tool for EDR Analysis VMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install Sysmon with light configuration
  python sysmon_cli.py install win10-64-defender

  # Install Sysmon with full configuration
  python sysmon_cli.py install win10-64-defender --config full

  # Check Sysmon status
  python sysmon_cli.py status win10-64-defender

  # Get recent Sysmon events
  python sysmon_cli.py events win10-64-defender --max-events 50

  # Uninstall Sysmon
  python sysmon_cli.py uninstall win10-64-defender
        """
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Install command
    install_parser = subparsers.add_parser("install", help="Install Sysmon on VM")
    install_parser.add_argument("vm_name", help="Name of the virtual machine")
    install_parser.add_argument("-u", "--username", default="vboxuser", help="VM username (default: vboxuser)")
    install_parser.add_argument("-p", "--password", default="123456", help="VM password (default: 123456)")
    install_parser.add_argument("-c", "--config", choices=["light", "full", "custom"], default="light", help="Configuration type (default: light)")
    install_parser.add_argument("--custom-config", help="Path to custom configuration file (required if config=custom)")
    install_parser.add_argument("-f", "--force", action="store_true", help="Force reinstallation")
    
    # Uninstall command
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall Sysmon from VM")
    uninstall_parser.add_argument("vm_name", help="Name of the virtual machine")
    uninstall_parser.add_argument("-u", "--username", default="vboxuser", help="VM username (default: vboxuser)")
    uninstall_parser.add_argument("-p", "--password", default="123456", help="VM password (default: 123456)")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check Sysmon status on VM")
    status_parser.add_argument("vm_name", help="Name of the virtual machine")
    status_parser.add_argument("-u", "--username", default="vboxuser", help="VM username (default: vboxuser)")
    status_parser.add_argument("-p", "--password", default="123456", help="VM password (default: 123456)")
    status_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # Update config command
    update_parser = subparsers.add_parser("update-config", help="Update Sysmon configuration on VM")
    update_parser.add_argument("vm_name", help="Name of the virtual machine")
    update_parser.add_argument("-u", "--username", default="vboxuser", help="VM username (default: vboxuser)")
    update_parser.add_argument("-p", "--password", default="123456", help="VM password (default: 123456)")
    update_parser.add_argument("-c", "--config", choices=["light", "full", "custom"], default="light", help="Configuration type (default: light)")
    update_parser.add_argument("--custom-config", help="Path to custom configuration file (required if config=custom)")
    
    # Events command
    events_parser = subparsers.add_parser("events", help="Get Sysmon events from VM")
    events_parser.add_argument("vm_name", help="Name of the virtual machine")
    events_parser.add_argument("-u", "--username", default="vboxuser", help="VM username (default: vboxuser)")
    events_parser.add_argument("-p", "--password", default="123456", help="VM password (default: 123456)")
    events_parser.add_argument("-n", "--max-events", type=int, default=100, help="Maximum number of events to retrieve (default: 100)")
    events_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate custom config argument
    if hasattr(args, 'config') and args.config == "custom" and not args.custom_config:
        print("❌ Error: --custom-config is required when using --config custom")
        return 1
    
    # Execute command
    try:
        if args.command == "install":
            return asyncio.run(install_command(args))
        elif args.command == "uninstall":
            return asyncio.run(uninstall_command(args))
        elif args.command == "status":
            return asyncio.run(status_command(args))
        elif args.command == "update-config":
            return asyncio.run(update_config_command(args))
        elif args.command == "events":
            return asyncio.run(events_command(args))
        else:
            print(f"❌ Error: Unknown command: {args.command}")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
