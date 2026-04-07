#!/usr/bin/env python
"""
Build script for creating a robust executable of the NGO Accounting System.
Usage: python build_exe.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def log(message: str, level: str = "INFO"):
    """Print a formatted log message."""
    print(f"[{level}] {message}")

def check_dependencies():
    """Check if required packages are installed."""
    required_packages = ["pyinstaller", "fastapi", "uvicorn", "jinja2", "passlib", "bcrypt"]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        log(f"Missing packages: {', '.join(missing)}", "WARNING")
        log("Installing missing packages...", "INFO")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        log("Packages installed successfully", "INFO")

def clean_build_artifacts():
    """Remove old build artifacts."""
    log("Cleaning old build artifacts...", "INFO")
    dirs_to_remove = ["build", "dist", "build_robust"]
    
    for dir_name in dirs_to_remove:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            log(f"Removed {dir_name}", "INFO")

def build_exe():
    """Build the executable using PyInstaller."""
    log("Starting PyInstaller build process...", "INFO")
    
    spec_file = "build_robust.spec"
    if not Path(spec_file).exists():
        log(f"Spec file not found: {spec_file}", "ERROR")
        return False
    
    try:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            spec_file,
            "--clean",
            "--onedir",
        ]
        
        log(f"Running command: {' '.join(cmd)}", "INFO")
        result = subprocess.run(cmd, check=True, capture_output=False)
        
        if result.returncode == 0:
            log("Build completed successfully!", "SUCCESS")
            return True
        else:
            log(f"Build failed with return code {result.returncode}", "ERROR")
            return False
            
    except subprocess.CalledProcessError as e:
        log(f"Build failed: {e}", "ERROR")
        return False
    except Exception as e:
        log(f"Unexpected error during build: {e}", "ERROR")
        return False

def verify_build():
    """Verify the build was successful."""
    exe_path = Path("dist/UROMI/UROMI.exe")
    
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        log(f"✓ Executable created: {exe_path} ({size_mb:.2f} MB)", "SUCCESS")
        
        # Check for static and templates directories
        static_path = Path("dist/UROMI/static")
        templates_path = Path("dist/UROMI/templates")
        
        if static_path.exists():
            log(f"✓ Static directory included", "SUCCESS")
        else:
            log(f"✗ Static directory missing", "WARNING")
        
        if templates_path.exists():
            log(f"✓ Templates directory included", "SUCCESS")
        else:
            log(f"✗ Templates directory missing", "WARNING")
        
        return True
    else:
        log(f"Executable not found at {exe_path}", "ERROR")
        return False

def main():
    """Main build process."""
    log("NGO Accounting System - Windows EXE Builder", "INFO")
    log("=" * 60, "INFO")
    
    os.chdir(Path(__file__).parent)
    
    # Step 1: Check dependencies
    log("\n[Step 1/4] Checking dependencies...", "INFO")
    try:
        check_dependencies()
    except Exception as e:
        log(f"Dependency check failed: {e}", "ERROR")
        return False
    
    # Step 2: Clean old artifacts
    log("\n[Step 2/4] Cleaning old artifacts...", "INFO")
    try:
        clean_build_artifacts()
    except Exception as e:
        log(f"Cleanup failed: {e}", "ERROR")
    
    # Step 3: Build executable
    log("\n[Step 3/4] Building executable...", "INFO")
    if not build_exe():
        return False
    
    # Step 4: Verify build
    log("\n[Step 4/4] Verifying build...", "INFO")
    if not verify_build():
        return False
    
    log("\n" + "=" * 60, "INFO")
    log("✓ Build process completed successfully!", "SUCCESS")
    log("Your executable is ready at: dist/UROMI/UROMI.exe", "SUCCESS")
    log("=" * 60, "INFO")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
