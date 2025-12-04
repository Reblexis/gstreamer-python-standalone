# GStreamer Python Standalone

**Fast, low-latency webcam capture for Python that works as a standalone executable.**

Cross-platform: Windows and Linux.

## Why This Exists

OpenCV's default webcam capture on Windows lags when the window loses focus. GStreamer solves this, but deploying it is notoriously difficult—until now.

- ✅ **Zero-lag capture** even when minimized or unfocused
- ✅ **Standalone deployment** with Nuitka (no installation needed on target machines)
- ✅ **GUI with camera settings** (resolution, FPS, GPU acceleration, custom pipelines)
- ✅ **Cross-platform** - Windows and Linux support
- ✅ **Optimized bundle** (~80MB instead of 300MB)

## Quick Start

### Windows

#### Prerequisites (Dev Machine Only)
1. **Python 3.12**
2. **GStreamer MSVC 64-bit** → `C:\gstreamer\1.0\msvc_x86_64`
   - Download: https://gstreamer.freedesktop.org/download/

#### Run
```bash
pip install -r requirements.txt
python settings_gui.py      # GUI with camera settings
python webcam_capture.py    # Simple CLI version
```

#### Build Standalone
```bash
python build_standalone.py
python optimize_dist.py
```
Output: `build/webcam_capture.dist/` — zip and ship.

---

### Linux

#### Prerequisites (Dev Machine Only)
```bash
# Install GStreamer and development libraries
sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                 gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
                 gstreamer1.0-tools gstreamer1.0-libav \
                 libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev

# Install PyGObject dependencies
sudo apt install libgirepository-2.0-dev gcc libcairo2-dev pkg-config python3-dev

# Install Python packages
pip install -r requirements.txt
pip install pycairo PyGObject
```

#### Run
```bash
python settings_gui.py      # GUI with camera settings
python webcam_capture.py    # Simple CLI version
```

#### Build Standalone
```bash
python build_standalone_linux.py
python optimize_dist_linux.py
```
Output: `build/webcam_capture.dist/` — tar and ship.

Run: `./build/webcam_capture.dist/webcam_capture`

---

## Usage

```python
from webcam_capture import GStreamerWebcam

camera = GStreamerWebcam(camera_id=0, width=1280, height=720, fps=30, use_gpu=False)
camera.start()

while True:
    ret, frame = camera.read()  # Returns BGR numpy array
    if ret:
        # Process frame...
        pass

camera.release()
```

## Project Structure

| File | Description |
|------|-------------|
| `settings_gui.py` | PySide6 GUI with camera/resolution/FPS selection |
| `webcam_capture.py` | Core webcam class (cross-platform) |
| `build_standalone.py` | Nuitka build script (Windows) |
| `build_standalone_linux.py` | Nuitka build script (Linux) |
| `optimize_dist.py` | Removes unused GStreamer plugins (Windows) |
| `optimize_dist_linux.py` | Removes unused GStreamer plugins (Linux) |

## Platform Notes

### Windows
- Camera sources: `mfvideosrc` (Media Foundation), `dshowvideosrc` (DirectShow)
- GPU acceleration: D3D11

### Linux
- Camera source: `v4l2src` (Video4Linux2)
- GPU acceleration: Not implemented (software only)

## License

MIT
