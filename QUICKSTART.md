# Quick Start Guide

## Installation (5 minutes)

### Step 1: Install GStreamer

1. Download **both** installers from https://gstreamer.freedesktop.org/download/:
   - Runtime: `gstreamer-1.0-msvc-x86_64-*.msi`
   - Development: `gstreamer-1.0-devel-msvc-x86_64-*.msi`

2. Install both (use default location: `C:\gstreamer\1.0\msvc_x86_64\`)

3. Add to PATH (Windows):
   ```
   System Properties → Environment Variables → Path → Add:
   C:\gstreamer\1.0\msvc_x86_64\bin
   ```

4. **Restart your terminal/IDE**

### Step 2: Install Python Packages

```bash
pip install numpy opencv-python PyGObject
```

**Note:** If PyGObject fails, see WINDOWS_SETUP.md for alternative installation methods.

### Step 3: Test Installation

```bash
python test_gstreamer.py
```

All tests should pass ✓

### Step 4: Run Example

```bash
python webcam_capture.py
```

Press 'q' to quit.

## Building Standalone Executable

```bash
pip install nuitka
python build_standalone.py
```

Your standalone app will be in `build/webcam_capture.dist/`

Run: `build\webcam_capture.dist\launch.bat`

## Troubleshooting

### "No module named 'gi'"
- PyGObject not installed
- Try: `pip install --upgrade PyGObject`
- Or use conda: `conda install -c conda-forge pygobject`

### "Could not load GStreamer"
- GStreamer not in PATH
- Restart terminal after adding to PATH
- Verify: `gst-launch-1.0 --version` should work

### "No camera detected"
- Check camera works in other apps
- Try: `gst-device-monitor-1.0` to list cameras
- Try changing `ksvideosrc` to `dshowvideosrc` in code

### Camera still lags when unfocused
- Make sure you're using GStreamer, not OpenCV's VideoCapture(0)
- Use `webcam_capture.py` or `webcam_headless.py`

## File Overview

- `webcam_capture.py` - Main class with GUI example
- `webcam_headless.py` - Background capture (no window)
- `test_gstreamer.py` - Verify installation
- `build_standalone.py` - Create standalone executable
- `WINDOWS_SETUP.md` - Detailed setup instructions
- `DEPLOYMENT_GUIDE.md` - Nuitka deployment details

## Using in Your Code

```python
from webcam_capture import GStreamerWebcam

camera = GStreamerWebcam(camera_id=0, width=640, height=480, fps=30)
camera.start()

while True:
    ret, frame = camera.read()  # frame is numpy array (BGR)
    if ret:
        # Your processing here
        pass

camera.release()
```

## Performance Notes

- **Latency:** ~30-50ms (much better than OpenCV DirectShow)
- **No focus lag:** Works even when window is minimized
- **CPU usage:** Similar to OpenCV
- **Deployment size:** ~100-300MB (depending on optimization)

## Need Help?

1. Run `python test_gstreamer.py` - shows what's missing
2. Check WINDOWS_SETUP.md for detailed setup
3. Check DEPLOYMENT_GUIDE.md for Nuitka issues


