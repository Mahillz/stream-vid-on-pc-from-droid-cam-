# DroidCam Web Viewer (Ultra-Smooth Streaming)

A Flask-based web app that proxies your phone's DroidCam stream to your PC with ultra-smooth playback.

Features include adaptive jitter buffering, multi-level temporal smoothing, performance monitoring, and AMD-friendly optimizations.

## Features
- Auto-detects DroidCam MJPEG endpoints (`/video`, `/mjpegfeed`, base URL)
- Correct MJPEG boundary/header forwarding, no-cache streaming
- Quality, FPS, and buffer controls (including XXL 128KB)
- Smoothing levels: `basic`, `enhanced`, `ultra`, `cinema`
- Adaptive jitter buffer and timing prediction
- Real-time CPU/RAM stats and hardware summary
- Fullscreen toggle and keyboard shortcuts (Ctrl+S/Q/F/R)

## Requirements
Python 3.9+ recommended.

Install dependencies:
```bash
pip install -r requirements.txt
```

## Run
```bash
python cv.py
```
Open the app at:
- http://127.0.0.1:8080

## Usage
1. Enter your phone's IP and port (DroidCam default port: `4747`).
2. Click "Scan Endpoints" to verify available streams.
3. Choose `Quality`, `FPS`, `Buffer`, and `Smoothing`.
4. Click "Start Stream".

## Tips for Smoothest Playback
- Set Smoothing to `Ultra` or `Cinema`.
- Use `XXL (128KB)` buffer on stable networks.
- 24 FPS provides a cinematic baseline; 60 FPS aims for ultra-fluid motion.

## Hardware Acceleration (Optional)
AMD OpenCL acceleration is detected via OpenCV if available. Ensure:
- Latest AMD drivers installed
- OpenCV with OpenCL support present

## API Endpoints
- `GET /` – Web UI
- `GET /stream?ip=...&port=...&quality=...&fps=...&buffer=...&smoothing=...` – MJPEG proxy
- `GET /api/scan?ip=...&port=...` – Probe available endpoints and content-types
- `GET /api/system-stats` – CPU/RAM and basic GPU status

## Notes
- Avoid opening DroidCam in multiple apps simultaneously (it may report "Busy or Unavailable").
- This app focuses on MJPEG. Other formats may be listed but are not proxied here.

## Development
Common commands:
```bash
git add -A
git commit -m "Your change"
git push
```

## License
MIT
