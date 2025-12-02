"""
List all available cameras using GStreamer
"""
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

def list_cameras():
    Gst.init(None)
    
    print("Available Video Devices:")
    print("=" * 60)
    
    # Test multiple camera indices
    for i in range(5):
        pipeline_str = f"ksvideosrc device-index={i} ! fakesink"
        pipeline = Gst.parse_launch(pipeline_str)
        
        result = pipeline.set_state(Gst.State.READY)
        
        if result != Gst.StateChangeReturn.FAILURE:
            print(f"✓ Camera {i}: Available")
            
            # Try to get more info
            source = pipeline.get_by_name("ksvideosrc0")
            if source:
                device_name = source.get_property("device-name")
                if device_name:
                    print(f"  Name: {device_name}")
        else:
            print(f"✗ Camera {i}: Not found")
        
        pipeline.set_state(Gst.State.NULL)
    
    print("=" * 60)
    print("\nTo use a camera, set camera_id in your code:")
    print("  camera = GStreamerWebcam(camera_id=0)")


if __name__ == "__main__":
    try:
        list_cameras()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure GStreamer is installed and in PATH")
        print("See WINDOWS_SETUP.md for instructions")


