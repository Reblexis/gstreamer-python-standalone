"""
List all available cameras using GStreamer
Cross-platform: Windows and Linux
"""
import sys

# Import platform detection and GStreamer setup from webcam_capture
# This ensures GStreamer is properly configured before we import gi
from webcam_capture import IS_WINDOWS, IS_LINUX

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


def list_cameras():
    Gst.init(None)
    
    print("Available Video Devices:")
    print("=" * 60)
    
    # Use device monitor (works on both platforms)
    monitor = Gst.DeviceMonitor.new()
    monitor.add_filter("Video/Source", None)
    monitor.start()
    
    devices = monitor.get_devices()
    
    if devices:
        for i, device in enumerate(devices):
            name = device.get_display_name()
            device_class = device.get_device_class()
            caps = device.get_caps()
            
            print(f"\n✓ Camera {i}: {name}")
            print(f"  Class: {device_class}")
            
            # Show some capabilities
            if caps:
                print(f"  Formats: ", end="")
                formats = set()
                for j in range(min(caps.get_size(), 10)):  # Limit to first 10
                    structure = caps.get_structure(j)
                    fmt = structure.get_name()
                    formats.add(fmt)
                print(", ".join(formats))
    else:
        print("No cameras detected via device monitor.")
        print("\nTrying manual probe...")
        
        # Manual probe for cameras
        if IS_WINDOWS:
            sources = ["mfvideosrc", "dshowvideosrc", "ksvideosrc"]
        else:
            sources = ["v4l2src"]
        
        for source_type in sources:
            print(f"\nProbing {source_type}:")
            for i in range(5):
                try:
                    if IS_LINUX and source_type == "v4l2src":
                        # v4l2src uses device path
                        pipeline_str = f"v4l2src device=/dev/video{i} ! fakesink"
                    else:
                        pipeline_str = f"{source_type} device-index={i} ! fakesink"
                    
                    pipeline = Gst.parse_launch(pipeline_str)
                    result = pipeline.set_state(Gst.State.READY)
                    
                    if result != Gst.StateChangeReturn.FAILURE:
                        print(f"  ✓ Device {i}: Available")
                    
                    pipeline.set_state(Gst.State.NULL)
                except Exception as e:
                    pass  # Device doesn't exist
    
    monitor.stop()
    
    print("\n" + "=" * 60)
    print("\nTo use a camera, set camera_id in your code:")
    print("  camera = GStreamerWebcam(camera_id=0)")
    
    if IS_LINUX:
        print("\nNote: On Linux, camera_id maps to /dev/video{id*2}")
        print("      (e.g., camera_id=0 → /dev/video0)")


if __name__ == "__main__":
    try:
        list_cameras()
    except Exception as e:
        print(f"Error: {e}")
        if IS_WINDOWS:
            print("\nMake sure GStreamer is installed and in PATH")
            print("See WINDOWS_SETUP.md for instructions")
        else:
            print("\nMake sure GStreamer is installed")
            print("See LINUX_SETUP.md for instructions")
