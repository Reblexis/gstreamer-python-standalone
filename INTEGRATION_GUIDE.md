# How to Integrate Standalone GStreamer Webcam into Nuitka Python Projects

This guide explains how to add fast, low-latency, standalone GStreamer webcam support to any Python application packaged with Nuitka on Windows.

## Why Use This?
- **Zero-Lag Background Capture:** Unlike OpenCV's default backend, GStreamer continues capturing frames at full speed even when the window is minimized or unfocused.
- **Standalone:** The final executable runs on any Windows machine without installing GStreamer or Python.
- **Optimized:** Includes a script to strip unused plugins, keeping the bundle size manageable (~50-80MB overhead).

---

## 1. Prerequisites (Dev Machine)

1.  **Install Python 3.12** (Required to match standard GStreamer binaries).
2.  **Install GStreamer MSVC 64-bit** (Runtime + Development) to `C:\gstreamer\1.0\msvc_x86_64`.
3.  **Install Build Dependencies:**
    ```bash
    pip install nuitka numpy opencv-python
    ```

---

## 2. Python Code Integration

Add this block to the **very top** of your main script (e.g., `main.py`). It configures the environment before importing GStreamer.

```python
import os
import sys
from pathlib import Path

# --- START GSTREAMER CONFIGURATION ---
if getattr(sys, 'frozen', False):
    # Standalone mode: bundled gstreamer is next to the executable
    BASE_DIR = Path(sys.executable).resolve().parent
    GST_ROOT = BASE_DIR / "gstreamer"
else:
    # Dev mode: use system installation
    GST_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")

BIN_PATH = GST_ROOT / "bin"
LIB_PATH = GST_ROOT / "lib"
PLUGIN_PATH = LIB_PATH / "gstreamer-1.0"

if BIN_PATH.exists():
    # 1. Add to PATH
    os.environ['PATH'] = str(BIN_PATH) + os.pathsep + os.environ.get('PATH', '')
    # 2. Configure PyGObject and GStreamer
    os.environ['PYGI_DLL_DIRS'] = str(BIN_PATH)
    os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
    # 3. Configure Registry
    registry = BASE_DIR / "registry.bin" if getattr(sys, 'frozen', False) else Path("registry.bin")
    os.environ['GST_REGISTRY'] = str(registry)
    # 4. Configure Scanner
    scanner = BIN_PATH / "gst-plugin-scanner.exe"
    if scanner.exists():
        os.environ['GST_PLUGIN_SCANNER'] = str(scanner)
    # 5. Add DLL Directory (Critical for Python 3.8+)
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(BIN_PATH))
        except Exception:
            pass
# --- END GSTREAMER CONFIGURATION ---

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
```

### Camera Class
Use this robust class for capture. It handles `appsink` buffer drops to ensure zero latency.

```python
class GStreamerWebcam:
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        Gst.init(None)
        self.width, self.height = width, height
        self.frame = None
        
        # Pipeline: dshowvideosrc -> force FPS -> leaky queue -> decode -> convert -> numpy
        cmd = (
            f"dshowvideosrc device-index={camera_id} ! "
            f"video/x-raw,framerate={fps}/1 ! "
            f"queue max-size-buffers=1 leaky=downstream ! "
            f"decodebin ! videoconvert ! video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
        )
        
        self.pipeline = Gst.parse_launch(cmd)
        self.appsink = self.pipeline.get_by_name('sink')
        self.appsink.connect('new-sample', self._on_sample)
        self.pipeline.set_state(Gst.State.PLAYING)

    def _on_sample(self, sink):
        sample = sink.emit('pull-sample')
        if sample:
            buf = sample.get_buffer()
            caps = sample.get_caps()
            h = caps.get_structure(0).get_value("height")
            w = caps.get_structure(0).get_value("width")
            success, info = buf.map(Gst.MapFlags.READ)
            if success:
                arr = np.frombuffer(info.data, dtype=np.uint8)
                self.frame = arr.reshape((h, w, 3))
                buf.unmap(info)
        return Gst.FlowReturn.OK

    def read(self):
        return (True, self.frame.copy()) if self.frame is not None else (False, None)

    def release(self):
        self.pipeline.set_state(Gst.State.NULL)
```

---

## 3. Build Script (`build.py`)

Use this script to compile and bundle the GStreamer runtime.

```python
import os
import shutil
import subprocess
from pathlib import Path

# Configuration
MAIN_SCRIPT = "main.py"
OUTPUT_NAME = "MyApp"
GST_SYSTEM_PATH = Path(r"C:\gstreamer\1.0\msvc_x86_64")

# 1. Build with Nuitka
cmd = [
    "python", "-m", "nuitka",
    "--standalone",
    "--enable-plugin=numpy",  # Required for OpenCV/Numpy
    "--windows-disable-console", # Hide console window
    f"--output-filename={OUTPUT_NAME}.exe",
    MAIN_SCRIPT
]
subprocess.run(cmd, check=True)

# 2. Bundle GStreamer
dist_dir = Path(f"{MAIN_SCRIPT.replace('.py', '')}.dist")
gst_target = dist_dir / "gstreamer"

print("Bundling GStreamer...")
if gst_target.exists(): shutil.rmtree(gst_target)
gst_target.mkdir()

shutil.copytree(GST_SYSTEM_PATH / "bin", gst_target / "bin")
shutil.copytree(GST_SYSTEM_PATH / "lib", gst_target / "lib")

# 3. Optimize (Remove unused plugins to reduce size/startup time)
print("Optimizing size...")
gst_plugins = gst_target / "lib/gstreamer-1.0"
keep_prefixes = ["gstcore", "gstvideo", "gstapp", "gstdirectshow", "gstmediafoundation", "gstplayback"]
keep_files = ["gstcoreelements.dll", "gstapp.dll", "gstdirectshow.dll", "gstvideoconvert.dll"]

for dll in gst_plugins.glob("*.dll"):
    name = dll.name
    if name in keep_files: continue
    if any(name.startswith(p) for p in keep_prefixes): continue
    try:
        os.remove(dll)
    except: pass

print("Build Complete!")
```

---

## 4. Deployment

1.  Run `python build.py`.
2.  The output folder (e.g., `main.dist`) is your standalone application.
3.  **Zip it and ship it.** No installation required on the user's machine.

## Troubleshooting

**"ImportError: Could not deduce DLL directories"**
- Ensure the `os.add_dll_directory` block is present at the top of your script.
- Ensure the `gstreamer` folder is copied correctly into the `.dist` folder.

**Startup takes 20+ seconds**
- You forgot step 3 (Optimization). GStreamer is scanning hundreds of unused plugins. Run the optimization to remove them.

**Camera lag**
- Ensure `queue max-size-buffers=1 leaky=downstream` is in your pipeline string. This forces GStreamer to drop old frames if your app is processing them slowly.

