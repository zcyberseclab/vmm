#!/usr/bin/env python3
"""
Release script for VirtualBox EDR Malware Analysis System

This script helps automate the release process by:
1. Updating version numbers
2. Creating git tags
3. Pushing to GitHub to trigger release workflow
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"Error output: {result.stderr}")
        sys.exit(1)
    return result


def update_version_in_file(file_path, old_version, new_version):
    """Update version in a specific file"""
    if not file_path.exists():
        print(f"Warning: {file_path} not found, skipping...")
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # Update version patterns
    patterns = [
        (rf'__version__ = ["\'].*?["\']', f'__version__ = "{new_version}"'),
        (rf'version=["\'].*?["\']', f'version="{new_version}"'),
        (rf'version: ["\'].*?["\']', f'version: "{new_version}"'),
    ]
    
    updated = False
    for pattern, replacement in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            updated = True
    
    if updated:
        file_path.write_text(content, encoding='utf-8')
        print(f"Updated version in {file_path}")
    else:
        print(f"No version pattern found in {file_path}")


def get_current_version():
    """Get current version from app/__init__.py"""
    init_file = Path("app/__init__.py")
    if not init_file.exists():
        return "0.0.0"
    
    content = init_file.read_text()
    match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "0.0.0"


def validate_version(version):
    """Validate version format (semantic versioning)"""
    pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?$'
    return re.match(pattern, version) is not None


def main():
    parser = argparse.ArgumentParser(description="Release script for VMM")
    parser.add_argument("version", help="New version number (e.g., 1.0.1)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually doing it")
    parser.add_argument("--no-push", action="store_true", help="Don't push to remote repository")
    
    args = parser.parse_args()
    
    # Validate version format
    if not validate_version(args.version):
        print("Error: Version must follow semantic versioning (e.g., 1.0.1)")
        sys.exit(1)
    
    # Get current version
    current_version = get_current_version()
    print(f"Current version: {current_version}")
    print(f"New version: {args.version}")
    
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
    
    # Check if we're in the right directory
    if not Path("app").exists() or not Path("main.py").exists():
        print("Error: This script must be run from the project root directory")
        sys.exit(1)
    
    # Check git status
    result = run_command("git status --porcelain")
    if result.stdout.strip() and not args.dry_run:
        print("Error: Working directory is not clean. Please commit or stash changes first.")
        sys.exit(1)
    
    # Update version in files
    files_to_update = [
        Path("app/__init__.py"),
        Path("main.py"),
    ]
    
    if not args.dry_run:
        for file_path in files_to_update:
            update_version_in_file(file_path, current_version, args.version)
    else:
        print("Would update version in:")
        for file_path in files_to_update:
            print(f"  - {file_path}")
    
    # Git operations
    tag_name = f"v{args.version}"
    
    if not args.dry_run:
        # Add and commit version changes
        run_command("git add .")
        run_command(f'git commit -m "Bump version to {args.version}"')
        
        # Create and push tag
        run_command(f'git tag -a {tag_name} -m "Release {tag_name}"')
        
        if not args.no_push:
            run_command("git push origin main")
            run_command(f"git push origin {tag_name}")
            print(f"\n✅ Release {tag_name} has been created and pushed!")
            print("GitHub Actions will now build and publish the release.")
        else:
            print(f"\n✅ Release {tag_name} has been created locally.")
            print("Run 'git push origin main && git push origin {tag_name}' to publish.")
    else:
        print(f"\nWould create and push tag: {tag_name}")
        print("Would run:")
        print("  git add .")
        print(f"  git commit -m 'Bump version to {args.version}'")
        print(f"  git tag -a {tag_name} -m 'Release {tag_name}'")
        if not args.no_push:
            print("  git push origin main")
            print(f"  git push origin {tag_name}")


if __name__ == "__main__":
    main()
