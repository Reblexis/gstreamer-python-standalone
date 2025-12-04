"""
Nuitka build script for standalone GStreamer webcam application
Linux version - bundles system GStreamer for portable deployment
"""
import os
import sys
import shutil
import subprocess
import glob
from pathlib import Path

OUTPUT_NAME = "webcam_capture"
ENTRY_SCRIPT = "settings_gui.py"

# Common library paths on Linux (architecture-dependent)
LIB_PATHS = [
    Path("/usr/lib/x86_64-linux-gnu"),
    Path("/usr/lib64"),
    Path("/usr/lib"),
]


def find_lib_path():
    """Find the system library path containing GStreamer."""
    for path in LIB_PATHS:
        gst_plugin_path = path / "gstreamer-1.0"
        if gst_plugin_path.exists():
            return path
    return None


def check_prerequisites():
    """Check that required packages are installed."""
    lib_path = find_lib_path()
    if lib_path is None:
        print("ERROR: GStreamer not found. Please install it:")
        print("  sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good \\")
        print("                   gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \\")
        print("                   gstreamer1.0-tools libgstreamer1.0-dev")
        return False
    
    # Check for PyGObject
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
    except (ImportError, ValueError) as e:
        print(f"ERROR: PyGObject/GStreamer bindings not found: {e}")
        print("  Install with: pip install PyGObject")
        print("  Or: sudo apt install python3-gi gir1.2-gst-plugins-base-1.0")
        return False
    
    print(f"✓ GStreamer found at {lib_path}")
    return True


def build_nuitka():
    """Build the application with Nuitka."""
    print("\n--- Building with Nuitka ---")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=numpy",
        "--enable-plugin=pyside6",
        "--include-module=asyncio",
        "--include-module=optparse",
        "--include-module=gettext",
        "--include-module=locale",
        "--include-package=xml",
        "--include-package=ctypes",
        "--output-dir=build",
        f"--output-filename={OUTPUT_NAME}",
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
    """Bundle GStreamer runtime libraries and plugins."""
    print("\n--- Bundling GStreamer Runtime ---")
    
    lib_path = find_lib_path()
    dist_dir = Path(f"build/{OUTPUT_NAME}.dist")
    gst_target = dist_dir / "gstreamer"
    
    if gst_target.exists():
        shutil.rmtree(gst_target)
    
    # Create directory structure
    (gst_target / "lib").mkdir(parents=True)
    (gst_target / "plugins").mkdir(parents=True)
    (gst_target / "bin").mkdir(parents=True)
    (gst_target / "lib" / "girepository-1.0").mkdir(parents=True)
    
    # 1. Copy GStreamer core libraries
    print("Copying GStreamer libraries...")
    gst_libs = list(lib_path.glob("libgst*.so*"))
    gst_libs += list(lib_path.glob("libglib*.so*"))
    gst_libs += list(lib_path.glob("libgobject*.so*"))
    gst_libs += list(lib_path.glob("libgio*.so*"))
    gst_libs += list(lib_path.glob("libgmodule*.so*"))
    gst_libs += list(lib_path.glob("liborc*.so*"))
    
    for lib in gst_libs:
        if lib.is_file():
            dest = gst_target / "lib" / lib.name
            if not dest.exists():
                shutil.copy2(lib, dest, follow_symlinks=False)
    
    # 2. Copy GStreamer plugins
    print("Copying GStreamer plugins...")
    plugin_src = lib_path / "gstreamer-1.0"
    if plugin_src.exists():
        for plugin in plugin_src.glob("*.so"):
            shutil.copy2(plugin, gst_target / "plugins" / plugin.name)
    
    # 3. Copy plugin scanner
    print("Copying plugin scanner...")
    scanner_paths = [
        lib_path / "gstreamer1.0" / "gstreamer-1.0" / "gst-plugin-scanner",
        lib_path / "gstreamer-1.0" / "gst-plugin-scanner",
        Path("/usr/libexec/gstreamer-1.0/gst-plugin-scanner"),
    ]
    for scanner in scanner_paths:
        if scanner.exists():
            shutil.copy2(scanner, gst_target / "bin" / "gst-plugin-scanner")
            os.chmod(gst_target / "bin" / "gst-plugin-scanner", 0o755)
            print(f"  Found scanner at {scanner}")
            break
    
    # 4. Copy GI typelibs (required for PyGObject to find GStreamer)
    print("Copying GI typelibs...")
    typelib_src = lib_path / "girepository-1.0"
    if typelib_src.exists():
        # Copy GStreamer-related typelibs
        patterns = ["Gst-1.0.typelib", "GstBase-1.0.typelib", "GstVideo-1.0.typelib",
                    "GstAudio-1.0.typelib", "GstApp-1.0.typelib", "GstPbutils-1.0.typelib",
                    "GLib-2.0.typelib", "GObject-2.0.typelib", "Gio-2.0.typelib",
                    "GModule-2.0.typelib"]
        for pattern in patterns:
            for typelib in typelib_src.glob(pattern):
                shutil.copy2(typelib, gst_target / "lib" / "girepository-1.0" / typelib.name)
    
    print("GStreamer bundled successfully.")




def main():
    if sys.platform != 'linux':
        print("ERROR: This build script is for Linux only.")
        print("Use build_standalone.py for Windows.")
        sys.exit(1)
    
    if not check_prerequisites():
        sys.exit(1)
    
    build_nuitka()
    bundle_gstreamer()
    
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    dist_dir = Path(f"build/{OUTPUT_NAME}.dist")
    print(f"Standalone application is ready in: {dist_dir}")
    print(f"\nTo run: ./{dist_dir}/{OUTPUT_NAME}")
    print("\nYou can tar this folder and distribute it.")
    print("Run optimize_dist_linux.py to reduce size before distribution.")


if __name__ == "__main__":
    main()

