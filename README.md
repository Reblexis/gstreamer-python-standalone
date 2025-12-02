# GStreamer Python Standalone

**Fast, low-latency webcam capture for Python that works as a standalone Windows executable.**

## Why This Exists

OpenCV's default webcam capture on Windows lags when the window loses focus. GStreamer solves this, but deploying it is notoriously difficult—until now.

- ✅ **Zero-lag capture** even when minimized or unfocused
- ✅ **Standalone deployment** with Nuitka (no installation needed on target machines)
- ✅ **GUI with camera settings** (resolution, FPS, GPU acceleration, custom pipelines)
- ✅ **Optimized bundle** (~80MB instead of 300MB)

## Quick Start

### Prerequisites (Dev Machine Only)
1. **Python 3.12**
2. **GStreamer MSVC 64-bit** → `C:\gstreamer\1.0\msvc_x86_64`
   - Download: https://gstreamer.freedesktop.org/download/

### Run
```bash
pip install -r requirements.txt
python settings_gui.py      # GUI with camera settings
python webcam_capture.py    # Simple CLI version
```

### Build Standalone
```bash
python build_standalone.py
python optimize_dist.py
```
Output: `build/webcam_capture.dist/` — zip and ship.

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
| `webcam_capture.py` | Core webcam class |
| `build_standalone.py` | Nuitka build script |
| `optimize_dist.py` | Removes unused GStreamer plugins |

## License

MIT
