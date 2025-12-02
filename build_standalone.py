"""
Nuitka build script for standalone GStreamer webcam application
Compatible with Windows 10/11
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

# Standard GStreamer installation path on Windows (MSVC)
GSTREAMER_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
OUTPUT_NAME = "webcam_capture"

def check_prerequisites():
    if not GSTREAMER_ROOT.exists():
        print(f"ERROR: GStreamer not found at {GSTREAMER_ROOT}")
        print("Please install GStreamer MSVC 64-bit binaries first.")
        print("Download: https://gstreamer.freedesktop.org/download/")
        return False
    return True

def build_nuitka():
    print("\n--- Building with Nuitka ---")
    
    # Core Nuitka command
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        # "--windows-disable-console",  # Commented out for debugging
        "--enable-plugin=numpy",
        "--output-dir=build",
        f"--output-filename={OUTPUT_NAME}.exe",
        "webcam_capture.py"
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("Nuitka build successful!")
    except subprocess.CalledProcessError as e:
        print(f"Nuitka build failed with exit code {e.returncode}")
        sys.exit(1)

def bundle_gstreamer():
    print("\n--- Bundling GStreamer Runtime ---")
    
    dist_dir = Path(f"build/{OUTPUT_NAME}.dist")
    local_gst_dir = dist_dir / "gstreamer"
    
    # Clean previous bundle
    if local_gst_dir.exists():
        shutil.rmtree(local_gst_dir)
    local_gst_dir.mkdir(parents=True)
    
    # 1. Copy BIN (contains DLLs and executables like gst-plugin-scanner)
    src_bin = GSTREAMER_ROOT / "bin"
    dst_bin = local_gst_dir / "bin"
    print(f"Copying {src_bin} -> {dst_bin}")
    shutil.copytree(src_bin, dst_bin)
    
    # 2. Copy LIB (contains plugins in lib/gstreamer-1.0)
    src_lib = GSTREAMER_ROOT / "lib"
    dst_lib = local_gst_dir / "lib"
    print(f"Copying {src_lib} -> {dst_lib}")
    shutil.copytree(src_lib, dst_lib)
    
    # 3. Clean up unnecessary files to reduce size (Optional but recommended)
    # Removing headers, .lib definition files, etc.
    print("Cleaning up dev files...")
    for root, dirs, files in os.walk(local_gst_dir):
        for file in files:
            if file.endswith(('.h', '.lib', '.pdb', '.def')):
                os.remove(os.path.join(root, file))
                
    print("GStreamer bundled successfully.")

def create_launcher_bat():
    # Optional: Create a batch file for easy testing, though the exe is now standalone
    dist_dir = Path(f"build/{OUTPUT_NAME}.dist")
    bat_path = dist_dir / "debug_launch.bat"
    
    content = f"""@echo off
echo Starting {OUTPUT_NAME}...
{OUTPUT_NAME}.exe
pause
"""
    with open(bat_path, 'w') as f:
        f.write(content)
    print(f"Created debug launcher at {bat_path}")

def main():
    if not check_prerequisites():
        sys.exit(1)
        
    build_nuitka()
    bundle_gstreamer()
    create_launcher_bat()
    
    print("\n" + "="*60)
    print("BUILD COMPLETE")
    print("="*60)
    print(f"Standalone application is ready in: build/{OUTPUT_NAME}.dist")
    print("You can zip this folder and distribute it to any Windows machine.")
    print("No GStreamer installation will be required on the target machine.")

if __name__ == "__main__":
    main()
