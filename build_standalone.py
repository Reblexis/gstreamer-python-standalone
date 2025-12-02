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
ENTRY_SCRIPT = "settings_gui.py"

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
    # PyGObject requires several standard library modules
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        # "--windows-disable-console",  # Commented out for debugging
        "--enable-plugin=numpy",
        "--enable-plugin=pyside6",
        "--include-module=asyncio",  # Required by PyGObject
        "--include-module=optparse",  # Required by gi._option
        "--include-module=gettext",  # Often needed by gi
        "--include-module=locale",  # Often needed by gi
        "--include-package=xml",  # Sometimes needed by gi
        "--include-package=ctypes",  # Required by gi
        "--output-dir=build",
        f"--output-filename={OUTPUT_NAME}.exe",
        ENTRY_SCRIPT
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("Nuitka build successful!")
    except subprocess.CalledProcessError as e:
        print(f"Nuitka build failed with exit code {e.returncode}")
        sys.exit(1)
    
    # Rename dist folder to match OUTPUT_NAME
    entry_name = Path(ENTRY_SCRIPT).stem
    src_dist = Path(f"build/{entry_name}.dist")
    dst_dist = Path(f"build/{OUTPUT_NAME}.dist")
    
    if src_dist.exists() and src_dist != dst_dist:
        if dst_dist.exists():
            shutil.rmtree(dst_dist)
        src_dist.rename(dst_dist)
        print(f"Renamed {src_dist} -> {dst_dist}")

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
    
    # 3. Copy PyGObject (gi module) to dist root
    # This is required because PyGObject is not pip-installable on Windows
    # and must come from the GStreamer installation
    src_gi = GSTREAMER_ROOT / "lib" / "site-packages" / "gi"
    dst_gi = dist_dir / "gi"
    if src_gi.exists():
        print(f"Copying PyGObject: {src_gi} -> {dst_gi}")
        if dst_gi.exists():
            shutil.rmtree(dst_gi)
        shutil.copytree(src_gi, dst_gi)
    
    # Also copy cairo if present (sometimes needed by gi)
    src_cairo = GSTREAMER_ROOT / "lib" / "site-packages" / "cairo"
    dst_cairo = dist_dir / "cairo"
    if src_cairo.exists():
        print(f"Copying cairo: {src_cairo} -> {dst_cairo}")
        if dst_cairo.exists():
            shutil.rmtree(dst_cairo)
        shutil.copytree(src_cairo, dst_cairo)
    
    # 4. Clean up unnecessary files to reduce size (Optional but recommended)
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
