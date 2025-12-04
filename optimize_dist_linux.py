"""
Optimize the Linux standalone distribution by removing unused GStreamer plugins.
This reduces size and improves startup time.
"""
import os
from pathlib import Path

DIST_DIR = Path("build/webcam_capture.dist")
GST_PLUGINS = DIST_DIR / "gstreamer/plugins"

# Essential plugins for webcam capture on Linux
# These are the plugin library names (without lib prefix and .so suffix)
KEEP_PREFIXES = [
    # Core
    "gstcoreelements",
    "gsttypefindfunctions",
    "gstplayback",       # decodebin
    "gstapp",            # appsink
    
    # Video processing
    "gstvideoconvertscale",
    "gstvideoconvert",
    "gstvideoscale",
    "gstvideorate",
    "gstvideofilter",
    "gstvideoparsersbad",
    
    # Camera sources
    "gstvideo4linux2",   # v4l2src - the main Linux camera source
    "gstv4l2codecs",     # V4L2 hardware codecs
    
    # Common formats
    "gstjpeg",           # MJPG decoding (common webcam format)
    "gstpng",
    "gstisomp4",
    "gstmatroska",
    "gstavi",
    
    # libav for decoding
    "gstlibav",
    
    # OpenGL (optional, for GPU support later)
    "gstopengl",
    
    # Audio (if needed)
    "gstaudioconvert",
    "gstaudioresample",
    "gstpulseaudio",
    "gstalsa",
    
    # Autodetect
    "gstautodetect",
]


def optimize():
    if not GST_PLUGINS.exists():
        print(f"Error: {GST_PLUGINS} not found. Build the app first with build_standalone_linux.py")
        return
    
    print(f"Optimizing {GST_PLUGINS}...")
    
    initial_count = 0
    deleted_count = 0
    initial_size = 0
    deleted_size = 0
    
    for plugin in GST_PLUGINS.glob("*.so"):
        initial_count += 1
        file_size = plugin.stat().st_size
        initial_size += file_size
        
        name = plugin.stem  # Remove .so extension
        if name.startswith("lib"):
            name = name[3:]  # Remove lib prefix
        
        keep = False
        for prefix in KEEP_PREFIXES:
            if name.startswith(prefix):
                keep = True
                break
        
        if not keep:
            print(f"  Deleting: {plugin.name} ({file_size // 1024} KB)")
            try:
                os.remove(plugin)
                deleted_count += 1
                deleted_size += file_size
            except Exception as e:
                print(f"    Failed to delete: {e}")
    
    print("-" * 50)
    print("Optimization Complete!")
    print(f"Plugins removed: {deleted_count}")
    print(f"Plugins remaining: {initial_count - deleted_count}")
    print(f"Space saved: {deleted_size // (1024 * 1024)} MB")
    print(f"\nStartup time should now be much faster.")


if __name__ == "__main__":
    optimize()

