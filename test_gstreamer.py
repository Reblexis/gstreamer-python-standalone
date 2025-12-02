"""
Quick test to verify GStreamer is installed and working
"""
import sys

def test_gstreamer_import():
    print("Testing GStreamer installation...")
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        print("✓ GStreamer Python bindings (PyGObject) found")
        return True
    except ImportError as e:
        print(f"✗ Failed to import GStreamer: {e}")
        print("\nInstall PyGObject:")
        print("  pip install PyGObject")
        return False


def test_gstreamer_version():
    print("\nChecking GStreamer version...")
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        version = Gst.version_string()
        print(f"✓ {version}")
        return True
    except Exception as e:
        print(f"✗ Error initializing GStreamer: {e}")
        return False


def test_opencv():
    print("\nTesting OpenCV...")
    try:
        import cv2
        print(f"✓ OpenCV version: {cv2.__version__}")
        return True
    except ImportError:
        print("✗ OpenCV not found")
        print("  pip install opencv-python")
        return False


def test_numpy():
    print("\nTesting NumPy...")
    try:
        import numpy as np
        print(f"✓ NumPy version: {np.__version__}")
        return True
    except ImportError:
        print("✗ NumPy not found")
        print("  pip install numpy")
        return False


def test_camera_detection():
    print("\nTesting camera detection...")
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        
        # Try to create a simple pipeline
        pipeline_str = "ksvideosrc device-index=0 ! fakesink"
        pipeline = Gst.parse_launch(pipeline_str)
        
        result = pipeline.set_state(Gst.State.PLAYING)
        if result == Gst.StateChangeReturn.FAILURE:
            print("✗ Failed to access camera")
            print("  Try: gst-device-monitor-1.0 to list cameras")
            pipeline.set_state(Gst.State.NULL)
            return False
        
        print("✓ Camera accessible")
        pipeline.set_state(Gst.State.NULL)
        return True
    except Exception as e:
        print(f"✗ Camera test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("GStreamer Webcam - Environment Test")
    print("=" * 60)
    
    tests = [
        test_numpy,
        test_opencv,
        test_gstreamer_import,
        test_gstreamer_version,
        test_camera_detection,
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ ALL TESTS PASSED - Ready to use!")
    else:
        print("✗ Some tests failed - see above for fixes")
        print("\nFor detailed setup instructions, see WINDOWS_SETUP.md")
    print("=" * 60)


if __name__ == "__main__":
    main()


