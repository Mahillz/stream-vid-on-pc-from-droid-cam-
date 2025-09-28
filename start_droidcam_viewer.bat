@echo off
title DroidCam Web Viewer - Ultra-Smooth Streaming
echo.
echo ========================================
echo   DroidCam Web Viewer - Starting...
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ and try again
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting DroidCam Web Viewer with AMD optimizations...
echo.
echo Web interface will be available at:
echo   http://127.0.0.1:8080
echo   http://localhost:8080
echo.
echo Features enabled:
echo   - Ultra-smooth streaming algorithms
echo   - WebGL GPU acceleration (bypasses AMD detection issues)
echo   - Adaptive jitter buffering
echo   - Cinema-grade smoothing options
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the Flask app
python cv.py

echo.
echo DroidCam Web Viewer stopped.
pause
