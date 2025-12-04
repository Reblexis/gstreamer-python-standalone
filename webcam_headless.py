"""
Headless webcam capture example (no GUI)
Useful for background processing, saving frames, etc.
Cross-platform: Windows and Linux
"""
import sys
from pathlib import Path

# Platform detection
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import time
from datetime import datetime


class HeadlessWebcam:
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        Gst.init(None)
        
        self.width = width
        self.height = height
        self.fps = fps
        self.camera_id = camera_id
        self.frame = None
        self.frame_count = 0
        self.running = False
        self.frame_callback = None
        
        # Platform-specific source
        if IS_WINDOWS:
            source = f"ksvideosrc device-index={camera_id}"
        else:
            device_path = f"/dev/video{camera_id}"
            source = f"v4l2src device={device_path}"
        
        # Simple pipeline - let camera output native format, then convert
        pipeline_str = (
            f"{source} ! "
            f"videoconvert ! "
            f"videoscale ! "
            f"video/x-raw,format=BGR,width={width},height={height} ! "
            f"appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsink = self.pipeline.get_by_name('sink')
        self.appsink.connect('new-sample', self.on_new_sample)
    
    def on_new_sample(self, sink):
        sample = sink.emit('pull-sample')
        if sample:
            buffer = sample.get_buffer()
            
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                self.frame = frame_data.reshape((self.height, self.width, 3))
                self.frame_count += 1
                
                if self.running and self.frame_callback:
                    self.frame_callback(self.frame, self.frame_count)
                
                buffer.unmap(map_info)
        
        return Gst.FlowReturn.OK
    
    def start(self, callback=None):
        self.frame_callback = callback
        self.running = True
        self.pipeline.set_state(Gst.State.PLAYING)
    
    def stop(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
    
    def get_latest_frame(self):
        return self.frame.copy() if self.frame is not None else None


def main():
    print("Starting headless webcam capture...")
    print("This runs in the background without a GUI window")
    print("Press Ctrl+C to stop\n")
    
    start_time = time.time()
    
    def on_frame(frame, frame_count):
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        if frame_count % 30 == 0:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Frame {frame_count:5d} | FPS: {fps:.1f} | Shape: {frame.shape}")
    
    camera = HeadlessWebcam(camera_id=0, width=640, height=480, fps=30)
    camera.start(callback=on_frame)
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
    
    camera.stop()
    
    elapsed = time.time() - start_time
    print(f"\nCaptured {camera.frame_count} frames in {elapsed:.1f}s")
    print(f"Average FPS: {camera.frame_count / elapsed:.1f}")


if __name__ == "__main__":
    main()
