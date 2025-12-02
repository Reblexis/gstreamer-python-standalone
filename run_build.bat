@echo off
set GST_ROOT=C:\gstreamer\1.0\msvc_x86_64
set PYTHONPATH=%GST_ROOT%\lib\site-packages;%PYTHONPATH%
set PATH=%GST_ROOT%\bin;%PATH%

echo Building with Python 3.12...
venv\Scripts\python build_standalone.py


