import os
import sys
import signal
from pathlib import Path

# ============================================================================
# STANDALONE ENVIRONMENT CONFIGURATION
# This block must run BEFORE importing 'gi'
# Supports both Windows and Linux
# ============================================================================

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

BASE_DIR = Path(sys.executable).resolve().parent
LOCAL_GST = BASE_DIR / "gstreamer"

def _configure_gstreamer_windows():
    """Configure GStreamer paths for Windows."""
    global GST_ROOT, BIN_PATH, LIB_PATH, PLUGIN_PATH
    
    if LOCAL_GST.exists():
        GST_ROOT = LOCAL_GST
        print(f"DEBUG: Detected standalone mode at {GST_ROOT}")
    elif getattr(sys, 'frozen', False):
        GST_ROOT = LOCAL_GST
        print(f"WARNING: Frozen mode detected but {GST_ROOT} missing!")
    else:
        GST_ROOT = Path(r"C:\gstreamer\1.0\msvc_x86_64")
        print(f"DEBUG: Detected dev mode at {GST_ROOT}")
    
    BIN_PATH = GST_ROOT / "bin"
    LIB_PATH = GST_ROOT / "lib"
    PLUGIN_PATH = LIB_PATH / "gstreamer-1.0"
    
    if BIN_PATH.exists():
        print(f"DEBUG: Configuring GStreamer from {GST_ROOT}")
        
        os.environ['PATH'] = str(BIN_PATH) + os.pathsep + os.environ.get('PATH', '')
        os.environ['PYGI_DLL_DIRS'] = str(BIN_PATH)
        os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
        
        registry = BASE_DIR / "registry.bin" if getattr(sys, 'frozen', False) else Path("registry.bin")
        os.environ['GST_REGISTRY'] = str(registry)
        
        scanner = LIB_PATH / "gstreamer-1.0" / "gst-plugin-scanner.exe"
        if not scanner.exists():
            scanner = BIN_PATH / "gst-plugin-scanner.exe"
        if scanner.exists():
            os.environ['GST_PLUGIN_SCANNER'] = str(scanner)
        
        # CRITICAL: Modern Python DLL loading (Python 3.8+)
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(str(BIN_PATH))
                print(f"DEBUG: os.add_dll_directory({BIN_PATH}) success")
            except Exception as e:
                print(f"DEBUG: os.add_dll_directory failed: {e}")
        
        # Add GStreamer's Python bindings to path ONLY in dev mode
        if not LOCAL_GST.exists():
            gst_site_packages = GST_ROOT / "lib" / "site-packages"
            if gst_site_packages.exists() and str(gst_site_packages) not in sys.path:
                sys.path.insert(0, str(gst_site_packages))
                print(f"DEBUG: Added {gst_site_packages} to sys.path")
    else:
        print(f"WARNING: GStreamer bin path not found at {BIN_PATH}")


def _configure_gstreamer_linux():
    """Configure GStreamer paths for Linux."""
    global GST_ROOT, BIN_PATH, LIB_PATH, PLUGIN_PATH
    
    if LOCAL_GST.exists():
        # Standalone mode: bundled GStreamer
        GST_ROOT = LOCAL_GST
        LIB_PATH = GST_ROOT / "lib"
        BIN_PATH = GST_ROOT / "bin"
        PLUGIN_PATH = GST_ROOT / "plugins"
        
        print(f"DEBUG: Detected standalone mode at {GST_ROOT}")
        
        # Set library path for bundled libs
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        os.environ['LD_LIBRARY_PATH'] = str(LIB_PATH) + os.pathsep + ld_path
        
        # Set plugin path
        os.environ['GST_PLUGIN_PATH'] = str(PLUGIN_PATH)
        
        # Registry file
        os.environ['GST_REGISTRY'] = str(BASE_DIR / "registry.bin")
        
        # Plugin scanner
        scanner = BIN_PATH / "gst-plugin-scanner"
        if scanner.exists():
            os.environ['GST_PLUGIN_SCANNER'] = str(scanner)
        
        # GI typelibs path for bundled typelibs
        gi_typelib_path = GST_ROOT / "lib" / "girepository-1.0"
        if gi_typelib_path.exists():
            existing = os.environ.get('GI_TYPELIB_PATH', '')
            os.environ['GI_TYPELIB_PATH'] = str(gi_typelib_path) + os.pathsep + existing
    else:
        # Dev mode: use system GStreamer (installed via apt)
        GST_ROOT = None
        BIN_PATH = None
        LIB_PATH = None
        PLUGIN_PATH = None
        print("DEBUG: Using system GStreamer")


# Apply platform-specific configuration
if IS_WINDOWS:
    _configure_gstreamer_windows()
elif IS_LINUX:
    _configure_gstreamer_linux()
else:
    print(f"WARNING: Unsupported platform {sys.platform}, assuming system GStreamer")

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
import re


