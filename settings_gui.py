"""
GStreamer Webcam Settings GUI

A PySide6 settings window that allows users to configure:
- Camera selection
- Resolution and FPS
- GPU acceleration
- Custom GStreamer pipeline
"""

import os
import sys
import signal
from pathlib import Path

# ============================================================================
# STANDALONE ENVIRONMENT CONFIGURATION
# This block must run BEFORE importing 'gi'
# ============================================================================

BASE_DIR = Path(sys.executable).resolve().parent
LOCAL_GST = BASE_DIR / "gstreamer"

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
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(BIN_PATH))
            print(f"DEBUG: os.add_dll_directory({BIN_PATH}) success")
        except Exception as e:
            print(f"DEBUG: os.add_dll_directory failed: {e}")
    
    # Add GStreamer's Python bindings to path ONLY in dev mode
    # In standalone mode, PyGObject is bundled by Nuitka
    if not LOCAL_GST.exists():  # Dev mode only
        gst_site_packages = GST_ROOT / "lib" / "site-packages"
        if gst_site_packages.exists() and str(gst_site_packages) not in sys.path:
            sys.path.insert(0, str(gst_site_packages))
            print(f"DEBUG: Added {gst_site_packages} to sys.path")
else:
    print(f"WARNING: GStreamer bin path not found at {BIN_PATH}")

# ============================================================================

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QCheckBox, QTextEdit, QPushButton, QGroupBox,
    QFormLayout, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import numpy as np
import cv2

from webcam_capture import GStreamerWebcam


# Fallback resolution presets (used if camera caps unavailable)
DEFAULT_RESOLUTIONS = [
    ("640x480 (VGA)", 640, 480),
    ("800x600 (SVGA)", 800, 600),
    ("1280x720 (HD)", 1280, 720),
    ("1920x1080 (Full HD)", 1920, 1080),
    ("2560x1440 (QHD)", 2560, 1440),
    ("3840x2160 (4K)", 3840, 2160),
]

DEFAULT_FPS_OPTIONS = [15, 24, 30, 60, 120]


