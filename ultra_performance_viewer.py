import asyncio
import aiohttp
import time
import weakref
import gc
from typing import Optional, AsyncGenerator, Dict, Set
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn
import logging
from contextlib import asynccontextmanager

# Configure logging for performance monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global connection pool and performance settings
CHUNK_SIZE = 16384  # Larger chunks for better throughput
MAX_CONNECTIONS = 100
KEEPALIVE_TIMEOUT = 30
CONNECTION_TIMEOUT = 5

class HighPerformanceDroidCamStreamer:
    def __init__(self):
        self.session_pool: Dict[str, aiohttp.ClientSession] = {}
        self.active_streams: Set[str] = set()
        self.performance_stats = {
            'total_bytes': 0,
            'total_chunks': 0,
            'active_connections': 0,
            'start_time': time.time()
        }
        
    async def get_optimized_session(self, key: str = "default") -> aiohttp.ClientSession:
        """Get or create an optimized session with connection pooling"""
        if key not in self.session_pool or self.session_pool[key].closed:
            # Ultra-high performance connector settings
            connector = aiohttp.TCPConnector(
                limit=MAX_CONNECTIONS,
                limit_per_host=20,
                keepalive_timeout=KEEPALIVE_TIMEOUT,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300,
                family=0,  # Allow both IPv4 and IPv6
                ssl=False,  # Disable SSL for local connections
                force_close=False  # Keep connections alive
            )
            
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout for streaming
                connect=CONNECTION_TIMEOUT,
                sock_read=30
            )
            
            self.session_pool[key] = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'UltraPerformanceViewer/1.0',
                    'Accept': 'multipart/x-mixed-replace,*/*',
                    'Accept-Encoding': 'identity',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache'
                },
                read_bufsize=CHUNK_SIZE * 4  # Larger read buffer
            )
            
        return self.session_pool[key]
    
    async def close_all_sessions(self):
        """Close all sessions and cleanup"""
        for session in self.session_pool.values():
            if not session.closed:
                await session.close()
        self.session_pool.clear()
        gc.collect()  # Force garbage collection
    
    async def scan_endpoints_fast(self, ip: str, port: int = 4747) -> dict:
        """Ultra-fast endpoint scanning with concurrent requests"""
        endpoints = [
            f"http://{ip}:{port}/video",
            f"http://{ip}:{port}/mjpegfeed", 
            f"http://{ip}:{port}/cam/1/stream",
            f"http://{ip}:{port}/"
        ]
        
        results = {}
        session = await self.get_optimized_session(f"scan_{ip}")
        
        # Concurrent scanning for maximum speed
        async def test_endpoint(endpoint):
            try:
                async with session.head(endpoint, timeout=aiohttp.ClientTimeout(total=2)) as response:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'multipart/x-mixed-replace' in content_type or 'image/jpeg' in content_type:
                        return endpoint, {
                            'status': 'available',
                            'content_type': content_type,
                            'status_code': response.status
                        }
                    else:
                        return endpoint, {
                            'status': 'not_mjpeg',
                            'content_type': content_type,
                            'status_code': response.status
                        }
            except Exception as e:
                return endpoint, {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Run all endpoint tests concurrently
        tasks = [test_endpoint(endpoint) for endpoint in endpoints]
        scan_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in scan_results:
            if isinstance(result, tuple):
                endpoint, data = result
                results[endpoint] = data
        
        return results
    
    async def ultra_high_performance_stream(
        self, 
        ip: str, 
        port: int = 4747,
        fps_limit: Optional[float] = None,
        drop_strategy: str = "none"
    ) -> AsyncGenerator[bytes, None]:
        """Ultra-high performance streaming with advanced optimizations"""
        
        # Priority order for endpoints (fastest first)
        endpoints = [
            f"http://{ip}:{port}/video",
            f"http://{ip}:{port}/mjpegfeed",
            f"http://{ip}:{port}/cam/1/stream"
        ]
        
        session = await self.get_optimized_session(f"stream_{ip}_{port}")
        stream_id = f"{ip}:{port}"
        
        try:
            self.active_streams.add(stream_id)
            self.performance_stats['active_connections'] += 1
            
            for endpoint in endpoints:
                try:
                    logger.info(f"Attempting ultra-fast connection to: {endpoint}")
                    
                    async with session.get(endpoint) as response:
                        if response.status != 200:
                            continue
                            
                        content_type = response.headers.get('content-type', '').lower()
                        if 'multipart/x-mixed-replace' not in content_type and 'image/jpeg' not in content_type:
                            continue
                        
                        logger.info(f"✅ Ultra-fast stream established: {endpoint}")
                        
                        # Performance monitoring variables
                        chunk_count = 0
                        bytes_streamed = 0
                        last_fps_time = time.time()
                        fps_frame_count = 0
                        
                        # FPS limiting setup
                        frame_interval = 1.0 / fps_limit if fps_limit else 0
                        last_frame_time = 0
                        
                        # Ultra-high performance streaming loop
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            if not chunk:
                                break
                            
                            chunk_count += 1
                            bytes_streamed += len(chunk)
                            fps_frame_count += 1
                            
                            # Update global performance stats
                            self.performance_stats['total_chunks'] += 1
                            self.performance_stats['total_bytes'] += len(chunk)
                            
                            # Advanced FPS limiting with minimal overhead
                            if fps_limit:
                                current_time = time.time()
                                if current_time - last_frame_time < frame_interval:
                                    if drop_strategy == "latest":
                                        continue  # Skip frame
                                    elif drop_strategy == "oldest":
                                        continue  # Skip frame
                                    else:
                                        # Precise sleep for FPS control
                                        sleep_time = frame_interval - (current_time - last_frame_time)
                                        if sleep_time > 0:
                                            await asyncio.sleep(sleep_time)
                                
                                last_frame_time = time.time()
                            
                            # Performance logging (every 100 chunks)
                            if chunk_count % 100 == 0:
                                current_time = time.time()
                                fps = fps_frame_count / (current_time - last_fps_time) if current_time > last_fps_time else 0
                                logger.info(f"Performance: {chunk_count} chunks, {bytes_streamed//1024}KB, {fps:.1f} FPS")
                                fps_frame_count = 0
                                last_fps_time = current_time
                            
                            yield chunk
                        
                        logger.info(f"Stream completed: {chunk_count} chunks, {bytes_streamed//1024}KB total")
                        return
                        
                except Exception as e:
                    logger.warning(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            # If all endpoints failed
            raise HTTPException(status_code=503, detail=f"No high-performance streams available at {ip}:{port}")
            
        finally:
            self.active_streams.discard(stream_id)
            self.performance_stats['active_connections'] -= 1
    
    def get_performance_stats(self) -> dict:
        """Get current performance statistics"""
        uptime = time.time() - self.performance_stats['start_time']
        return {
            'uptime_seconds': uptime,
            'total_bytes_streamed': self.performance_stats['total_bytes'],
            'total_chunks_processed': self.performance_stats['total_chunks'],
            'active_connections': self.performance_stats['active_connections'],
            'average_throughput_mbps': (self.performance_stats['total_bytes'] * 8) / (uptime * 1024 * 1024) if uptime > 0 else 0,
            'chunks_per_second': self.performance_stats['total_chunks'] / uptime if uptime > 0 else 0
        }

# Global streamer instance with lifecycle management
streamer = HighPerformanceDroidCamStreamer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle for optimal performance"""
    logger.info("🚀 Starting Ultra-High Performance DroidCam Viewer")
    yield
    logger.info("🛑 Shutting down and cleaning up connections")
    await streamer.close_all_sessions()

app = FastAPI(
    title="Ultra-High Performance DroidCam Viewer",
    description="Optimized for maximum throughput and minimal latency",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚀 Ultra-High Performance DroidCam Viewer</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { font-size: 2.5em; margin: 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
            .header p { font-size: 1.2em; opacity: 0.9; margin: 10px 0; }
            .controls { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); padding: 25px; border-radius: 15px; margin-bottom: 25px; }
            .control-row { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; flex-wrap: wrap; }
            .control-group { display: flex; align-items: center; gap: 10px; }
            label { font-weight: 600; min-width: 100px; }
            input, select { padding: 10px; border: none; border-radius: 8px; background: rgba(255,255,255,0.9); color: #333; font-size: 14px; }
            button { padding: 12px 20px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s; font-size: 14px; }
            .btn-primary { background: #4CAF50; color: white; }
            .btn-primary:hover { background: #45a049; transform: translateY(-2px); }
            .btn-secondary { background: #2196F3; color: white; }
            .btn-secondary:hover { background: #1976D2; transform: translateY(-2px); }
            .btn-danger { background: #f44336; color: white; }
            .btn-danger:hover { background: #d32f2f; transform: translateY(-2px); }
            .status { margin: 15px 0; padding: 15px; border-radius: 10px; font-weight: 500; }
            .status.success { background: rgba(76, 175, 80, 0.2); border: 1px solid #4CAF50; }
            .status.error { background: rgba(244, 67, 54, 0.2); border: 1px solid #f44336; }
            .video-container { text-align: center; background: rgba(0,0,0,0.3); border-radius: 15px; padding: 20px; }
            .video-placeholder { width: 100%; height: 500px; background: #000; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5em; color: #888; }
            #videoStream { max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px; }
            .stat-card { background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; text-align: center; }
            .stat-value { font-size: 1.8em; font-weight: bold; color: #4CAF50; }
            .stat-label { font-size: 0.9em; opacity: 0.8; margin-top: 5px; }
            .scan-results { margin-top: 20px; }
            .endpoint { margin: 8px 0; padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.1); }
            .endpoint.available { background: rgba(76, 175, 80, 0.2); border-left: 4px solid #4CAF50; }
            .endpoint.error { background: rgba(244, 67, 54, 0.2); border-left: 4px solid #f44336; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Ultra-High Performance DroidCam Viewer</h1>
                <p>Optimized for maximum throughput, minimal latency, and smooth streaming</p>
            </div>
            
            <div class="controls">
                <div class="control-row">
                    <div class="control-group">
                        <label>Phone IP:</label>
                        <input type="text" id="phoneIP" value="192.168.8.253" placeholder="192.168.1.100">
                    </div>
                    <div class="control-group">
                        <label>Port:</label>
                        <input type="number" id="phonePort" value="4747" style="width: 80px;">
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>Resolution:</label>
                        <select id="resolution">
                            <option value="auto" selected>Auto (Original)</option>
                            <option value="1920x1080">1080p (1920x1080)</option>
                            <option value="1280x720">720p (1280x720)</option>
                            <option value="854x480">480p (854x480)</option>
                            <option value="640x360">360p (640x360)</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Quality:</label>
                        <select id="quality">
                            <option value="high" selected>High Quality</option>
                            <option value="medium">Medium Quality</option>
                            <option value="low">Low Quality (Faster)</option>
                        </select>
                    </div>
                </div>
                
                <div class="control-row">
                    <div class="control-group">
                        <label>FPS Limit:</label>
                        <select id="fpsLimit">
                            <option value="">Unlimited</option>
                            <option value="15">15 FPS</option>
                            <option value="24">24 FPS</option>
                            <option value="30" selected>30 FPS</option>
                            <option value="60">60 FPS</option>
                            <option value="120">120 FPS</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Drop Strategy:</label>
                        <select id="dropStrategy">
                            <option value="none">No Dropping</option>
                            <option value="latest" selected>Drop Latest</option>
                            <option value="oldest">Drop Oldest</option>
                        </select>
                    </div>
                </div>
                
                <div class="control-row">
                    <button class="btn-secondary" onclick="scanEndpoints()">🔍 Ultra-Fast Scan</button>
                    <button class="btn-primary" onclick="startStream()">▶️ Start Ultra Stream</button>
                    <button class="btn-danger" onclick="stopStream()">⏹️ Stop Stream</button>
                    <button class="btn-secondary" onclick="updateStats()">📊 Performance Stats</button>
                </div>
                
                <div id="status"></div>
                <div id="scanResults" class="scan-results"></div>
            </div>
            
            <div class="video-container">
                <div id="videoPlaceholder" class="video-placeholder">
                    🎥 Click "Start Ultra Stream" for maximum performance streaming
                </div>
                <img id="videoStream" style="display: none;" alt="Ultra Performance DroidCam Stream">
            </div>
            
            <div id="performanceStats" class="stats"></div>
        </div>

        <script>
            let streamActive = false;
            let streamImg = null;
            let statsInterval = null;
            
            function showStatus(message, type = 'success') {
                const status = document.getElementById('status');
                status.className = `status ${type}`;
                status.innerHTML = message;
                status.style.display = 'block';
            }
            
            async function scanEndpoints() {
                const ip = document.getElementById('phoneIP').value;
                const port = document.getElementById('phonePort').value;
                
                showStatus('🚀 Ultra-fast scanning...', 'success');
                
                try {
                    const startTime = performance.now();
                    const response = await fetch(`/api/scan?ip=${ip}&port=${port}`);
                    const results = await response.json();
                    const scanTime = (performance.now() - startTime).toFixed(1);
                    
                    let html = `<h4>🔍 Scan Results (${scanTime}ms):</h4>`;
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
                    showStatus(`✅ Ultra-fast scan completed in ${scanTime}ms`, 'success');
                } catch (error) {
                    showStatus(`❌ Scan failed: ${error.message}`, 'error');
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
                
                document.getElementById('videoPlaceholder').style.display = 'none';
                
                const img = document.getElementById('videoStream');
                img.style.display = 'block';
                
                // Apply resolution styling for better display
                if (resolution !== 'auto') {
                    const [width, height] = resolution.split('x');
                    img.style.maxWidth = `${width}px`;
                    img.style.maxHeight = `${height}px`;
                } else {
                    img.style.maxWidth = '100%';
                    img.style.maxHeight = 'auto';
                }
                
                img.src = url + '&t=' + Date.now();
                streamActive = true;
                streamImg = img;
                
                showStatus(`🚀 Ultra-performance streaming ${resolution} ${quality} quality from ${ip}:${port}`, 'success');
                
                img.onload = () => {
                    console.log('Ultra stream loaded successfully');
                    startStatsUpdates();
                };
                
                img.onerror = (e) => {
                    console.error('Stream error:', e);
                    showStatus('Stream failed - check connection and try again', 'error');
                    stopStream();
                };
            }
            
            function stopStream() {
                streamActive = false;
                
                if (statsInterval) {
                    clearInterval(statsInterval);
                    statsInterval = null;
                }
                
                const img = document.getElementById('videoStream');
                img.src = '';
                img.style.display = 'none';
                
                document.getElementById('videoPlaceholder').style.display = 'flex';
                document.getElementById('performanceStats').innerHTML = '';
                
                streamImg = null;
                showStatus('⏹️ Ultra stream stopped', 'success');
            }
            
            function startStatsUpdates() {
                updateStats();
                statsInterval = setInterval(updateStats, 2000);
            }
            
            async function updateStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    
                    const statsHtml = `
                        <div class="stat-card">
                            <div class="stat-value">${stats.active_connections}</div>
                            <div class="stat-label">Active Connections</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${(stats.total_bytes_streamed / 1024 / 1024).toFixed(1)}MB</div>
                            <div class="stat-label">Total Streamed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.average_throughput_mbps.toFixed(1)}</div>
                            <div class="stat-label">Mbps Throughput</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.chunks_per_second.toFixed(0)}</div>
                            <div class="stat-label">Chunks/sec</div>
                        </div>
                    `;
                    
                    document.getElementById('performanceStats').innerHTML = statsHtml;
                } catch (error) {
                    console.error('Stats update failed:', error);
                }
            }
            
            // Auto-scan on page load
            window.onload = () => {
                console.log('Ultra-performance viewer loaded');
                scanEndpoints();
            };
        </script>
    </body>
    </html>
    """

@app.get("/api/scan")
async def scan_endpoints(ip: str = Query(...), port: int = Query(4747)):
    """Ultra-fast endpoint scanning"""
    try:
        results = await streamer.scan_endpoints_fast(ip, port)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_performance_stats():
    """Get real-time performance statistics"""
    return streamer.get_performance_stats()

@app.get("/stream")
async def stream_video(
    ip: str = Query(...),
    port: int = Query(4747),
    fps_limit: Optional[float] = Query(None),
    drop_strategy: str = Query("none"),
    resolution: str = Query("auto"),
    quality: str = Query("high")
):
    """Ultra-high performance streaming endpoint"""
    
    async def generate():
        try:
            # Log the streaming parameters for debugging
            logger.info(f"Starting stream: {ip}:{port}, FPS: {fps_limit}, Quality: {quality}, Resolution: {resolution}")
            
            async for chunk in streamer.ultra_high_performance_stream(ip, port, fps_limit, drop_strategy):
                yield chunk
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"Stream error: {str(e)}".encode()
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=--dcmjpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"  # Disable nginx buffering for real-time streaming
        }
    )

if __name__ == "__main__":
    print("Starting Ultra-High Performance DroidCam Viewer...")
    print("Features: Connection pooling, advanced FPS control, real-time stats")
    print("Open: http://127.0.0.1:8081/")
    
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8081,
        loop="asyncio",  # Use asyncio instead of uvloop for compatibility
        log_level="info",
        access_log=False,  # Disable access logs for performance
        workers=1
    )
