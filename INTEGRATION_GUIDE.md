# Integrating GStreamer into Standalone Nuitka/PySide6 Apps

This guide explains how to add GStreamer webcam capture to any Python app and deploy it as a standalone executable on **Windows** or **Linux**.

## Prerequisites (Dev Machine)

### Windows
1. **Python 3.12**
2. **GStreamer MSVC 64-bit** → `C:\gstreamer\1.0\msvc_x86_64`
   - Download Runtime + Development from https://gstreamer.freedesktop.org/download/
3. `pip install nuitka numpy opencv-python PySide6`

### Linux
1. **Python 3.10+**
2. **GStreamer** (system packages):
   ```bash
   sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
                    gstreamer1.0-libav libgstreamer1.0-dev
   ```
3. **PyGObject**:
   ```bash
   sudo apt install python3-gi gir1.2-gst-plugins-base-1.0
   # Or in venv: pip install PyGObject (needs libgirepository-2.0-dev)
   ```
4. `pip install nuitka numpy opencv-python PySide6`

---

## Step 1: Python Code Setup

Add this block at the **very top** of your main script, **before any other imports**:

```python
import os
import sys
from pathlib import Path

# ============================================================================
# GSTREAMER STANDALONE CONFIGURATION - Cross-platform
# Must run BEFORE importing 'gi'
# ============================================================================

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

BASE_DIR = Path(sys.executable).resolve().parent
LOCAL_GST = BASE_DIR / "gstreamer"

if LOCAL_GST.exists():
    # Standalone mode: use bundled GStreamer
    if IS_WINDOWS:
        BIN_PATH = LOCAL_GST / "bin"
        PLUGIN_PATH = LOCAL_GST / "lib" / "gstreamer-1.0"
        os.environ['PATH'] = str(BIN_PATH) + os.pathsep + os.environ.get('PATH', '')
        os.environ['PYGI_DLL_DIRS'] = str(BIN_PATH)
        os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
        os.environ['GST_PLUGIN_SCANNER'] = str(BIN_PATH / "gst-plugin-scanner.exe")
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(str(BIN_PATH))
    else:  # Linux
        LIB_PATH = LOCAL_GST / "lib"
        PLUGIN_PATH = LOCAL_GST / "plugins"
        os.environ['LD_LIBRARY_PATH'] = str(LIB_PATH) + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
        os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
        os.environ['GST_PLUGIN_SCANNER'] = str(LOCAL_GST / "bin" / "gst-plugin-scanner")
        gi_typelib = LOCAL_GST / "lib" / "girepository-1.0"
        if gi_typelib.exists():
            os.environ['GI_TYPELIB_PATH'] = str(gi_typelib) + os.pathsep + os.environ.get('GI_TYPELIB_PATH', '')
    
    os.environ['GST_REGISTRY'] = str(BASE_DIR / "registry.bin")

elif IS_WINDOWS:
    # Dev mode: Windows system GStreamer
    GST_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
    if GST_ROOT.exists():
        os.environ['PATH'] = str(GST_ROOT / "bin") + os.pathsep + os.environ.get('PATH', '')
        os.environ['GST_PLUGIN_PATH'] = str(GST_ROOT / "lib" / "gstreamer-1.0")
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(str(GST_ROOT / "bin"))
        sys.path.insert(0, str(GST_ROOT / "lib" / "site-packages"))

# Linux dev mode: uses system GStreamer automatically (no setup needed)

# ============================================================================

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
```

---

## Step 2: Camera Class

```python
class GStreamerWebcam:
    def __init__(self, camera_id=0, width=1280, height=720, fps=30):
        Gst.init(None)
        self.frame = None
        self.running = False
        
        # Platform-specific camera source
        if sys.platform == 'win32':
            source = f"mfvideosrc device-index={camera_id} do-timestamp=true ! decodebin"
        else:  # Linux
            source = f"v4l2src device=/dev/video{camera_id} do-timestamp=true"
        
        pipeline_str = (
            f"{source} ! "
            f"videoconvert ! "
            f"videorate drop-only=true ! video/x-raw,framerate={fps}/1 ! "
            f"videoscale ! video/x-raw,width={width},height={height} ! "
            f"videoconvert ! video/x-raw,format=BGR ! "
            f"queue max-size-buffers=2 leaky=downstream ! "
            f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsink = self.pipeline.get_by_name('sink')
        self.appsink.connect('new-sample', self._on_sample)

    def _on_sample(self, sink):
        sample = sink.emit('pull-sample')
        if sample:
            buf = sample.get_buffer()
            caps = sample.get_caps()
            h = caps.get_structure(0).get_value("height")
            w = caps.get_structure(0).get_value("width")
            success, info = buf.map(Gst.MapFlags.READ)
            if success:
                self.frame = np.frombuffer(info.data, dtype=np.uint8).reshape((h, w, 3))
                buf.unmap(info)
        return Gst.FlowReturn.OK

    def start(self):
        self.running = True
        self.pipeline.set_state(Gst.State.PLAYING)

    def read(self):
        return (True, self.frame.copy()) if self.frame is not None else (False, None)

    def release(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
```

---

## Step 3: Build Script

### Windows (`build.py`)

