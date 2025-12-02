# GStreamer Webcam Deployment Guide for Windows with Nuitka

## Prerequisites

### 1. Install GStreamer Runtime on Development Machine

Download and install from: https://gstreamer.freedesktop.org/download/

**Required installers (both MSVC versions):**
- `gstreamer-1.0-msvc-x86_64-1.22.0.msi` (Runtime)
- `gstreamer-1.0-devel-msvc-x86_64-1.22.0.msi` (Development)

**Installation path (default):**
```
C:\gstreamer\1.0\msvc_x86_64\
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note:** PyGObject on Windows requires GTK. Install via:
```bash
pip install --upgrade --force-reinstall pygobject
```

If that fails, use MSYS2 or pre-built wheels from:
https://github.com/pygobject/pygobject/releases

### 3. Install Nuitka

```bash
pip install nuitka
```

## Testing Before Deployment

Run the script to verify it works:
```bash
python webcam_capture.py
```

## Nuitka Compilation

### Basic Compilation

```bash
nuitka --standalone --windows-disable-console webcam_capture.py
```

### Include GStreamer Dependencies

Create `build.py`:

```python
import os
import shutil
from pathlib import Path

GSTREAMER_PATH = r"C:\gstreamer\1.0\msvc_x86_64"

os.system(
    "nuitka "
    "--standalone "
    "--windows-disable-console "
    "--enable-plugin=numpy "
    "webcam_capture.py"
)

# Copy GStreamer runtime
dist_folder = Path("webcam_capture.dist")
gst_folder = dist_folder / "gstreamer"

if not gst_folder.exists():
    gst_folder.mkdir(parents=True)

# Copy essential GStreamer files
for folder in ["bin", "lib"]:
    src = Path(GSTREAMER_PATH) / folder
    dst = gst_folder / folder
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)

print("Build complete!")
```

Run:
```bash
python build.py
```

## Manual Bundling (Alternative Approach)

After Nuitka compilation:

1. **Copy GStreamer binaries to dist folder:**

```bash
xcopy /E /I C:\gstreamer\1.0\msvc_x86_64\bin webcam_capture.dist\gstreamer\bin
xcopy /E /I C:\gstreamer\1.0\msvc_x86_64\lib webcam_capture.dist\gstreamer\lib
```

2. **Create launcher script** (`launch.bat`):

```batch
@echo off
set GSTREAMER_ROOT=%~dp0gstreamer
set PATH=%GSTREAMER_ROOT%\bin;%PATH%
set GST_PLUGIN_PATH=%GSTREAMER_ROOT%\lib\gstreamer-1.0
webcam_capture.exe
```

## Distribution

Your final distribution folder structure:
```
webcam_capture.dist/
├── webcam_capture.exe
├── launch.bat
├── gstreamer/
│   ├── bin/
│   └── lib/
└── [other Nuitka files]
```

**Users run:** `launch.bat`

## Known Issues & Solutions

### Issue: "Could not find GStreamer"
**Solution:** Ensure `PATH` includes GStreamer bin directory

### Issue: "No cameras detected"
**Solution:** Change `device-index` in pipeline or use DirectShow source:
```python
pipeline_str = f"dshowvideosrc device-index={camera_id} ! ..."
```

### Issue: Large deployment size (~300MB)
**Solution:** This is expected. GStreamer bundles many plugins. You can reduce size by removing unused plugins from `lib/gstreamer-1.0/`

## Optimization: Minimal GStreamer Bundle

For webcam only, you need these plugins (in `lib/gstreamer-1.0/`):
- `gstcoreelements.dll`
- `gstvideoconvert.dll`
- `gstvideoscale.dll`
- `gstksvideosrc.dll` (Windows camera source)
- `gstapp.dll` (appsink)

Remove other `.dll` files to reduce size to ~100MB.


