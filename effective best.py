import asyncio
import aiohttp
import time
import logging
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import cv2
import numpy as np
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DroidCam Optimized Viewer - Enhanced Performance")


class DroidCamStreamer:
    def __init__(self):
        self.session = None
        self.stats = {
            'frames_processed': 0,
            'bytes_transferred': 0,
            'start_time': None,
            'last_frame_time': None,
            'connection_count': 0,
            'errors': 0
        }

    async def get_session(self):
        if self.session is None or self.session.closed:
            # Optimized connection settings for better performance
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'DroidCam-Optimized-Viewer/2.0'}
            )
            logger.info("🚀 Optimized session created with enhanced connection pooling")
        return self.session

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def scan_endpoints(self, ip: str, port: int = 4747) -> dict:
        """Scan DroidCam endpoints to find available streams"""
        endpoints = [
            f"http://{ip}:{port}/video",
            f"http://{ip}:{port}/mjpegfeed",
            f"http://{ip}:{port}/"
        ]

        results = {}
        session = await self.get_session()

        for endpoint in endpoints:
            try:
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'multipart/x-mixed-replace' in content_type or 'image/jpeg' in content_type:
                        results[endpoint] = {
                            'status': 'available',
                            'content_type': content_type,
                            'status_code': response.status
                        }
                    else:
                        results[endpoint] = {
                            'status': 'not_mjpeg',
                            'content_type': content_type,
                            'status_code': response.status
                        }
            except Exception as e:
                results[endpoint] = {
                    'status': 'error',
                    'error': str(e)
                }

        return results

    async def stream_with_fps_limit(
            self,
            ip: str,
            port: int = 4747,
            fps_limit: Optional[float] = None,
            drop_strategy: str = "none",
            resolution: str = "auto",
            quality: str = "high"
    ) -> AsyncGenerator[bytes, None]:
        """Stream MJPEG with FPS limiting, frame dropping, resolution and quality control"""
        
        # Initialize stats
        if not self.stats['start_time']:
            self.stats['start_time'] = datetime.now()
            logger.info(f"🎬 Starting optimized stream: {resolution} {quality} quality @ {fps_limit or 'unlimited'} FPS")

        # Try more DroidCam endpoints including newer versions
        endpoints = [
            f"http://{ip}:{port}/mjpegfeed",
            f"http://{ip}:{port}/video",
            f"http://{ip}:{port}/cam/1/stream",
            f"http://{ip}:{port}/cam/1/mjpeg",
            f"http://{ip}:{port}/",
            f"http://{ip}:{port}/stream"
        ]

        session = await self.get_session()

        for endpoint in endpoints:
            try:
                print(f"Trying endpoint: {endpoint}")
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    print(f"Response status: {response.status}")
                    print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")

                    if response.status != 200:
                        continue

                    content_type = response.headers.get('content-type', '').lower()

                    # Accept both multipart and direct JPEG streams
                    if 'multipart/x-mixed-replace' in content_type or 'image/jpeg' in content_type:
                        print(f"Found valid stream at {endpoint}")

                        frame_interval = 1.0 / fps_limit if fps_limit else 0
                        last_frame_time = 0

                        # Optimized chunk size based on quality setting
                        chunk_size = {
                            'high': 16384,    # 16KB for high quality
                            'medium': 12288,  # 12KB for medium quality  
                            'low': 8192       # 8KB for low quality (faster)
                        }.get(quality, 12288)
                        
                        async for chunk in response.content.iter_chunked(chunk_size):
                            if not chunk:
                                break

                            # Update performance stats
                            self.stats['bytes_transferred'] += len(chunk)
                            self.stats['last_frame_time'] = datetime.now()
                            
                            current_time = time.time()

                            if fps_limit:
                                # Enhanced FPS limiting with quality-based optimization
                                if current_time - last_frame_time < frame_interval:
                                    # Quality-based frame timing adjustment
                                    quality_multiplier = {
                                        'high': 1.0,    # No adjustment for high quality
                                        'medium': 0.9,  # Slightly faster for medium
                                        'low': 0.8      # Faster for low quality
                                    }.get(quality, 1.0)
                                    
                                    if drop_strategy == "latest":
                                        # Skip this frame
                                        continue
                                    elif drop_strategy == "oldest":
                                        # Clear buffer and use latest
                                        continue
                                    else:
                                        # Wait to maintain FPS with quality adjustment
                                        sleep_time = (frame_interval * quality_multiplier) - (current_time - last_frame_time)
                                        if sleep_time > 0:
                                            await asyncio.sleep(sleep_time)

                                last_frame_time = time.time()

                            # Update frame counter
                            self.stats['frames_processed'] += 1
                            yield chunk

                        return  # Successfully streamed from this endpoint
                    else:
                        print(f"Wrong content type: {content_type}")

            except Exception as e:
                print(f"Failed to connect to {endpoint}: {e}")
                continue

        # If we get here, all endpoints failed
        error_msg = f"No DroidCam streams found at {ip}:{port}. Check: 1) DroidCam app is running 2) Phone IP is correct 3) Same WiFi network"
        print(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)


