# Integrating GStreamer into Standalone Nuitka/PySide6 Apps

This guide explains how to add GStreamer webcam capture to any Python app and deploy it as a standalone Windows executable.

## Prerequisites (Dev Machine)

1. **Python 3.12** (must match GStreamer's bundled bindings)
2. **GStreamer MSVC 64-bit** installed to `C:\gstreamer\1.0\msvc_x86_64`
   - Download both Runtime and Development from https://gstreamer.freedesktop.org/download/
3. **Dependencies:**
   ```bash
   pip install nuitka numpy opencv-python PySide6
   ```

---

## Step 1: Python Code Setup

Add this block at the **very top** of your main script, **before any other imports**:

```python
import os
import sys
from pathlib import Path

# ============================================================================
# GSTREAMER STANDALONE CONFIGURATION
# Must run BEFORE importing 'gi'
# ============================================================================

BASE_DIR = Path(sys.executable).resolve().parent
LOCAL_GST = BASE_DIR / "gstreamer"

# Detect standalone vs dev mode
if LOCAL_GST.exists():
    GST_ROOT = LOCAL_GST  # Standalone: use bundled gstreamer
else:
    GST_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")  # Dev: use system install

BIN_PATH = GST_ROOT / "bin"
LIB_PATH = GST_ROOT / "lib"
PLUGIN_PATH = LIB_PATH / "gstreamer-1.0"

if BIN_PATH.exists():
    # 1. PATH for DLLs
    os.environ['PATH'] = str(BIN_PATH) + os.pathsep + os.environ.get('PATH', '')
    
    # 2. PyGObject DLL location
    os.environ['PYGI_DLL_DIRS'] = str(BIN_PATH)
    
    # 3. GStreamer plugin path
    os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
    
    # 4. Registry file (avoid conflicts)
    os.environ['GST_REGISTRY'] = str(BASE_DIR / "registry.bin")
    
    # 5. Plugin scanner
    scanner = BIN_PATH / "gst-plugin-scanner.exe"
    if scanner.exists():
        os.environ['GST_PLUGIN_SCANNER'] = str(scanner)
    
    # 6. CRITICAL: Python 3.8+ DLL loading
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(str(BIN_PATH))
    
    # 7. Add GStreamer's Python bindings (DEV MODE ONLY)
    # In standalone mode, gi is bundled in dist root
    if not LOCAL_GST.exists():
        gst_site_packages = GST_ROOT / "lib" / "site-packages"
        if gst_site_packages.exists():
            sys.path.insert(0, str(gst_site_packages))

# ============================================================================

# NOW import gi and other modules
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
        
        # Robust pipeline: let camera output native format, then convert
        pipeline_str = (
            f"mfvideosrc device-index={camera_id} do-timestamp=true ! "
            f"decodebin ! "
            f"videoconvert ! "
            f"videorate drop-only=true ! "
            f"video/x-raw,framerate={fps}/1 ! "
            f"videoscale ! "
            f"video/x-raw,width={width},height={height} ! "
            f"videoconvert ! "
            f"video/x-raw,format=BGR ! "
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
                arr = np.frombuffer(info.data, dtype=np.uint8)
                self.frame = arr.reshape((h, w, 3))
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

Create `build.py`:

```python
import os
import sys
import shutil
import subprocess
from pathlib import Path

GSTREAMER_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
ENTRY_SCRIPT = "main.py"  # Your main script
OUTPUT_NAME = "MyApp"

def build():
    # 1. Nuitka compilation
    # CRITICAL: Include stdlib modules required by PyGObject
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",  # If using PySide6
        "--enable-plugin=numpy",
        "--include-module=asyncio",   # Required by gi
        "--include-module=optparse",  # Required by gi._option
        "--include-module=gettext",   # Required by gi
        "--include-module=locale",    # Required by gi
        "--include-package=xml",      # Required by gi
        "--include-package=ctypes",   # Required by gi
        "--output-dir=build",
        f"--output-filename={OUTPUT_NAME}.exe",
        ENTRY_SCRIPT
    ]
    subprocess.run(cmd, check=True)
    
    # 2. Determine dist folder
    entry_name = Path(ENTRY_SCRIPT).stem
    dist_dir = Path(f"build/{entry_name}.dist")
    
    # 3. Bundle GStreamer runtime
    gst_target = dist_dir / "gstreamer"
    if gst_target.exists():
        shutil.rmtree(gst_target)
    gst_target.mkdir()
    
    shutil.copytree(GSTREAMER_ROOT / "bin", gst_target / "bin")
    shutil.copytree(GSTREAMER_ROOT / "lib", gst_target / "lib")
    
    # 4. CRITICAL: Bundle PyGObject (gi module)
    # PyGObject is NOT pip-installable on Windows, must copy from GStreamer
    src_gi = GSTREAMER_ROOT / "lib" / "site-packages" / "gi"
    if src_gi.exists():
        shutil.copytree(src_gi, dist_dir / "gi")
    
    src_cairo = GSTREAMER_ROOT / "lib" / "site-packages" / "cairo"
    if src_cairo.exists():
        shutil.copytree(src_cairo, dist_dir / "cairo")
    
    # 5. Clean dev files
    for root, dirs, files in os.walk(gst_target):
        for f in files:
            if f.endswith(('.h', '.lib', '.pdb', '.def')):
                os.remove(os.path.join(root, f))
    
    print(f"Build complete: {dist_dir}")

if __name__ == "__main__":
    build()
```

---

## Step 4: Optimize (Reduce Size & Startup Time)

Create `optimize.py`:

```python
import os
from pathlib import Path

DIST_DIR = Path("build/MyApp.dist")  # Adjust to your dist folder name
GST_PLUGINS = DIST_DIR / "gstreamer/lib/gstreamer-1.0"

# Essential plugins for webcam capture
KEEP_PREFIXES = [
    "gstcoreelements", "gstvideoconvert", "gstvideoscale", "gstvideorate",
    "gstvideofilter", "gstdirectshow", "gstmediafoundation", "gstapp",
    "gsttypefindfunctions", "gstplayback", "gstjpeg", "gstpng",
    "gstisomp4", "gstd3d11", "gstd3d12", "gstopengl",
    "gstaudioconvert", "gstaudioresample", "gstwasapi", "gstwasapi2"
]

for dll in GST_PLUGINS.glob("*.dll"):
    if not any(dll.name.startswith(p) for p in KEEP_PREFIXES):
        os.remove(dll)
        print(f"Removed: {dll.name}")

print("Optimization complete!")
```

---

## Step 5: Deploy

1. Run `python build.py`
2. Run `python optimize.py`
3. Your standalone app is in `build/MyApp.dist/`
4. Zip and distribute — no installation required on target machines

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'gi'"**
- The `gi` folder must be copied to the dist root (Step 3.4)

**"ModuleNotFoundError: No module named 'asyncio'" (or optparse, etc.)**
- Add the missing module to Nuitka's `--include-module` flags

**"Could not deduce DLL directories"**
- Ensure `os.add_dll_directory(str(BIN_PATH))` runs before importing `gi`
- Ensure `PYGI_DLL_DIRS` environment variable is set

**Slow startup (20+ seconds)**
- Run the optimize script to remove unused plugins

**Camera not detected**
- Try different sources: `mfvideosrc`, `dshowvideosrc`, `ksvideosrc`
- Check `device-index` (0, 1, 2...)

**Low FPS / Lag**
- Use `queue leaky=downstream` and `appsink drop=true`
- Use `videorate drop-only=true` to only drop frames, never duplicate
