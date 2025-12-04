# Linux GStreamer Setup Guide

## Step 1: Install GStreamer

### Ubuntu / Debian

```bash
# Core GStreamer
sudo apt update
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly gstreamer1.0-libav

# Development libraries (needed for building PyGObject)
sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
                 libgstreamer-plugins-bad1.0-dev
```

### Fedora

```bash
sudo dnf install gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good \
                 gstreamer1-plugins-bad-free gstreamer1-plugins-ugly \
                 gstreamer1-devel gstreamer1-plugins-base-devel
```

### Arch Linux

```bash
sudo pacman -S gstreamer gst-plugins-base gst-plugins-good \
               gst-plugins-bad gst-plugins-ugly gst-libav
```

## Step 2: Install PyGObject

### Option A: System Package (Easiest)

```bash
# Ubuntu/Debian
sudo apt install python3-gi python3-gi-cairo gir1.2-gst-plugins-base-1.0

# Fedora
sudo dnf install python3-gobject

# Arch
sudo pacman -S python-gobject
```

### Option B: pip in Virtual Environment

```bash
# Install build dependencies first
# Ubuntu/Debian:
sudo apt install libgirepository-2.0-dev gcc libcairo2-dev pkg-config python3-dev

# Fedora:
sudo dnf install gcc gobject-introspection-devel cairo-gobject-devel pkg-config python3-devel

# Arch:
sudo pacman -S python cairo pkgconf gobject-introspection

# Then install via pip
pip install pycairo PyGObject
```

## Step 3: Install Other Python Dependencies

```bash
pip install opencv-python numpy PySide6 nuitka
```

## Step 4: Verify Installation

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

## Step 5: Test Webcam

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

# Linux camera source (v4l2src)
pipeline_str = "v4l2src device=/dev/video0 ! autovideosink"
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

## Step 6: List Available Cameras

```bash
# Using GStreamer
gst-device-monitor-1.0 Video/Source

# Or using v4l2
v4l2-ctl --list-devices

# Check device capabilities
v4l2-ctl -d /dev/video0 --list-formats-ext
```

## Building Standalone

```bash
# Build
python build_standalone_linux.py

# Optimize (reduce size)
python optimize_dist_linux.py

# Run
./build/webcam_capture.dist/webcam_capture
```

## Troubleshooting

### Error: "No module named 'gi'"
- PyGObject not installed
- Make sure you installed `python3-gi` or `pip install PyGObject`

### Error: "Namespace Gst not available"
- GStreamer typelibs not installed
- Install: `sudo apt install gir1.2-gst-plugins-base-1.0`

### Error: "Could not open device '/dev/video0'"
- Camera not detected or wrong device path
- Check with: `ls -la /dev/video*`
- Try `/dev/video0`, `/dev/video2`, etc.

### Error: "Permission denied" for camera
```bash
# Add yourself to video group
sudo usermod -a -G video $USER
# Then log out and back in
```

### Camera shows wrong device index
On Linux, `/dev/video0` might not be the capture device. Many webcams create multiple devices:
- `/dev/video0` - capture
- `/dev/video1` - metadata
- etc.

Use `v4l2-ctl --list-devices` to find the correct one.

### No picture / black screen
```bash
# Check if camera works with v4l2
v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=10

# Or test with GStreamer directly
gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink
```

### Slow startup in standalone build
- Run `python optimize_dist_linux.py` to remove unused plugins
- This can reduce startup time from 20+ seconds to instant

### "Registry mismatch" or plugin errors after update
- Delete the registry file to rebuild it:
```bash
rm ~/.cache/gstreamer-1.0/registry.*.bin
# Or for standalone:
rm build/webcam_capture.dist/registry.bin
```