streamer = DroidCamStreamer()

# Add performance statistics method
def get_performance_stats():
    """Get real-time performance statistics"""
    if streamer.stats['start_time']:
        runtime = (datetime.now() - streamer.stats['start_time']).total_seconds()
        fps = streamer.stats['frames_processed'] / runtime if runtime > 0 else 0
        bandwidth = (streamer.stats['bytes_transferred'] / 1024 / 1024) / runtime if runtime > 0 else 0  # MB/s
        
        return {
            'frames_processed': streamer.stats['frames_processed'],
            'runtime_seconds': round(runtime, 2),
            'current_fps': round(fps, 2),
            'bandwidth_mbps': round(bandwidth, 2),
            'bytes_transferred': streamer.stats['bytes_transferred'],
            'connection_count': streamer.stats['connection_count'],
            'errors': streamer.stats['errors'],
            'last_frame_time': streamer.stats['last_frame_time'].isoformat() if streamer.stats['last_frame_time'] else None
        }
    return {'status': 'not_started'}

@app.get("/api/stats")
async def get_stats():
    """Get real-time performance statistics"""
    return get_performance_stats()

@app.on_event("shutdown")
async def shutdown_event():
    await streamer.close_session()


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DroidCam FastAPI Viewer</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            .controls { margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; }
            .control-group { margin-bottom: 10px; }
            label { display: inline-block; width: 120px; font-weight: bold; }
            input, select, button { padding: 8px; margin: 2px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; cursor: pointer; padding: 10px 20px; }
            button:hover { background: #0056b3; }
            .status { margin: 10px 0; padding: 10px; border-radius: 4px; }
            .status.success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .status.error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
            .video-container { text-align: center; margin-top: 20px; }
            #videoStream { max-width: 100%; height: auto; border: 2px solid #ddd; border-radius: 8px; }
            .scan-results { margin-top: 15px; }
            .endpoint { margin: 5px 0; padding: 8px; background: #e9ecef; border-radius: 4px; }
            .endpoint.available { background: #d4edda; }
            .endpoint.error { background: #f8d7da; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 DroidCam FastAPI Viewer</h1>
            <p>High-performance async streaming with FPS control and frame dropping strategies.</p>

            <div class="controls">
                <div class="control-group">
                    <label>Phone IP:</label>
                    <input type="text" id="phoneIP" value="192.168.8.253" placeholder="192.168.1.100">
                    <label>Port:</label>
                    <input type="number" id="phonePort" value="4747" style="width: 80px;">
                </div>

                <div class="control-group">
                    <label>Resolution:</label>
                    <select id="resolution">
                        <option value="auto">Auto (Original)</option>
                        <option value="640x480" selected>480p (640x480)</option>
                        <option value="1920x1080">1080p (1920x1080)</option>
                        <option value="1280x720">720p (1280x720)</option>
                        <option value="854x480">480p (854x480)</option>
                        <option value="640x360">360p (640x360)</option>
                    </select>

                    <label>Quality:</label>
                    <select id="quality">
                        <option value="high" selected>High Quality</option>
                        <option value="medium">Medium Quality</option>
                        <option value="low">Low Quality (Faster)</option>
                    </select>
                </div>

                <div class="control-group">
                    <label>FPS Limit:</label>
                    <select id="fpsLimit">
                        <option value="">No Limit</option>
                        <option value="15">15 FPS</option>
                        <option value="24" selected>24 FPS</option>
                        <option value="30">30 FPS</option>
                        <option value="60">60 FPS</option>
                    </select>

                    <label>Drop Strategy:</label>
                    <select id="dropStrategy">
                        <option value="none">No Dropping</option>
                        <option value="latest" selected>Drop Latest</option>
                        <option value="oldest">Drop Oldest</option>
                    </select>
                </div>

                <div class="control-group">
                    <button onclick="scanEndpoints()">🔍 Scan Endpoints</button>
                    <button onclick="startStream()">▶️ Start Stream</button>
                    <button onclick="stopStream()">⏹️ Stop Stream</button>
                </div>

                <div id="status"></div>
                <div id="scanResults" class="scan-results"></div>
            </div>

            <div class="video-container">
                <div id="videoPlaceholder" style="
                    width: 100%; 
                    height: 400px; 
                    background: #000; 
                    border: 2px solid #ddd; 
                    border-radius: 8px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    color: #fff; 
                    font-size: 18px;
                ">
                    📱 Click "Start Stream" to view DroidCam footage
                </div>
                <img id="videoStream" style="
                    display: none; 
                    max-width: 100%; 
                    height: auto; 
                    border: 2px solid #ddd; 
                    border-radius: 8px; 
                    background: #000;
                " alt="DroidCam Stream">
            </div>
        </div>

        <script>
            let streamActive = false;
            let streamImg = null;

            function showStatus(message, type = 'success') {
                const status = document.getElementById('status');
                status.className = `status ${type}`;
                status.innerHTML = message;
                status.style.display = 'block';
            }

            async function scanEndpoints() {
                const ip = document.getElementById('phoneIP').value;
                const port = document.getElementById('phonePort').value;

                showStatus('Scanning endpoints...', 'success');

                try {
                    const response = await fetch(`/api/scan?ip=${ip}&port=${port}`);
                    const results = await response.json();

                    let html = '<h4>Scan Results:</h4>';
                    for (const [endpoint, result] of Object.entries(results)) {
                        const className = result.status === 'available' ? 'available' : 'error';
                        html += `<div class="endpoint ${className}">
                            <strong>${endpoint}</strong><br>
                            Status: ${result.status}<br>
                            ${result.content_type ? `Type: ${result.content_type}<br>` : ''}
                            ${result.error ? `Error: ${result.error}` : ''}
                        </div>`;
                    }

                    document.getElementById('scanResults').innerHTML = html;
                    showStatus('Scan completed', 'success');
                } catch (error) {
                    showStatus(`Scan failed: ${error.message}`, 'error');
                }
            }

            function startStream() {
                if (streamActive) {
                    showStatus('Stream is already active', 'error');
                    return;
                }

                const ip = document.getElementById('phoneIP').value;
                const port = document.getElementById('phonePort').value;
                const fpsLimit = document.getElementById('fpsLimit').value;
                const dropStrategy = document.getElementById('dropStrategy').value;
                const resolution = document.getElementById('resolution').value;
                const quality = document.getElementById('quality').value;

                if (!ip) {
                    showStatus('Please enter phone IP address', 'error');
                    return;
                }

                let url = `/stream?ip=${ip}&port=${port}`;
                if (fpsLimit) url += `&fps_limit=${fpsLimit}`;
                if (dropStrategy !== 'none') url += `&drop_strategy=${dropStrategy}`;
                if (resolution !== 'auto') url += `&resolution=${resolution}`;
                if (quality !== 'high') url += `&quality=${quality}`;

                // Hide placeholder and show video
                document.getElementById('videoPlaceholder').style.display = 'none';

                const img = document.getElementById('videoStream');
                img.style.display = 'block';
                img.src = url + '&t=' + Date.now(); // Add timestamp to prevent caching
                streamActive = true;
                streamImg = img;

                showStatus(`Streaming from ${ip}:${port} (${fpsLimit || 'unlimited'} FPS, ${dropStrategy} drop)`, 'success');

                // Handle load and error events
                img.onload = () => {
                    console.log('Stream loaded successfully');
                };

                img.onerror = (e) => {
                    console.error('Stream error:', e);
                    showStatus('Stream failed to load - check connection and try again', 'error');
                    stopStream();
                };

                // Monitor stream health
                setTimeout(() => {
                    if (streamActive && img.naturalWidth === 0) {
                        showStatus('Stream appears to be empty - check DroidCam app', 'error');
                    }
                }, 3000);
            }

            function stopStream() {
                streamActive = false;

                const img = document.getElementById('videoStream');
                img.src = '';
                img.style.display = 'none';

                // Show placeholder
                document.getElementById('videoPlaceholder').style.display = 'flex';

                streamImg = null;
                showStatus('Stream stopped', 'success');
            }

            // Auto-scan on page load
            window.onload = () => {
                console.log('Page loaded, starting auto-scan');
                scanEndpoints();
            };

            // Handle page visibility changes to restart stream if needed
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible' && streamActive && streamImg) {
                    // Refresh stream URL to prevent stale connections
                    const currentSrc = streamImg.src;
                    if (currentSrc) {
                        const baseUrl = currentSrc.split('&t=')[0];
                        streamImg.src = baseUrl + '&t=' + Date.now();
                    }
                }
            });
        </script>
    </body>
    </html>
    """


@app.get("/api/scan")
async def scan_endpoints(ip: str = Query(...), port: int = Query(4747)):
    """Scan DroidCam endpoints"""
    try:
        results = await streamer.scan_endpoints(ip, port)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream")
async def stream_video(
        ip: str = Query(...),
        port: int = Query(4747),
        fps_limit: Optional[float] = Query(None),
        drop_strategy: str = Query("none"),
        resolution: str = Query("auto"),
        quality: str = Query("high")
):
    """Proxy DroidCam MJPEG, enforce FPS, optional resizing and quality re-encode."""

    # Try to pass resolution and FPS parameters to DroidCam
    droidcam_url = f"http://{ip}:{port}/video"
    params = []
    
    if resolution and resolution.lower() != "auto":
        # Try common DroidCam URL parameters for resolution control
        try:
            w, h = resolution.lower().split("x")
            params.extend([f"width={w}", f"height={h}", f"resolution={resolution}", f"size={resolution}"])
        except Exception:
            pass
    
    if fps_limit:
        # Try common FPS parameter formats
        params.extend([f"fps={int(fps_limit)}", f"framerate={int(fps_limit)}", f"rate={int(fps_limit)}"])
    
    if params:
        droidcam_url += "?" + "&".join(params)
        print(f"Trying DroidCam URL with parameters: {droidcam_url}")

    # Parse target resolution
    target_size = None
    if resolution and resolution.lower() != "auto":
        try:
            w, h = resolution.lower().split("x")
            target_size = (int(w), int(h))
        except Exception:
            target_size = None

    # Map quality preset to JPEG quality
    quality_map = {"high": 90, "medium": 75, "low": 60}
    jpeg_quality = quality_map.get(quality, 85)

    # FPS timing
    frame_interval = (1.0 / float(fps_limit)) if fps_limit else 0.0
    last_sent = 0.0

    async def generate():
        nonlocal last_sent
        session = await streamer.get_session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'multipart/x-mixed-replace,*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }

        try:
            async with session.get(droidcam_url, headers=headers, timeout=aiohttp.ClientTimeout(total=None)) as response:
                ct = response.headers.get('content-type', '').lower()
                if response.status != 200:
                    yield f"DroidCam status {response.status}".encode()
                    return
                if 'text/html' in ct:
                    yield b"DroidCam returned HTML, not MJPEG. Check app permissions/state."
                    return

                buffer = bytearray()
                SOI = b"\xff\xd8"  # Start Of Image
                EOI = b"\xff\xd9"  # End Of Image

                async for chunk in response.content.iter_chunked(16384):
                    if not chunk:
                        break
                    buffer.extend(chunk)

                    # Extract full JPEG frames from buffer
                    while True:
                        start = buffer.find(SOI)
                        end = buffer.find(EOI, start + 2)
                        if start != -1 and end != -1:
                            end += 2
                            frame_bytes = bytes(buffer[start:end])
                            del buffer[:end]

                            # FPS control
                            now = time.time()
                            if frame_interval > 0:
                                delta = now - last_sent
                                if delta < frame_interval:
                                    if drop_strategy == "latest":
                                        # Drop this frame, continue to next available
                                        continue
                                    elif drop_strategy == "oldest":
                                        # Wait until send time
                                        await asyncio.sleep(frame_interval - delta)
                                    else:
                                        await asyncio.sleep(frame_interval - delta)

                            # Decode for optional resize/quality
                            if target_size is not None or quality in quality_map:
                                np_img = np.frombuffer(frame_bytes, dtype=np.uint8)
                                img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
                                if img is None:
                                    # Fallback: forward original
                                    pass
                                else:
                                    if target_size is not None:
                                        img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
                                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
                                    ok, enc = cv2.imencode('.jpg', img, encode_param)
                                    if ok:
                                        frame_bytes = enc.tobytes()

                            # Update timing after successful frame generation
                            last_sent = time.time()

                            # Emit our own multipart frame
                            header = (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                + f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode('ascii')
                            )
                            yield header + frame_bytes + b"\r\n"
                        else:
                            break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            yield f"Stream error: {e}".encode()

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close",
            "Access-Control-Allow-Origin": "*"
        }
    )


if __name__ == "__main__":
    print("Starting DroidCam FastAPI Viewer...")
    print("Open: http://127.0.0.1:8084/")
    print("Features: Enhanced performance, resolution controls, quality settings, real-time stats")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8084")),
        loop="uvloop" if hasattr(asyncio, "uvloop") else "asyncio",
        log_level="info"
    )
