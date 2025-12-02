@echo off
setlocal

echo ========================================================
echo STANDALONE VERIFICATION TEST
echo ========================================================
echo.
echo 1. Clearing Environment Variables...

REM Clear Python variables
set PYTHONPATH=
set PYTHONHOME=

REM Clear GStreamer variables
set GST_PLUGIN_PATH=
set GST_PLUGIN_SYSTEM_PATH=
set GST_REGISTRY=
set GST_REGISTRY_UPDATE=
set PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem

echo.
echo 2. Environment is now minimal:
echo    PATH=%PATH%
echo    PYTHONPATH=%PYTHONPATH% (Should be empty)
echo    GST_PLUGIN_PATH=%GST_PLUGIN_PATH% (Should be empty)
echo.
echo 3. Launching Application...
echo    If this works, it is truly standalone!
echo.

build\webcam_capture.dist\webcam_capture.exe

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] Application crashed or failed to start.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Application closed normally.
pause


