#!/usr/bin/env python3
"""
Setup script for VirtualBox EDR Malware Analysis System
"""

from setuptools import setup, find_packages
from pathlib import Path
import re

# Read version from app/__init__.py
def get_version():
    init_file = Path("app/__init__.py")
    if init_file.exists():
        content = init_file.read_text()
        match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    return "1.0.0"

# Read long description from README
def get_long_description():
    readme_file = Path("README.md")
    if readme_file.exists():
        return readme_file.read_text(encoding='utf-8')
    return ""

# Read requirements
def get_requirements():
    req_file = Path("requirements.txt")
    if req_file.exists():
        return req_file.read_text().strip().split('\n')
    return []

setup(
    name="vmm-edr-analysis",
    version=get_version(),
    author="zcyberseclab",
    author_email="support@zcyberseclab.com",
    description="VirtualBox EDR Malware Analysis System",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/zcyberseclab/vmm",
    project_urls={
        "Bug Reports": "https://github.com/zcyberseclab/vmm/issues",
        "Source": "https://github.com/zcyberseclab/vmm",
        "Documentation": "https://github.com/zcyberseclab/vmm#readme",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Testing",
    ],
    python_requires=">=3.11",
    install_requires=get_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "isort>=5.0",
            "flake8>=6.0",
            "bandit>=1.7",
            "safety>=2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "vmm-server=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": [
            "services/windows/sysmon/configs/*.xml",
            "services/windows/sysmon/scripts/*.py",
        ],
    },
    zip_safe=False,
    keywords="malware analysis edr virtualbox sysmon security",
)
