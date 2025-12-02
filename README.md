# Standalone GStreamer Webcam for Windows

**Zero-Dependency Deployment:** The final application runs on any Windows machine without installing GStreamer or Python.

## ⚠️ CRITICAL PREREQUISITE: Python Version Match

**You are using GStreamer 1.22+ which bundles Python bindings for Python 3.8, 3.9, 3.10, 3.11, 3.12.**

**HOWEVER**, the installer you used (MSVC) seems to only have installed the **Python 3.12 bindings** (checked via file inspection).

**You must use Python 3.12** for development, OR compile PyGObject yourself.

### Option A: Switch to Python 3.12 (Easiest)
1. Install Python 3.12.
2. Re-create your environment:
   ```bash
   py -3.12 -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   pip install nuitka
   ```
3. Point to the bundled GStreamer bindings:
   ```bash
   set PYTHONPATH=C:\gstreamer\1.0\msvc_x86_64\lib\site-packages;%PYTHONPATH%
   ```

### Option B: Compile for Python 3.10 (Harder)
1. Re-install **GStreamer Development MSI** and ensure **"Complete"** is selected (you are missing header files).
2. Install `pkg-config` support.
3. Run `pip install PyGObject` again.

---

## 1. Developer Setup (Once Requirements Met)

1.  **Install GStreamer (MSVC 64-bit)** to `C:\gstreamer\1.0\msvc_x86_64`.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install nuitka
    ```

## 2. Build Standalone App

Run the build script. It compiles your Python code and bundles the GStreamer DLLs automatically.

```bash
python build_standalone.py
```

## 3. Deploy

*   Go to the `build/` folder.
*   Copy the `webcam_capture.dist` folder to any other computer.
*   Run `webcam_capture.exe`.

**That's it! No installers needed on the target machine.**

## How It Works

*   **Self-Configuration:** `webcam_capture.py` detects if it's running as a frozen exe.
*   **Environment Injection:** It sets `PATH` and `GST_PLUGIN_PATH` to point to the bundled `gstreamer/` folder before loading the library.
*   **Lag Prevention:** Uses GStreamer's `appsink` with `drop=true` and `max-buffers=1` to ensure the webcam feed never lags.
