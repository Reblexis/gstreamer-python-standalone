# GStreamer Python Standalone

**Fast, low-latency webcam capture for Python that works as a standalone Windows executable.**

## Why This Exists

OpenCV's default webcam capture on Windows has a critical flaw: **it lags when the window loses focus**. This is unacceptable for background processing, automation, or any app that needs consistent frame rates.

GStreamer solves this, but deploying it is notoriously difficult—until now.

This project provides:
- ✅ **Zero-lag capture** even when minimized or unfocused
- ✅ **Standalone deployment** with Nuitka (no Python or GStreamer installation needed on target machines)
- ✅ **Simple API** compatible with OpenCV workflows
- ✅ **Optimized bundle** (~50-80MB instead of 300MB)

## Quick Start

### Prerequisites (Development Machine Only)
1. **Python 3.12**
2. **GStreamer MSVC 64-bit** installed to `C:\gstreamer\1.0\msvc_x86_64`
   - Download: https://gstreamer.freedesktop.org/download/

### Install & Run
```bash
pip install -r requirements.txt
python webcam_capture.py
```

### Build Standalone Executable
```bash
python build_standalone.py
python optimize_dist.py  # Reduces size and startup time
```

Your standalone app is now in `build/webcam_capture.dist/`. Zip it and ship it.

## Usage

```python
from webcam_capture import GStreamerWebcam

camera = GStreamerWebcam(camera_id=0, width=640, height=480, fps=30)
camera.start()

while True:
    ret, frame = camera.read()  # Returns numpy array (BGR, like OpenCV)
    if ret:
        # Process frame...
        pass

camera.release()
```

## Project Structure

| File | Description |
|------|-------------|
| `webcam_capture.py` | Main webcam class with GUI example |
| `webcam_headless.py` | Headless capture (no window) |
| `build_standalone.py` | Nuitka build + GStreamer bundling |
| `optimize_dist.py` | Removes unused plugins for faster startup |
| `INTEGRATION_GUIDE.md` | How to add this to your own project |

## How It Works

1. **Self-configuring:** The app detects if it's running standalone and configures GStreamer paths automatically.
2. **Bundled runtime:** All GStreamer DLLs are copied into the distribution folder.
3. **Optimized pipeline:** Uses `appsink` with `drop=true` and `max-buffers=1` to ensure zero latency.

## Troubleshooting

**Slow startup (20+ seconds)?**
Run `python optimize_dist.py` after building. This removes unused codec plugins.

**"Could not deduce DLL directories"?**
The `gstreamer` folder must be next to your `.exe`. Check your build output structure.

**No camera detected?**
Run `python list_cameras.py` to see available devices.

## License

MIT / Public Domain - Use freely.