```python
import os, sys, shutil, subprocess
from pathlib import Path

GSTREAMER_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
ENTRY_SCRIPT = "main.py"

def build():
    # Nuitka compilation
    subprocess.run([
        sys.executable, "-m", "nuitka", "--standalone",
        "--enable-plugin=pyside6",
        "--include-module=asyncio", "--include-module=optparse",
        "--include-module=gettext", "--include-module=locale",
        "--include-package=xml", "--include-package=ctypes",
        "--output-dir=build", ENTRY_SCRIPT
    ], check=True)
    
    dist_dir = Path(f"build/{Path(ENTRY_SCRIPT).stem}.dist")
    gst_target = dist_dir / "gstreamer"
    
    # Bundle GStreamer
    shutil.copytree(GSTREAMER_ROOT / "bin", gst_target / "bin")
    shutil.copytree(GSTREAMER_ROOT / "lib", gst_target / "lib")
    
    # Bundle PyGObject (required on Windows)
    shutil.copytree(GSTREAMER_ROOT / "lib/site-packages/gi", dist_dir / "gi")
    
    # Clean dev files
    for root, _, files in os.walk(gst_target):
        for f in files:
            if f.endswith(('.h', '.lib', '.pdb', '.def')):
                os.remove(os.path.join(root, f))

if __name__ == "__main__":
    build()
```

### Linux (`build_linux.py`)

```python
import os, sys, shutil, subprocess
from pathlib import Path

ENTRY_SCRIPT = "main.py"
LIB_PATH = Path("/usr/lib/x86_64-linux-gnu")  # Adjust for your distro

def build():
    # Nuitka compilation
    subprocess.run([
        sys.executable, "-m", "nuitka", "--standalone",
        "--enable-plugin=pyside6",
        "--include-module=asyncio", "--include-module=optparse",
        "--include-module=gettext", "--include-module=locale",
        "--include-package=xml", "--include-package=ctypes",
        "--output-dir=build", ENTRY_SCRIPT
    ], check=True)
    
    dist_dir = Path(f"build/{Path(ENTRY_SCRIPT).stem}.dist")
    gst_target = dist_dir / "gstreamer"
    gst_target.mkdir(exist_ok=True)
    (gst_target / "lib").mkdir(); (gst_target / "plugins").mkdir(); (gst_target / "bin").mkdir()
    
    # Bundle GStreamer libraries
    for lib in LIB_PATH.glob("libgst*.so*"):
        shutil.copy2(lib, gst_target / "lib" / lib.name, follow_symlinks=False)
    for lib in LIB_PATH.glob("libglib*.so*"):
        shutil.copy2(lib, gst_target / "lib" / lib.name, follow_symlinks=False)
    
    # Bundle plugins
    for plugin in (LIB_PATH / "gstreamer-1.0").glob("*.so"):
        shutil.copy2(plugin, gst_target / "plugins" / plugin.name)
    
    # Bundle typelibs
    (gst_target / "lib/girepository-1.0").mkdir(parents=True)
    for typelib in ["Gst-1.0", "GstBase-1.0", "GstVideo-1.0", "GstApp-1.0", "GLib-2.0", "GObject-2.0"]:
        src = LIB_PATH / "girepository-1.0" / f"{typelib}.typelib"
        if src.exists():
            shutil.copy2(src, gst_target / "lib/girepository-1.0")

if __name__ == "__main__":
    build()
```

---

## Step 4: Optimize (Reduce Size)

Remove unused plugins to reduce size from ~300MB to ~80MB.

### Windows
```python
KEEP = ["gstcoreelements", "gstvideoconvert", "gstvideoscale", "gstvideorate",
        "gstmediafoundation", "gstdirectshow", "gstapp", "gstplayback", "gstjpeg"]
for dll in Path("build/main.dist/gstreamer/lib/gstreamer-1.0").glob("*.dll"):
    if not any(dll.name.startswith(p) for p in KEEP):
        dll.unlink()
```

### Linux
```python
KEEP = ["gstcoreelements", "gstvideoconvert", "gstvideoscale", "gstvideorate",
        "gstvideo4linux2", "gstapp", "gstplayback", "gstjpeg", "gstlibav"]
for so in Path("build/main.dist/gstreamer/plugins").glob("*.so"):
    if not any(so.stem.startswith(p) or so.stem.startswith("lib"+p) for p in KEEP):
        so.unlink()
```

---

## Step 5: Deploy

| Platform | Build | Output | Run |
|----------|-------|--------|-----|
| Windows | `python build.py` | `build/main.dist/` | `main.exe` |
| Linux | `python build_linux.py` | `build/main.dist/` | `./main` |

Zip/tar the dist folder and ship — no GStreamer installation required on target.

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `No module named 'gi'` | Windows: copy `gi` folder to dist root. Linux: install `python3-gi` |
| `Namespace Gst not available` | Linux: install `gir1.2-gst-plugins-base-1.0` or bundle typelibs |
| `Could not open /dev/video0` | Linux: check permissions (`sudo usermod -aG video $USER`) |
| Camera not detected | Windows: try `mfvideosrc`, `dshowvideosrc`. Linux: try `/dev/video0`, `/dev/video2` |
| Slow startup (20+ sec) | Run optimize script to remove unused plugins |
