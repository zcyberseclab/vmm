#!/usr/bin/env python3
"""
GitHub Actions Build Script for VMM Sandbox
Optimized for CI/CD automated releases
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def github_build():
    """Build executable for GitHub Actions"""
    print("GitHub Actions Build for VMM Sandbox")
    print("=" * 50)
    
    # Project root
    project_root = Path(__file__).parent.parent.parent
    build_dir = Path(__file__).parent
    
    # Change to project root
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    try:
        # Determine executable name
        if platform.system() == "Windows":
            exe_name = "vmm-sandbox"
            exe_file = "vmm-sandbox.exe"
        else:
            exe_name = "vmm-sandbox"
            exe_file = "vmm-sandbox"
        
        print(f"Building {exe_file} for {platform.system()}...")

        # PyInstaller command optimized for CI
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", exe_name,
            "--distpath", str(build_dir / "dist"),
            "--workpath", str(build_dir / "work"),
            "--specpath", str(build_dir / "specs"),
            "--clean",
            "--noconfirm",
            "--console",
            "--optimize", "2",  # Optimize for size
            
            # Essential hidden imports
            "--hidden-import", "uvicorn",
            "--hidden-import", "fastapi",
            "--hidden-import", "pydantic",
            "--hidden-import", "loguru",
            "--hidden-import", "yaml",
            "--hidden-import", "aiofiles",
            
            # Exclude unnecessary modules for smaller size
            "--exclude-module", "tkinter",
            "--exclude-module", "matplotlib",
            "--exclude-module", "numpy",
            "--exclude-module", "scipy",
            "--exclude-module", "pandas",
            "--exclude-module", "PIL",
            "--exclude-module", "cv2",
            "--exclude-module", "torch",
            "--exclude-module", "tensorflow",
            "--exclude-module", "jupyter",
            "--exclude-module", "notebook",
            "--exclude-module", "IPython",
            
            # Main script
            "main.py"
        ]
        
        print("Running PyInstaller...")

        # Run PyInstaller with minimal output for CI
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        print("Build completed successfully!")
        
        # Verify output
        dist_dir = build_dir / "dist"
        exe_path = dist_dir / exe_file
        
        if exe_path.exists():
            size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"Generated: {exe_file} ({size:.1f} MB)")

            # Set executable permissions on Linux
            if platform.system() != "Windows":
                os.chmod(exe_path, 0o755)
                print("Set executable permissions")

            return True
        else:
            print("ERROR: Executable not found!")
            return False
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout[-500:])  # Last 500 chars
        if e.stderr:
            print("STDERR:", e.stderr[-500:])  # Last 500 chars
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def prepare_release_artifacts():
    """Prepare release artifacts for GitHub"""
    print("\nPreparing release artifacts...")
    
    build_dir = Path(__file__).parent
    project_root = build_dir.parent.parent
    dist_dir = build_dir / "dist"
    
    if platform.system() == "Windows":
        exe_file = "vmm-sandbox.exe"
    else:
        exe_file = "vmm-sandbox"
    
    exe_path = dist_dir / exe_file
    
    if not exe_path.exists():
        print("ERROR: Executable not found for artifact preparation")
        return False
    
    # Create artifacts directory
    artifacts_dir = build_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    # Copy executable
    shutil.copy2(exe_path, artifacts_dir / exe_file)
    
    # Copy essential files
    essential_files = [
        "config.yaml.example",
        "README.md",
        "LICENSE"
    ]
    
    for file_name in essential_files:
        src_file = project_root / file_name
        if src_file.exists():
            shutil.copy2(src_file, artifacts_dir / file_name)
            print(f"Copied {file_name}")

    print(f"Release artifacts prepared in {artifacts_dir}")
    return True

def main():
    """Main function for GitHub Actions"""
    print("VMM Sandbox - GitHub Actions Build")
    print("=" * 45)

    # Check environment
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Working directory: {os.getcwd()}")

    # Install PyInstaller if needed
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("PyInstaller installed")
    
    # Create build directories
    build_dir = Path(__file__).parent
    (build_dir / "dist").mkdir(exist_ok=True)
    (build_dir / "work").mkdir(exist_ok=True)
    (build_dir / "specs").mkdir(exist_ok=True)
    
    # Build executable
    if github_build():
        # Prepare artifacts
        if prepare_release_artifacts():
            print("\nGitHub Actions build completed successfully!")
            return True
        else:
            print("\nFailed to prepare release artifacts")
            return False
    else:
        print("\nGitHub Actions build failed!")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nBuild interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
