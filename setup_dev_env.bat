@echo off
echo Setting up GStreamer Development Environment...

REM GStreamer Root
set GST_ROOT=C:\gstreamer\1.0\msvc_x86_64

REM Check if GStreamer is installed
if not exist "%GST_ROOT%" (
    echo [ERROR] GStreamer not found at %GST_ROOT%
    echo Please install GStreamer MSVC 64-bit first.
    pause
    exit /b 1
)

REM Add BIN to PATH (for DLLs)
set PATH=%GST_ROOT%\bin;%PATH%

REM Set Plugin Path
set GST_PLUGIN_PATH=%GST_ROOT%\lib\gstreamer-1.0

REM Set PYTHONPATH to use bundled bindings (if using matching Python version)
set PYTHONPATH=%GST_ROOT%\lib\site-packages;%PYTHONPATH%

echo.
echo [OK] Environment configured!
echo.
echo Python Version:
python --version
echo.
echo You can now run: python webcam_capture.py
echo.
cmd /k