class CameraPreview(QLabel):
    """Widget to display camera preview."""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 240)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #16213e;
                border-radius: 8px;
                color: #e94560;
                font-size: 14px;
            }
        """)
        self.setText("No camera feed")
    
    def update_frame(self, frame):
        """Update the preview with a new frame (numpy array, BGR format)."""
        if frame is None:
            return
        
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        
        # Convert BGR to RGB for Qt
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # Scale to fit while maintaining aspect ratio
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)


class SettingsWindow(QMainWindow):
    """Main settings window for camera configuration."""
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.preview_timer = None
        self.init_ui()
        self.refresh_cameras()
    
    def init_ui(self):
        self.setWindowTitle("GStreamer Webcam Settings")
        self.setMinimumSize(800, 600)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0f0f23;
                color: #cccccc;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1px solid #16213e;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                color: #e94560;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QComboBox, QTextEdit {
                background-color: #1a1a2e;
                border: 1px solid #16213e;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
                selection-background-color: #e94560;
            }
            QComboBox:hover, QTextEdit:focus {
                border-color: #e94560;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #e94560;
                margin-right: 10px;
            }
            QCheckBox {
                spacing: 8px;
                color: #cccccc;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #16213e;
                background-color: #1a1a2e;
            }
            QCheckBox::indicator:checked {
                background-color: #e94560;
                border-color: #e94560;
            }
            QPushButton {
                background-color: #16213e;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a1a2e;
                border: 1px solid #e94560;
            }
            QPushButton:pressed {
                background-color: #e94560;
            }
            QPushButton#startBtn {
                background-color: #e94560;
                font-size: 14px;
                padding: 12px 30px;
            }
            QPushButton#startBtn:hover {
                background-color: #ff6b6b;
            }
            QPushButton#stopBtn {
                background-color: #c0392b;
            }
            QPushButton#stopBtn:hover {
                background-color: #e74c3c;
            }
            QLabel {
                color: #cccccc;
            }
            QLabel#title {
                font-size: 24px;
                font-weight: bold;
                color: #e94560;
                padding: 10px;
            }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Left panel: Settings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        # Title
        title = QLabel("Camera Settings")
        title.setObjectName("title")
        left_layout.addWidget(title)
        
        # Camera selection group
        camera_group = QGroupBox("Camera")
        camera_form = QFormLayout(camera_group)
        
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_form.addRow("Device:", self.camera_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_cameras)
        camera_form.addRow("", refresh_btn)
        
        left_layout.addWidget(camera_group)
        
        # Resolution/FPS group
        video_group = QGroupBox("Video Settings")
        video_form = QFormLayout(video_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumWidth(200)
        video_form.addRow("Mode:", self.mode_combo)
        
        # Also keep manual override option
        self.manual_group = QGroupBox("Manual Override")
        self.manual_group.setCheckable(True)
        self.manual_group.setChecked(False)
        manual_form = QFormLayout(self.manual_group)
        
        self.resolution_combo = QComboBox()
        for name, w, h in DEFAULT_RESOLUTIONS:
            self.resolution_combo.addItem(name, (w, h))
        self.resolution_combo.setCurrentIndex(2)  # Default to 1280x720
        manual_form.addRow("Resolution:", self.resolution_combo)
        
        self.fps_combo = QComboBox()
        for fps in DEFAULT_FPS_OPTIONS:
            self.fps_combo.addItem(f"{fps} FPS", fps)
        self.fps_combo.setCurrentIndex(2)  # Default to 30
        manual_form.addRow("Frame Rate:", self.fps_combo)
        
        video_form.addRow(self.manual_group)
        
        left_layout.addWidget(video_group)
        
        # GPU acceleration group
        gpu_group = QGroupBox("Acceleration")
        gpu_layout = QVBoxLayout(gpu_group)
        
        self.gpu_checkbox = QCheckBox("Enable D3D11 GPU Acceleration")
        self.gpu_checkbox.setToolTip("Use DirectX 11 for hardware-accelerated video conversion")
        gpu_layout.addWidget(self.gpu_checkbox)
        
        left_layout.addWidget(gpu_group)
        
        # Custom pipeline group
        pipeline_group = QGroupBox("Custom Pipeline (Advanced)")
        pipeline_layout = QVBoxLayout(pipeline_group)
        
        pipeline_hint = QLabel("Leave empty to use settings above.\nMust include 'appsink name=sink'.")
        pipeline_hint.setStyleSheet("color: #888888; font-size: 11px;")
        pipeline_layout.addWidget(pipeline_hint)
        
        self.pipeline_edit = QTextEdit()
        self.pipeline_edit.setMaximumHeight(80)
        self.pipeline_edit.setPlaceholderText(
            "e.g.: dshowvideosrc device-index=0 ! videoconvert ! "
            "video/x-raw,format=BGR ! appsink name=sink emit-signals=true"
        )
        pipeline_layout.addWidget(self.pipeline_edit)
        
        left_layout.addWidget(pipeline_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self.start_camera)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()
        
        # Right panel: Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e94560;")
        right_layout.addWidget(preview_label)
        
        self.preview = CameraPreview()
        right_layout.addWidget(self.preview, 1)
        
        # Status
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: #888888; padding: 5px;")
        right_layout.addWidget(self.status_label)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
    
    def refresh_cameras(self):
        """Refresh the list of available cameras."""
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        
        try:
            cameras = GStreamerWebcam.list_cameras()
            for cam in cameras:
                self.camera_combo.addItem(f"{cam['index']}: {cam['name']}", cam['index'])
            
            if cameras:
                self.status_label.setText(f"Status: Found {len(cameras)} camera(s)")
            else:
                self.status_label.setText("Status: No cameras found")
        except Exception as e:
            self.status_label.setText(f"Status: Error listing cameras: {e}")
            # Add fallback entries
            for i in range(4):
                self.camera_combo.addItem(f"{i}: Camera {i}", i)
        
        self.camera_combo.blockSignals(False)
        
        # Trigger mode refresh for first camera
        if self.camera_combo.count() > 0:
            self.on_camera_changed(0)
    
    def on_camera_changed(self, index):
        """Called when camera selection changes. Updates available modes."""
        camera_index = self.camera_combo.currentData()
        if camera_index is None:
            return
        
        self.mode_combo.clear()
        
        try:
            modes = GStreamerWebcam.get_camera_modes(camera_index)
            
            # Group modes by resolution, show max FPS for each
            seen_resolutions = {}
            for mode in modes:
                key = (mode['width'], mode['height'])
                if key not in seen_resolutions or mode['fps'] > seen_resolutions[key]['fps']:
                    seen_resolutions[key] = mode
            
            # Add all unique modes
            for mode in modes:
                # Ensure values are integers for display
                w = int(mode['width'])
                h = int(mode['height'])
                fps = int(mode['fps'])
                label = f"{w}x{h} @ {fps} FPS"
                # Store as integers
                mode_data = {'width': w, 'height': h, 'fps': fps}
                self.mode_combo.addItem(label, mode_data)
            
            if modes:
                self.status_label.setText(f"Status: Found {len(modes)} mode(s) for camera {camera_index}")
            else:
                self.status_label.setText("Status: No modes detected, using defaults")
                self._add_default_modes()
                
        except Exception as e:
            print(f"Error getting camera modes: {e}")
            self.status_label.setText(f"Status: Using default modes")
            self._add_default_modes()
    
    def _add_default_modes(self):
        """Add default resolution/FPS modes as fallback."""
        default_modes = [
            {'width': 1920, 'height': 1080, 'fps': 30},
            {'width': 1280, 'height': 720, 'fps': 30},
            {'width': 640, 'height': 480, 'fps': 30},
        ]
        for mode in default_modes:
            label = f"{mode['width']}x{mode['height']} @ {mode['fps']} FPS"
            self.mode_combo.addItem(label, mode)
    
    def start_camera(self):
        """Start the camera with current settings."""
        self.stop_camera()  # Stop any existing camera
        
        try:
            custom_pipeline = self.pipeline_edit.toPlainText().strip()
            
            if custom_pipeline:
                # Use custom pipeline
                self.camera = GStreamerWebcam.from_pipeline(custom_pipeline)
            else:
                # Use GUI settings
                camera_id = self.camera_combo.currentData() or 0
                use_gpu = self.gpu_checkbox.isChecked()
                
                # Check if manual override is enabled
                if self.manual_group.isChecked():
                    width, height = self.resolution_combo.currentData() or (1280, 720)
                    fps = self.fps_combo.currentData() or 30
                else:
                    # Use selected mode from camera capabilities
                    mode = self.mode_combo.currentData()
                    if mode:
                        width = mode['width']
                        height = mode['height']
                        fps = mode['fps']
                    else:
                        width, height, fps = 1280, 720, 30
                
                print(f"Starting camera {camera_id} at {width}x{height}@{fps}fps (GPU: {use_gpu})")
                
                self.camera = GStreamerWebcam(
                    camera_id=camera_id,
                    width=width,
                    height=height,
                    fps=fps,
                    use_gpu=use_gpu
                )
            
            self.camera.start()
            
            # Start preview timer
            self.preview_timer = QTimer()
            self.preview_timer.timeout.connect(self.update_preview)
            self.preview_timer.start(33)  # ~30 FPS preview
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Status: Camera running")
            self.status_label.setStyleSheet("color: #27ae60; padding: 5px;")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start camera:\n{e}")
            self.status_label.setText(f"Status: Error - {e}")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 5px;")
    
    def stop_camera(self):
        """Stop the camera."""
        if self.preview_timer:
            self.preview_timer.stop()
            self.preview_timer = None
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.preview.setText("No camera feed")
        self.preview.setPixmap(QPixmap())
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet("color: #888888; padding: 5px;")
    
    def update_preview(self):
        """Update the preview with the latest frame."""
        if self.camera:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                self.preview.update_frame(frame)
    
    def closeEvent(self, event):
        """Clean up when window is closed."""
        self.stop_camera()
        event.accept()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = SettingsWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

