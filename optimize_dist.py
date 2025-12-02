import os
import shutil
from pathlib import Path

DIST_DIR = Path("build/webcam_capture.dist")
GST_LIB = DIST_DIR / "gstreamer/lib/gstreamer-1.0"

# Essential plugins for webcam capture
KEEP_PREFIXES = [
    "gstcoreelements",
    "gstvideoconvertscale",  # Combined convert+scale plugin
    "gstvideoconvert",
    "gstvideoscale",
    "gstvideorate",
    "gstvideofilter",  # Base video filter
    "gstvideo4linux2",
    "gstdirectshow",     # Windows Camera
    "gstmediafoundation", # Windows Camera (Modern)
    "gstapp",            # For appsink
    "gsttypefindfunctions",
    "gstplayback",       # For decodebin
    "gstvideotestsrc",   # For testing
    "gstjpeg",           # MJPG decoding
    "gstpng",
    "gstisomp4",         # MP4 decoding (some cameras)
    "gstmatroska",
    "gstopengl",         # Sometimes needed for internal conversions
    "gstd3d11",          # Hardware accel
    "gstd3d12",
    "gstwasapi",         # Audio
    "gstwasapi2",
    "gstaudioconvert",
    "gstaudioresample"
]

# Exact filenames to definitely keep (base libraries)
KEEP_FILES = [
    "gstcoreelements.dll",
    "gstapp.dll",
    "gstdirectshow.dll",
    "gstvideoconvert.dll"
]

def optimize():
    if not GST_LIB.exists():
        print(f"Error: {GST_LIB} not found. Build the app first.")
        return

    print(f"Optimizing {GST_LIB}...")
    
    initial_count = 0
    deleted_count = 0
    
    for file in GST_LIB.glob("*.dll"):
        initial_count += 1
        name = file.name
        
        keep = False
        # Check explicit list
        if name in KEEP_FILES:
            keep = True
        
        # Check prefixes
        if not keep:
            for prefix in KEEP_PREFIXES:
                if name.startswith(prefix):
                    keep = True
                    break
        
        if not keep:
            print(f"  Deleting: {name}")
            try:
                os.remove(file)
                deleted_count += 1
            except Exception as e:
                print(f"    Failed to delete: {e}")
    
    print("-" * 40)
    print(f"Optimization Complete!")
    print(f"Files removed: {deleted_count}")
    print(f"Files remaining: {initial_count - deleted_count}")
    print(f"\nYour startup time should now be instantaneous.")

if __name__ == "__main__":
    optimize()

