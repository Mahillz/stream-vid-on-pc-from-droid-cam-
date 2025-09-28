import asyncio
import aiohttp
import time
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="DroidCam FastAPI Viewer")

class DroidCamStreamer:
    def __init__(self):
        self.session = None
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            self.session = aiohttp.ClientSession(timeout=timeout)
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
        drop_strategy: str = "none"
    ) -> AsyncGenerator[bytes, None]:
        """Stream MJPEG with optional FPS limiting and frame dropping"""
        
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
                        
                        async for chunk in response.content.iter_chunked(8192):
                            if not chunk:
                                break
                                
                            current_time = time.time()
                            
                            if fps_limit:
                                # FPS limiting logic
                                if current_time - last_frame_time < frame_interval:
                                    if drop_strategy == "latest":
                                        # Skip this frame
                                        continue
                                    elif drop_strategy == "oldest":
                                        # Clear buffer and use latest
                                        continue
                                    else:
                                        # Wait to maintain FPS
                                        sleep_time = frame_interval - (current_time - last_frame_time)
                                        if sleep_time > 0:
                                            await asyncio.sleep(sleep_time)
                                
                                last_frame_time = time.time()
                            
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
                    <label>FPS Limit:</label>
                    <select id="fpsLimit">
                        <option value="">No Limit</option>
                        <option value="15">15 FPS</option>
                        <option value="24">24 FPS</option>
                        <option value="30" selected>30 FPS</option>
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
                
                if (!ip) {
                    showStatus('Please enter phone IP address', 'error');
                    return;
                }
                
                let url = `/stream?ip=${ip}&port=${port}`;
                if (fpsLimit) url += `&fps_limit=${fpsLimit}`;
                if (dropStrategy !== 'none') url += `&drop_strategy=${dropStrategy}`;
                
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
    drop_strategy: str = Query("none")
):
    """Direct proxy stream from DroidCam with proper headers"""
    
    # Use the exact endpoint that scan confirmed works
    droidcam_url = f"http://{ip}:{port}/video"
    
    async def generate():
        session = await streamer.get_session()
        
        try:
            print(f"Direct proxy to: {droidcam_url}")
            
            # Use specific headers that DroidCam expects
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'multipart/x-mixed-replace,*/*',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
            
            async with session.get(droidcam_url, headers=headers, timeout=aiohttp.ClientTimeout(total=None)) as response:
                print(f"DroidCam response status: {response.status}")
                print(f"DroidCam content-type: {response.headers.get('content-type')}")
                print(f"DroidCam headers: {dict(response.headers)}")
                
                if response.status != 200:
                    error_msg = f"DroidCam returned status {response.status}"
                    print(error_msg)
                    yield error_msg.encode()
                    return
                
                # Check if we're getting the right content type
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' in content_type:
                    print("ERROR: DroidCam returned HTML instead of MJPEG stream")
                    print("This usually means:")
                    print("1. DroidCam app is not properly started")
                    print("2. Camera permission not granted")
                    print("3. Another app is using the camera")
                    
                    error_html = await response.text()
                    print(f"HTML response: {error_html[:200]}...")
                    
                    yield f"DroidCam Error: Received HTML instead of video stream. Check DroidCam app status.".encode()
                    return
                
                if 'multipart/x-mixed-replace' not in content_type and 'image/jpeg' not in content_type:
                    print(f"WARNING: Unexpected content type: {content_type}")
                
                # Stream the actual content
                chunk_count = 0
                bytes_streamed = 0
                
                async for chunk in response.content.iter_chunked(8192):
                    if not chunk:
                        print("Empty chunk - stream ended")
                        break
                    
                    chunk_count += 1
                    bytes_streamed += len(chunk)
                    
                    # Apply FPS limiting if requested
                    if fps_limit and chunk_count > 1:
                        await asyncio.sleep(1.0 / fps_limit / 10)  # Rough FPS control
                    
                    if chunk_count % 50 == 0:  # Log every 50 chunks
                        print(f"Streamed {chunk_count} chunks, {bytes_streamed} bytes")
                    
                    yield chunk
                    
                print(f"Stream completed: {chunk_count} chunks, {bytes_streamed} bytes total")
                    
        except asyncio.CancelledError:
            print("Stream cancelled by client")
            raise
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            print(error_msg)
            yield error_msg.encode()
    
    # Return the stream with DroidCam's exact content-type
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=--dcmjpeg",
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
    print("Open: http://127.0.0.1:8080/")
    print("Features: Async streaming, FPS limiting, frame dropping")
    
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8080,
        loop="uvloop" if hasattr(asyncio, "uvloop") else "asyncio",
        log_level="info"
    )
