#!/usr/bin/env python3
"""
Simple PyInstaller Build Script - No data files
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def simple_build():
    """Simple build without data files"""
    print("🚀 Simple Build for VMM Sandbox (No data files)")
    print("=" * 55)
    
    # Project root
    project_root = Path(__file__).parent.parent.parent
    build_dir = Path(__file__).parent
    
    # Change to project root
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    try:
        # Executable name
        if platform.system() == "Windows":
            exe_name = "vmm-sandbox"
        else:
            exe_name = "vmm-sandbox"
        
        # Minimal PyInstaller command
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
            
            # Essential hidden imports only
            "--hidden-import", "uvicorn",
            "--hidden-import", "fastapi",
            "--hidden-import", "pydantic",
            "--hidden-import", "loguru",
            "--hidden-import", "yaml",
            
            # Exclude heavy modules
            "--exclude-module", "tkinter",
            "--exclude-module", "matplotlib",
            "--exclude-module", "numpy",
            "--exclude-module", "scipy",
            "--exclude-module", "pandas",
            "--exclude-module", "PIL",
            "--exclude-module", "torch",
            "--exclude-module", "tensorflow",
            
            # Main script
            "main.py"
        ]
        
        print(f"Building {exe_name}.exe...")
        print("⚠️  This may take 3-8 minutes...")
        print()
        
        # Run PyInstaller with real-time output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Show progress
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()
                # Show important progress messages
                if any(keyword in line.lower() for keyword in [
                    'info: pyinstaller:', 'analyzing', 'building', 'collecting'
                ]):
                    print(f"  {line}")
        
        return_code = process.poll()
        
        if return_code == 0:
            print("\n✅ Build completed successfully!")
            
            # Check output
            dist_dir = build_dir / "dist"
            if dist_dir.exists():
                print(f"📁 Output directory: {dist_dir}")
                for item in dist_dir.iterdir():
                    if item.is_file():
                        size = item.stat().st_size / (1024 * 1024)  # MB
                        print(f"  📄 {item.name} ({size:.1f} MB)")
            
            print("\n💡 Usage:")
            print(f"  {dist_dir / (exe_name + '.exe')}")
            print("\n📋 Note: You'll need to copy config.yaml.example manually")
            
            return True
        else:
            print(f"\n❌ Build failed with return code: {return_code}")
            return False
        
    except KeyboardInterrupt:
        print("\n⚠️ Build interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def main():
    """Main function"""
    print("🛡️ VMM Sandbox - Simple Build")
    print("=" * 40)
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Create directories
    build_dir = Path(__file__).parent
    (build_dir / "dist").mkdir(exist_ok=True)
    (build_dir / "work").mkdir(exist_ok=True)
    (build_dir / "specs").mkdir(exist_ok=True)
    
    # Build
    success = simple_build()
    
    if success:
        print("\n🎉 Build completed!")
    else:
        print("\n❌ Build failed!")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(1)