class GStreamerWebcam:
    """
    GStreamer-based webcam capture with optional GPU acceleration.
    Cross-platform: supports Windows and Linux.
    
    Args:
        camera_id: Camera device index (0, 1, 2...)
        width: Desired frame width
        height: Desired frame height
        fps: Desired frames per second
        use_gpu: Enable GPU acceleration (D3D11 on Windows, disabled on Linux)
        custom_pipeline: Override all settings with a custom GStreamer pipeline string.
                        Must include 'appsink name=sink' for frame retrieval.
    """
    
    def __init__(self, camera_id=0, width=640, height=480, fps=30, use_gpu=False, custom_pipeline=None):
        Gst.init(None)
        
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.camera_id = int(camera_id)
        self.use_gpu = use_gpu and IS_WINDOWS  # GPU only supported on Windows currently
        self.frame = None
        self.new_frame = False
        self.running = False
        
        if custom_pipeline:
            print(f"Using custom pipeline...")
            try:
                self.pipeline = Gst.parse_launch(custom_pipeline)
                print(f"✓ Custom pipeline parsed successfully")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to parse custom pipeline: {e}")
                raise RuntimeError(f"Invalid pipeline: {e}")
        else:
            self._build_auto_pipeline()
        
        print(f"Launching pipeline...")
        self.appsink = self.pipeline.get_by_name('sink')
        if not self.appsink:
            raise RuntimeError("Pipeline must contain 'appsink name=sink'")
        self.appsink.connect('new-sample', self.on_new_sample)
    
    def _get_camera_sources(self):
        """Get platform-specific camera sources in order of preference."""
        if IS_WINDOWS:
            return [
                f"mfvideosrc device-index={self.camera_id}",
                f"dshowvideosrc device-index={self.camera_id}",
                f"ksvideosrc device-index={self.camera_id}"
            ]
        elif IS_LINUX:
            # v4l2src uses device path, not index
            # /dev/video0, /dev/video2, etc. (even numbers are usually capture devices)
            device_path = f"/dev/video{self.camera_id * 2}"  # Try even indices first
            alt_device_path = f"/dev/video{self.camera_id}"
            return [
                f"v4l2src device={device_path}",
                f"v4l2src device={alt_device_path}",
            ]
        else:
            # Fallback: try autovideosrc
            return ["autovideosrc"]
    
    def _get_gpu_convert_chain(self):
        """Get platform-specific GPU conversion chain."""
        if self.use_gpu and IS_WINDOWS:
            print("GPU acceleration: ENABLED (D3D11)")
            return (
                "d3d11upload ! "
                "d3d11convert ! "
                "d3d11download ! "
                "videoconvert ! "
            )
        else:
            if self.use_gpu and IS_LINUX:
                print("GPU acceleration: Not implemented for Linux, using software")
            else:
                print("GPU acceleration: DISABLED")
            return "videoconvert ! "
    
    def _build_auto_pipeline(self):
        """Build pipeline automatically, trying different camera sources."""
        sources = self._get_camera_sources()
        convert_chain = self._get_gpu_convert_chain()
        
        pipeline_str = None
        last_error = None
        
        print(f"Target: {self.width}x{self.height}@{self.fps}fps")
        
        # On Linux, v4l2src outputs raw video - no decodebin needed
        # On Windows, sources may output MJPEG so decodebin is useful
        use_decodebin = IS_WINDOWS
        decode_element = "decodebin ! " if use_decodebin else ""
        
        # Strategy 1: Full pipeline with framerate control
        for source in sources:
            try:
                source_name = source.split()[0]
                print(f"Trying source: {source_name}...")
                
                test_str = (
                    f"{source} do-timestamp=true ! "
                    f"{decode_element}"
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
        
        # Strategy 2: Simpler pipeline without videorate
        if pipeline_str is None:
            print("Trying simpler pipeline without framerate control...")
            for source in sources:
                try:
                    source_name = source.split()[0]
                    test_str = (
                        f"{source} do-timestamp=true ! "
                        f"{decode_element}"
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
        
        # Strategy 3: Minimal pipeline
        if pipeline_str is None:
            print("Trying minimal pipeline...")
            for source in sources:
                try:
                    source_name = source.split()[0]
                    test_str = (
                        f"{source} ! "
                        f"{decode_element}"
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
        
        monitor = Gst.DeviceMonitor.new()
        monitor.add_filter("Video/Source", None)
        
        try:
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
        finally:
            monitor.stop()
        
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
        
        monitor = Gst.DeviceMonitor.new()
        monitor.add_filter("Video/Source", None)
        
        try:
            monitor.start()
            devices = monitor.get_devices()
            if camera_index < len(devices):
                device = devices[camera_index]
                caps = device.get_caps()
                
                if caps:
                    for i in range(caps.get_size()):
                        structure = caps.get_structure(i)
                        
                        width = None
                        if structure.has_field("width"):
                            success, w = structure.get_int("width")
                            if success:
                                width = w
                        
                        height = None
                        if structure.has_field("height"):
                            success, h = structure.get_int("height")
                            if success:
                                height = h
                        
                        fps_list = []
                        if structure.has_field("framerate"):
                            # Try single fraction first
                            success, fps_num, fps_denom = structure.get_fraction("framerate")
                            if success and fps_denom > 0:
                                fps_list.append(fps_num // fps_denom)
                            else:
                                # Framerate is a list - parse from string representation
                                # Format: framerate=(fraction){ 30/1, 24/1, ... }
                                s_str = structure.to_string()
                                match = re.search(r'framerate=\(fraction\)\{([^}]+)\}', s_str)
                                if match:
                                    fractions = re.findall(r'(\d+)/(\d+)', match.group(1))
                                    for num, denom in fractions:
                                        fps = int(num) // int(denom)
                                        if fps not in fps_list:
                                            fps_list.append(fps)
                        
                        if not fps_list:
                            fps_list = [30]
                        
                        if width and height:
                            for fps in fps_list:
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
        finally:
            monitor.stop()
        
        modes.sort(key=lambda m: (m['width'] * m['height'], m['fps']), reverse=True)
        
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
            
            structure = caps.get_structure(0)
            self.height = structure.get_value("height")
            self.width = structure.get_value("width")
            
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                try:
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
            return True, self.frame.copy()
        return False, None
    
    def release(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)


def main():
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
