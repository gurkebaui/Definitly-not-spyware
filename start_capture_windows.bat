@echo off
echo === CHIMERA DATA RECORDER (Windows) ===
echo Installing dependencies...
pip install opencv-python sounddevice soundfile pynput mss numpy
echo.
echo Starting Recorder...
python capture_data_windows.py
pause