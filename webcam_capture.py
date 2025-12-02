import os
import sys
import signal
from pathlib import Path

# ============================================================================
# STANDALONE ENVIRONMENT CONFIGURATION
# This block must run BEFORE importing 'gi'
# ============================================================================

# Determine paths once, robustly
# Use sys.executable as the anchor
# Resolve symlinks to ensure we find the real location
BASE_DIR = Path(sys.executable).resolve().parent
LOCAL_GST = BASE_DIR / "gstreamer"

# If local folder exists, use it regardless of frozen state
# This handles Nuitka standalone where sys.frozen might be ambiguous
if LOCAL_GST.exists():
    GST_ROOT = LOCAL_GST
    print(f"DEBUG: Detected standalone mode at {GST_ROOT}")
elif getattr(sys, 'frozen', False):
    # Frozen but folder missing?
    GST_ROOT = LOCAL_GST
    print(f"WARNING: Frozen mode detected but {GST_ROOT} missing!")
else:
    # Running as script (dev mode)
    GST_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
    print(f"DEBUG: Detected dev mode at {GST_ROOT}")

BIN_PATH = GST_ROOT / "bin"
LIB_PATH = GST_ROOT / "lib"
PLUGIN_PATH = LIB_PATH / "gstreamer-1.0"

# Apply environment settings UNCONDITIONALLY if the folder exists
if BIN_PATH.exists():
    print(f"DEBUG: Configuring GStreamer from {GST_ROOT}")
    
    # 1. PATH
    os.environ['PATH'] = str(BIN_PATH) + os.pathsep + os.environ.get('PATH', '')
    
    # 2. PyGObject specific
    os.environ['PYGI_DLL_DIRS'] = str(BIN_PATH)
    
    # 3. GStreamer specific
    os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
    
    # 4. Registry (to avoid conflicts)
    registry = BASE_DIR / "registry.bin" if getattr(sys, 'frozen', False) else Path("registry.bin")
    os.environ['GST_REGISTRY'] = str(registry)
    
    # 5. Scanner
    scanner = LIB_PATH / "gstreamer-1.0" / "gst-plugin-scanner.exe"
    if not scanner.exists():
        scanner = BIN_PATH / "gst-plugin-scanner.exe"
    if scanner.exists():
        os.environ['GST_PLUGIN_SCANNER'] = str(scanner)

    # 6. CRITICAL: Modern Python DLL loading (Python 3.8+)
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(BIN_PATH))
            print(f"DEBUG: os.add_dll_directory({BIN_PATH}) success")
        except Exception as e:
            print(f"DEBUG: os.add_dll_directory failed: {e}")

else:
    print(f"WARNING: GStreamer bin path not found at {BIN_PATH}")

# ============================================================================

import gi
try:
    gi.require_version('Gst', '1.0')
except ValueError:
    print("ERROR: GStreamer not found. Please install it or check PATH.")
    sys.exit(1)

from gi.repository import Gst, GLib
import numpy as np
import cv2

class GStreamerWebcam:
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        Gst.init(None)
        
        self.width = width
        self.height = height
        self.fps = fps
        self.camera_id = camera_id
        self.frame = None
        self.new_frame = False
        self.running = False
        
        # Try different Windows-compatible sources
        # ksvideosrc = Kernel Streaming (sometimes missing or deprecated)
        # dshowvideosrc = DirectShow (Standard for Windows 7+)
        # mfvideosrc = Media Foundation (Newer, Windows 10+)
        
        pipeline_str = None
        sources = [
            f"dshowvideosrc device-index={camera_id}",
            f"ksvideosrc device-index={camera_id}",
            f"mfvideosrc device-index={camera_id}"
        ]
        
        last_error = None
        for source in sources:
            try:
                print(f"Trying source: {source.split()[0]}...")
                test_str = (
                    f"{source} ! "
                    f"video/x-raw,framerate={fps}/1 ! "  # Request high FPS from camera
                    f"queue max-size-buffers=1 leaky=downstream ! "  # Drop old frames instantly to reduce latency
                    f"decodebin ! "
                    f"videoconvert ! "
                    f"video/x-raw,format=BGR ! "
                    f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
                )
                self.pipeline = Gst.parse_launch(test_str)
                # If we get here, parse_launch succeeded (element exists)
                pipeline_str = test_str
                print(f"✓ Successfully initialized {source.split()[0]}")
                break
            except Exception as e:
                print(f"✗ Failed to load {source.split()[0]}: {e}")
                last_error = e
        
        if pipeline_str is None:
            print("CRITICAL ERROR: No suitable camera source element found.")
            print("Available plugins might be missing or GST_PLUGIN_PATH is wrong.")
            print(f"Last error: {last_error}")
            sys.exit(1)

        print(f"Launching pipeline...")
            
        self.appsink = self.pipeline.get_by_name('sink')
        self.appsink.connect('new-sample', self.on_new_sample)
        
    def on_new_sample(self, sink):
        if not self.running:
            return Gst.FlowReturn.OK
            
        sample = sink.emit('pull-sample')
        if sample:
            buffer = sample.get_buffer()
            caps = sample.get_caps()
            
            # Extract width/height from the actual caps we negotiated
            structure = caps.get_structure(0)
            self.height = structure.get_value("height")
            self.width = structure.get_value("width")
            
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                try:
                    # Create numpy array from buffer
                    frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                    self.frame = frame_data.reshape((self.height, self.width, 3))
                    self.new_frame = True
                except Exception as e:
                    print(f"Frame decode error: {e}")
                finally:
                    buffer.unmap(map_info)
        
        return Gst.FlowReturn.OK
    
    def start(self):
        self.running = True
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state.")
            sys.exit(1)
    
    def read(self):
        if self.frame is not None:
            # Optional: Set to False if you want to strictly ensure you only read fresh frames
            # self.new_frame = False 
            return True, self.frame.copy()
        return False, None
    
    def release(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    print("Initializing GStreamer Webcam...")
    camera = GStreamerWebcam(camera_id=0, width=640, height=480, fps=30)
    camera.start()
    
    print("Camera started. Press 'q' to quit.")
    
    frames_received = 0
    while True:
        ret, frame = camera.read()
        
        if ret:
            if frames_received == 0:
                print("First frame received! Opening window...")
            frames_received += 1
            cv2.imshow('GStreamer Standalone', frame)
        else:
            if frames_received == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    camera.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
