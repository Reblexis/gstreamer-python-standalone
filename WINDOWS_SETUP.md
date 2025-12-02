# Windows GStreamer Setup Guide

## Step 1: Download GStreamer

Visit: https://gstreamer.freedesktop.org/download/

### Required Downloads (MSVC version, 64-bit):

1. **Runtime installer:**
   - `gstreamer-1.0-msvc-x86_64-1.22.0.msi`

2. **Development installer:**
   - `gstreamer-1.0-devel-msvc-x86_64-1.22.0.msi`

## Step 2: Install GStreamer

1. Run the runtime installer
   - Choose "Complete" installation
   - Default path: `C:\gstreamer\1.0\msvc_x86_64\`

2. Run the development installer
   - Same path as runtime

## Step 3: Set Environment Variables

### Option A: Manual (Persistent)

1. Open System Properties → Environment Variables
2. Edit `Path` (User or System)
3. Add: `C:\gstreamer\1.0\msvc_x86_64\bin`
4. Create new variable:
   - Name: `GST_PLUGIN_PATH`
   - Value: `C:\gstreamer\1.0\msvc_x86_64\lib\gstreamer-1.0`

**Restart your terminal/IDE after this**

### Option B: Script (Temporary, for testing)

Create `setup_env.bat`:
```batch
@echo off
set GSTREAMER_ROOT=C:\gstreamer\1.0\msvc_x86_64
set PATH=%GSTREAMER_ROOT%\bin;%PATH%
set GST_PLUGIN_PATH=%GSTREAMER_ROOT%\lib\gstreamer-1.0
echo GStreamer environment configured!
cmd
```

Run this before using Python scripts.

## Step 4: Install PyGObject (GStreamer Python Bindings)

### Method 1: pip (may not work on all Windows setups)
```bash
pip install PyGObject
```

### Method 2: Pre-built wheels (recommended)

Download from: https://github.com/pygobject/pygobject/releases

Or use conda:
```bash
conda install -c conda-forge pygobject
```

### Method 3: MSYS2 (most reliable)

1. Install MSYS2: https://www.msys2.org/
2. Open MSYS2 MINGW64 terminal
3. Run:
```bash
pacman -S mingw-w64-x86_64-python-gobject
pacman -S mingw-w64-x86_64-gstreamer
```

## Step 5: Verify Installation

Create `test_gstreamer.py`:

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)
print(f"GStreamer version: {Gst.version_string()}")

# Test pipeline
pipeline = Gst.parse_launch("videotestsrc ! autovideosink")
pipeline.set_state(Gst.State.PLAYING)
print("If you see a test pattern, GStreamer is working!")

# Press Ctrl+C to stop
try:
    import time
    time.sleep(5)
except KeyboardInterrupt:
    pass

pipeline.set_state(Gst.State.NULL)
```

Run:
```bash
python test_gstreamer.py
```

## Step 6: Test Webcam

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

# Windows-specific camera source
pipeline_str = "ksvideosrc device-index=0 ! autovideosink"
pipeline = Gst.parse_launch(pipeline_str)
pipeline.set_state(Gst.State.PLAYING)

print("Camera test - Press Ctrl+C to stop")

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

pipeline.set_state(Gst.State.NULL)
```

## Troubleshooting

### Error: "No module named 'gi'"
- PyGObject not installed correctly
- Try Method 3 (MSYS2) above

### Error: "Could not load GStreamer"
- Environment variables not set
- Restart terminal after setting variables
- Verify `gst-launch-1.0.exe` exists in bin folder

### Error: "No cameras found"
- Try `dshowvideosrc` instead of `ksvideosrc`
- List cameras: `gst-device-monitor-1.0`

### Camera lag/freeze
- Reduce resolution or FPS
- Add `max-buffers=1 drop=true` to appsink


