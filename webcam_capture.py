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
    
    # 7. Add GStreamer's Python bindings to path ONLY in dev mode
    # In standalone mode, PyGObject is bundled by Nuitka
    if not LOCAL_GST.exists():  # Dev mode only
        gst_site_packages = GST_ROOT / "lib" / "site-packages"
        if gst_site_packages.exists() and str(gst_site_packages) not in sys.path:
            sys.path.insert(0, str(gst_site_packages))
            print(f"DEBUG: Added {gst_site_packages} to sys.path")

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
    """
    GStreamer-based webcam capture with optional GPU acceleration.
    
    Args:
        camera_id: Camera device index (0, 1, 2...)
        width: Desired frame width
        height: Desired frame height
        fps: Desired frames per second
        use_gpu: Enable D3D11 GPU acceleration for video conversion
        custom_pipeline: Override all settings with a custom GStreamer pipeline string.
                        Must include 'appsink name=sink' for frame retrieval.
    """
    
    def __init__(self, camera_id=0, width=640, height=480, fps=30, use_gpu=False, custom_pipeline=None):
        Gst.init(None)
        
        # Ensure all values are integers for GStreamer caps
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.camera_id = int(camera_id)
        self.use_gpu = use_gpu
        self.frame = None
        self.new_frame = False
        self.running = False
        
        # If custom pipeline provided, use it directly
        if custom_pipeline:
            print(f"Using custom pipeline...")
            try:
                self.pipeline = Gst.parse_launch(custom_pipeline)
                print(f"✓ Custom pipeline parsed successfully")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to parse custom pipeline: {e}")
                raise RuntimeError(f"Invalid pipeline: {e}")
        else:
            # Build pipeline automatically
            self._build_auto_pipeline()
        
        print(f"Launching pipeline...")
        self.appsink = self.pipeline.get_by_name('sink')
        if not self.appsink:
            raise RuntimeError("Pipeline must contain 'appsink name=sink'")
        self.appsink.connect('new-sample', self.on_new_sample)
    
    def _build_auto_pipeline(self):
        """Build pipeline automatically, trying different camera sources."""
        # Windows camera sources in order of preference:
        # 1. mfvideosrc = Media Foundation (Modern, Windows 10+, best performance)
        # 2. dshowvideosrc = DirectShow (Legacy but widely compatible)
        # 3. ksvideosrc = Kernel Streaming (low-level, sometimes missing)
        
        sources = [
            f"mfvideosrc device-index={self.camera_id}",
            f"dshowvideosrc device-index={self.camera_id}",
            f"ksvideosrc device-index={self.camera_id}"
        ]
        
        # Build conversion chain based on GPU setting
        if self.use_gpu:
            # D3D11 GPU-accelerated pipeline
            convert_chain = (
                "d3d11upload ! "
                "d3d11convert ! "
                "d3d11download ! "
                "videoconvert ! "
            )
            print("GPU acceleration: ENABLED (D3D11)")
        else:
            convert_chain = "videoconvert ! "
            print("GPU acceleration: DISABLED")
        
        pipeline_str = None
        last_error = None
        
        # Strategy 1: Let camera output native format, then convert and scale
        # This is more reliable than forcing caps on the source
        print(f"Target: {self.width}x{self.height}@{self.fps}fps")
        
        for source in sources:
            try:
                source_name = source.split()[0]
                print(f"Trying source: {source_name}...")
                
                # Best practice pipeline:
                # 1. Source outputs whatever format it wants
                # 2. decodebin handles any encoded formats (MJPG, etc.)
                # 3. videoconvert converts to a common format
                # 4. videorate adjusts framerate (drops/duplicates frames)
                # 5. videoscale adjusts resolution
                # 6. Final videoconvert to BGR for OpenCV
                # 7. Leaky queue right before appsink to drop old frames
                test_str = (
                    f"{source} do-timestamp=true ! "
                    f"decodebin ! "
                    f"videoconvert ! "
                    f"videorate drop-only=true ! "
                    f"video/x-raw,framerate={self.fps}/1 ! "
                    f"videoscale ! "
                    f"video/x-raw,width={self.width},height={self.height} ! "
                    f"{convert_chain}"
                    f"video/x-raw,format=BGR ! "
                    f"queue max-size-buffers=2 max-size-time=0 max-size-bytes=0 leaky=downstream ! "
                    f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true wait-on-eos=false"
                )
                self.pipeline = Gst.parse_launch(test_str)
                pipeline_str = test_str
                print(f"✓ Initialized {source_name}")
                break
            except Exception as e:
                print(f"✗ Failed: {e}")
                last_error = e
        
        # Strategy 2: Simpler pipeline without videorate (for problematic cameras)
        if pipeline_str is None:
            print("Trying simpler pipeline without framerate control...")
            for source in sources:
                try:
                    source_name = source.split()[0]
                    test_str = (
                        f"{source} do-timestamp=true ! "
                        f"decodebin ! "
                        f"videoconvert ! "
                        f"videoscale ! "
                        f"video/x-raw,width={self.width},height={self.height} ! "
                        f"{convert_chain}"
                        f"video/x-raw,format=BGR ! "
                        f"queue max-size-buffers=2 leaky=downstream ! "
                        f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
                    )
                    self.pipeline = Gst.parse_launch(test_str)
                    pipeline_str = test_str
                    print(f"✓ Initialized {source_name} (no framerate control)")
                    break
                except Exception as e:
                    last_error = e
        
        # Strategy 3: Minimal pipeline (just convert to BGR)
        if pipeline_str is None:
            print("Trying minimal pipeline...")
            for source in sources:
                try:
                    source_name = source.split()[0]
                    test_str = (
                        f"{source} ! "
                        f"decodebin ! "
                        f"videoconvert ! "
                        f"video/x-raw,format=BGR ! "
                        f"queue max-size-buffers=2 leaky=downstream ! "
                        f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
                    )
                    self.pipeline = Gst.parse_launch(test_str)
                    pipeline_str = test_str
                    print(f"✓ Initialized {source_name} (minimal)")
                    break
                except Exception as e:
                    last_error = e
        
        if pipeline_str is None:
            raise RuntimeError(f"No suitable camera source found. Last error: {last_error}")
    
    @staticmethod
    def list_cameras():
        """
        List available camera devices.
        
        Returns:
            List of dicts with 'index', 'name', and 'caps' keys.
        """
        Gst.init(None)
        cameras = []
        
        # Try to get device monitor
        monitor = Gst.DeviceMonitor.new()
        monitor.add_filter("Video/Source", None)
        monitor.start()
        
        devices = monitor.get_devices()
        for i, device in enumerate(devices):
            name = device.get_display_name()
            caps = device.get_caps()
            cameras.append({
                'index': i,
                'name': name,
                'device': device,
                'caps': caps
            })
        
        monitor.stop()
        
        # Fallback: if no devices found via monitor, return generic entries
        if not cameras:
            for i in range(4):
                cameras.append({
                    'index': i,
                    'name': f"Camera {i}",
                    'caps': None
                })
        
        return cameras
    
    @staticmethod
    def get_camera_modes(camera_index=0):
        """
        Get available resolution/FPS modes for a specific camera.
        
        Returns:
            List of dicts with 'width', 'height', 'fps' keys, sorted by resolution then FPS.
        """
        Gst.init(None)
        modes = []
        seen = set()
        
        # Get device caps
        monitor = Gst.DeviceMonitor.new()
        monitor.add_filter("Video/Source", None)
        monitor.start()
        
        devices = monitor.get_devices()
        if camera_index < len(devices):
            device = devices[camera_index]
            caps = device.get_caps()
            
            if caps:
                for i in range(caps.get_size()):
                    structure = caps.get_structure(i)
                    
                    # Get width
                    width = None
                    if structure.has_field("width"):
                        success, w = structure.get_int("width")
                        if success:
                            width = w
                    
                    # Get height
                    height = None
                    if structure.has_field("height"):
                        success, h = structure.get_int("height")
                        if success:
                            height = h
                    
                    # Get framerate (can be a fraction or a list)
                    fps_list = []
                    if structure.has_field("framerate"):
                        fps_value = structure.get_value("framerate")
                        if fps_value is not None:
                            # Could be a single fraction or a GstFractionRange
                            if hasattr(fps_value, 'num') and hasattr(fps_value, 'denom'):
                                if fps_value.denom > 0:
                                    fps_list.append(fps_value.num // fps_value.denom)
                            elif isinstance(fps_value, int):
                                fps_list.append(fps_value)
                    
                    # If no FPS found, try common values
                    if not fps_list:
                        fps_list = [30]
                    
                    if width and height:
                        for fps in fps_list:
                            # Ensure all values are integers
                            w_int = int(width)
                            h_int = int(height)
                            fps_int = int(fps) if fps else 30
                            
                            key = (w_int, h_int, fps_int)
                            if key not in seen:
                                seen.add(key)
                                modes.append({
                                    'width': w_int,
                                    'height': h_int,
                                    'fps': fps_int
                                })
        
        monitor.stop()
        
        # Sort by resolution (descending) then FPS (descending)
        modes.sort(key=lambda m: (m['width'] * m['height'], m['fps']), reverse=True)
        
        # If no modes found, return common defaults
        if not modes:
            modes = [
                {'width': 1920, 'height': 1080, 'fps': 30},
                {'width': 1280, 'height': 720, 'fps': 30},
                {'width': 640, 'height': 480, 'fps': 30},
            ]
        
        return modes
    
    @classmethod
    def from_pipeline(cls, pipeline_str):
        """
        Create a GStreamerWebcam from a custom pipeline string.
        
        The pipeline MUST include 'appsink name=sink' for frame retrieval.
        
        Example:
            cam = GStreamerWebcam.from_pipeline(
                "videotestsrc ! videoconvert ! video/x-raw,format=BGR ! appsink name=sink"
            )
        """
        return cls(custom_pipeline=pipeline_str)
        
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
