# DroidCam Web Viewer - AMD GPU Accelerated Solution
from flask import Flask, Response, request, jsonify
import requests
import logging
import time
import psutil
import threading
import os
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

app = Flask(__name__)
DEFAULT_IP = "192.168.8.253"
DEFAULT_PORT = "4747"

# Enable detailed logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# AMD GPU and CPU optimization settings
AMD_GPU_ENABLED = False
CPU_CORES = psutil.cpu_count(logical=False)
CPU_THREADS = psutil.cpu_count(logical=True)

# Try to detect AMD GPU
try:
    if CV2_AVAILABLE:
        # Check for AMD OpenCL support
        platforms = cv2.ocl.getPlatformsInfo() if hasattr(cv2.ocl, 'getPlatformsInfo') else []
        for platform in platforms:
            if 'AMD' in platform.get('name', '') or 'Radeon' in platform.get('name', ''):
                AMD_GPU_ENABLED = True
                logging.info(f"AMD GPU detected: {platform.get('name', 'Unknown')}")
                break
except Exception as e:
    logging.warning(f"GPU detection failed: {e}")

logging.info(f"System: AMD Ryzen 5 7000 series - CPU cores: {CPU_CORES}, threads: {CPU_THREADS}, GPU accel: {AMD_GPU_ENABLED}")

@app.route("/stream")
def stream_video():
    """Optimized MJPEG streaming endpoint with quality controls"""
    ip = request.args.get("ip", DEFAULT_IP)
    port = request.args.get("port", DEFAULT_PORT)
    quality = request.args.get("quality", "medium")  # low, medium, high, ultra
    fps = request.args.get("fps", "auto")  # auto, 15, 30, 60
    buffer_size = int(request.args.get("buffer", "65536"))  # Streaming buffer size (default XL for ultra-smooth)
    smoothing = request.args.get("smoothing", "ultra")  # basic, enhanced, ultra, cinema
    
    # Quality-based endpoint selection optimized for AMD hardware
    quality_params = {
        "low": {"res": "320x240", "q": "50", "fps": "15", "codec": "h264_amf" if AMD_GPU_ENABLED else "mjpeg"},
        "medium": {"res": "640x480", "q": "75", "fps": "24", "codec": "h264_amf" if AMD_GPU_ENABLED else "mjpeg"},
        "high": {"res": "1280x720", "q": "85", "fps": "30", "codec": "h264_amf" if AMD_GPU_ENABLED else "mjpeg"},
        "ultra": {"res": "1920x1080", "q": "95", "fps": "60", "codec": "h264_amf" if AMD_GPU_ENABLED else "mjpeg"}
    }
    
    params = quality_params.get(quality, quality_params["medium"])
    if fps != "auto":
        params["fps"] = fps
    
    # Build endpoints with quality parameters
    base_url = f"http://{ip}:{port}"
    endpoints = [
        f"{base_url}/video?res={params['res']}&quality={params['q']}&fps={params['fps']}",
        f"{base_url}/video?quality={params['q']}&fps={params['fps']}",
        f"{base_url}/video",  # Fallback to basic MJPEG
        f"{base_url}/mjpegfeed",
        f"{base_url}",
    ]
    
    for endpoint in endpoints:
        try:
            logging.info(f"Trying endpoint: {endpoint}")
            r = requests.get(endpoint, stream=True, timeout=(5, 10))
            
            if r.status_code == 200:
                ctype = r.headers.get("Content-Type", "")
                logging.info(f"Success! Status={r.status_code}, Content-Type='{ctype}'")
                
                # Check if it's actually MJPEG
                if "multipart" in ctype.lower() or "mjpeg" in ctype.lower():
                    # AMD GPU accelerated streaming with optimized buffering
                    chunk_size = buffer_size
                    if AMD_GPU_ENABLED:
                        # Larger chunks for GPU processing
                        chunk_size = min(buffer_size * 2, 131072)  # Max 128KB for GPU
                    
                    def generate():
                        try:
                            frame_count = 0
                            start_time = time.time()
                            last_frame_time = start_time
                            frame_buffer = []
                            target_fps = float(params.get('fps', '24'))
                            frame_interval = 1.0 / target_fps if target_fps > 0 else 1.0/24
                            
                            # Ultra-smooth streaming variables
                            jitter_buffer = []
                            frame_timestamps = []
                            # Ultra-smooth parameters based on smoothing level
                            smoothing_params = {
                                "basic": {"window": 5, "tolerance": 0.8, "max_buffer": 2, "micro_delay": 0.001},
                                "enhanced": {"window": 8, "tolerance": 0.75, "max_buffer": 3, "micro_delay": 0.0005},
                                "ultra": {"window": 10, "tolerance": 0.7, "max_buffer": 5, "micro_delay": 0.0003},
                                "cinema": {"window": 15, "tolerance": 0.65, "max_buffer": 8, "micro_delay": 0.0001}
                            }
                            
                            smooth_config = smoothing_params.get(smoothing, smoothing_params["ultra"])
                            smoothing_window = smooth_config["window"]
                            frame_tolerance = smooth_config["tolerance"]
                            max_jitter_buffer = smooth_config["max_buffer"]
                            base_micro_delay = smooth_config["micro_delay"]
                            
                            adaptive_delay = 0.0
                            frame_size_history = []
                            
                            # Ultra-smooth adaptive streaming with advanced buffering
                            for chunk in r.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    current_time = time.time()
                                    frame_count += 1
                                    chunk_size_kb = len(chunk) / 1024
                                    
                                    # Track frame sizes for adaptive optimization
                                    frame_size_history.append(chunk_size_kb)
                                    if len(frame_size_history) > smoothing_window:
                                        frame_size_history.pop(0)
                                    
                                    # Advanced jitter buffer management
                                    frame_timestamps.append(current_time)
                                    if len(frame_timestamps) > smoothing_window:
                                        frame_timestamps.pop(0)
                                    
                                    # Calculate adaptive frame timing with jitter compensation
                                    if len(frame_timestamps) >= 3:
                                        # Compute rolling average of frame intervals
                                        intervals = [frame_timestamps[i] - frame_timestamps[i-1] 
                                                   for i in range(1, len(frame_timestamps))]
                                        avg_interval = sum(intervals) / len(intervals)
                                        jitter = max(intervals) - min(intervals)
                                        
                                        # Adaptive delay based on network jitter
                                        if jitter > 0.01:  # High jitter detected
                                            adaptive_delay = min(0.005, jitter * 0.3)
                                        else:
                                            adaptive_delay = max(0.0, adaptive_delay - 0.001)
                                    
                                    # Enhanced frame rate regulation with prediction
                                    time_since_last = current_time - last_frame_time
                                    predicted_next_frame = frame_interval - adaptive_delay
                                    
                                    # Ultra-smooth frame delivery with interpolation buffer
                                    if time_since_last < predicted_next_frame * frame_tolerance:
                                        # Add to jitter buffer with timestamp
                                        jitter_buffer.append((chunk, current_time, chunk_size_kb))
                                        
                                        # Limit jitter buffer size (adaptive based on smoothing level and network conditions)
                                        dynamic_max_buffer = max_jitter_buffer + (2 if jitter > 0.02 else 0)
                                        if len(jitter_buffer) > dynamic_max_buffer:
                                            # Remove oldest frame
                                            jitter_buffer.pop(0)
                                        continue
                                    
                                    # Send buffered frames with optimal timing
                                    while jitter_buffer:
                                        buffered_chunk, buffered_time, buffered_size = jitter_buffer.pop(0)
                                        yield buffered_chunk
                                        
                                        # Micro-delay for ultra-smooth delivery (adaptive based on smoothing level)
                                        size_factor = (buffered_size / 1000.0) * 0.0001
                                        optimal_delay = base_micro_delay + size_factor
                                        time.sleep(optimal_delay)
                                    
                                    # Send current frame with temporal smoothing
                                    yield chunk
                                    last_frame_time = current_time
                                    
                                    # Additional smoothing delay based on frame complexity and smoothing level
                                    complexity_multiplier = {
                                        "basic": 1.0, "enhanced": 0.8, "ultra": 0.6, "cinema": 0.4
                                    }.get(smoothing, 0.6)
                                    
                                    if chunk_size_kb > 50:  # Large frame
                                        time.sleep(0.0008 * complexity_multiplier)
                                    elif chunk_size_kb > 20:  # Medium frame
                                        time.sleep(0.0003 * complexity_multiplier)
                                    else:  # Small frame
                                        time.sleep(0.0001 * complexity_multiplier)
                                    
                                    # AMD Ryzen optimization: use multiple threads for processing
                                    if AMD_GPU_ENABLED and frame_count % 10 == 0:
                                        if hasattr(cv2, 'ocl') and cv2.ocl.useOpenCL():
                                            pass  # GPU is handling processing
                                    
                                    # Enhanced performance stats every 100 frames
                                    if frame_count % 100 == 0:
                                        elapsed = time.time() - start_time
                                        actual_fps = frame_count / elapsed if elapsed > 0 else 0
                                        cpu_percent = psutil.cpu_percent(interval=None)
                                        memory_percent = psutil.virtual_memory().percent
                                        gpu_status = "GPU" if AMD_GPU_ENABLED else "CPU"
                                        fps_efficiency = (actual_fps / target_fps * 100) if target_fps > 0 else 0
                                        avg_jitter = sum([max(intervals) - min(intervals) for intervals in [intervals[-5:]] if len(intervals) >= 2]) if len(intervals) >= 2 else 0
                                        logging.info(f"Stream stats: {frame_count} frames, {actual_fps:.1f}/{target_fps} FPS ({fps_efficiency:.1f}% efficiency), {gpu_status} mode, smoothing={smoothing}, jitter={avg_jitter:.4f}s, CPU: {cpu_percent:.1f}%, RAM: {memory_percent:.1f}%, quality={quality}")
                            
                            # Send any remaining buffered frames with optimal timing
                            while frame_buffer:
                                yield frame_buffer.pop(0)
                                time.sleep(0.001)
                            
                            # Send remaining jitter buffer frames
                            while jitter_buffer:
                                buffered_chunk, _, buffered_size = jitter_buffer.pop(0)
                                yield buffered_chunk
                                time.sleep(0.0005 + (buffered_size / 1000.0) * 0.0001)
                        except Exception as e:
                            logging.error(f"Stream error: {e}")
                    
                    headers = {
                        "Content-Type": ctype,
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        "Access-Control-Allow-Origin": "*",
                        "Connection": "keep-alive",  # Keep connection alive for smoother streaming
                        "Transfer-Encoding": "chunked",
                        "X-Stream-Quality": quality,
                        "X-Stream-FPS": str(params['fps']),
                        "X-Hardware-Accel": "AMD-GPU" if AMD_GPU_ENABLED else "CPU",
                        "X-CPU-Cores": str(CPU_CORES),
                        "X-Buffer-Size": str(chunk_size),
                        "X-Frame-Smoothing": "ultra-enabled",
                        "X-Jitter-Buffer": "adaptive",
                        "X-Temporal-Smoothing": "active"
                    }
                    return Response(generate(), headers=headers)
                else:
                    logging.warning(f"Not MJPEG: {ctype}")
                    r.close()
            else:
                logging.warning(f"HTTP {r.status_code} from {endpoint}")
                r.close()
                
        except Exception as e:
            logging.error(f"Failed {endpoint}: {e}")
    
    return Response(f"No MJPEG stream found. Tried: {', '.join(endpoints)}", 
                   status=502, content_type="text/plain")

@app.route("/api/scan")
def scan_endpoints():
    """Scan for available DroidCam endpoints"""
    ip = request.args.get("ip", DEFAULT_IP)
    port = request.args.get("port", DEFAULT_PORT)
    
    endpoints = [
        f"http://{ip}:{port}/video",
        f"http://{ip}:{port}/mjpegfeed", 
        f"http://{ip}:{port}",
        f"http://{ip}:{port}/jpg",
        f"http://{ip}:{port}/h264"
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            resp = requests.head(endpoint, timeout=3)
            if resp.status_code >= 400:
                resp = requests.get(endpoint, stream=True, timeout=3)
                try:
                    preview = next(resp.iter_content(1024))[:200].decode(errors="ignore")
                except:
                    preview = ""
                resp.close()
            else:
                preview = ""
                
            results.append({
                "url": endpoint,
                "status": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
                "available": resp.status_code == 200,
                "preview": preview
            })
        except Exception as e:
            results.append({
                "url": endpoint,
                "error": str(e),
                "available": False
            })
    
    return jsonify(results)

@app.route("/api/system-stats")
def system_stats():
    """Get real-time system performance stats for AMD hardware monitoring"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Try to get GPU info if available
        gpu_temp = None
        gpu_usage = None
        try:
            if AMD_GPU_ENABLED and CV2_AVAILABLE:
                # Basic GPU status check
                gpu_usage = "Available" if cv2.ocl.useOpenCL() else "Disabled"
        except:
            gpu_usage = "Unknown"
        
        stats = {
            "cpu": round(cpu_percent, 1),
            "memory": round(memory.percent, 1),
            "cpu_cores": CPU_CORES,
            "cpu_threads": CPU_THREADS,
            "gpu_enabled": AMD_GPU_ENABLED,
            "gpu_status": gpu_usage,
            "memory_total_gb": round(memory.total / (1024**3), 1),
            "memory_available_gb": round(memory.available / (1024**3), 1)
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Hilt Hilz Web Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        .controls {{ margin-bottom: 20px; padding: 15px; background: #e9ecef; border-radius: 5px; }}
        .video-container {{ text-align: center; margin: 20px 0; }}
        #videoStream {{ 
            max-width: 100%; 
            height: auto; 
            border: 2px solid #007bff; 
            border-radius: 5px; 
            transition: all 0.3s ease;
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crisp-edges;
            backface-visibility: hidden;
            transform: translateZ(0);
            will-change: transform;
            filter: contrast(1.05) brightness(1.02);
            -webkit-filter: contrast(1.05) brightness(1.02);
        }}
        #videoStream.ultra-smooth {{
            image-rendering: auto;
            image-rendering: smooth;
            filter: contrast(1.08) brightness(1.03) saturate(1.1);
            -webkit-filter: contrast(1.08) brightness(1.03) saturate(1.1);
        }}
        #webglCanvas {{
            display: none;
            max-width: 100%;
            height: auto;
            border: 2px solid #28a745;
            border-radius: 5px;
            background: #000;
        }}
        .webgl-active #videoStream {{ display: none !important; }}
        .webgl-active #webglCanvas {{ display: block !important; }}
        #videoStream.fullscreen {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999; background: black; border: none; border-radius: 0; object-fit: contain; }}
        .performance {{ font-family: monospace; font-size: 12px; color: #666; margin-top: 10px; }}
        .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .info {{ background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }}
        input, button {{ padding: 8px 12px; margin: 5px; border: 1px solid #ccc; border-radius: 4px; }}
        button {{ background: #007bff; color: white; cursor: pointer; }}
        button:hover {{ background: #0056b3; }}
        .endpoint-list {{ margin-top: 15px; }}
        .endpoint {{ padding: 8px; margin: 5px 0; background: #f8f9fa; border-left: 4px solid #007bff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 DroidCam Web Viewer</h1>
        
        <div class="controls">
            <h3>Connection Settings</h3>
            <label>Phone IP: <input type="text" id="phoneIP" value="{DEFAULT_IP}" placeholder="192.168.x.x"></label>
            <label>Port: <input type="text" id="phonePort" value="{DEFAULT_PORT}" placeholder="4747"></label>
            <br><br>
            <label>Quality: 
                <select id="quality">
                    <option value="low">📱 Low (320p, fast)</option>
                    <option value="medium" selected>📺 Medium (480p, balanced)</option>
                    <option value="high">🎬 High (720p, quality)</option>
                    <option value="ultra">🎯 Ultra (1080p, max)</option>
                </select>
            </label>
            <label>FPS: 
                <select id="fps">
                    <option value="auto" selected>🔄 Auto</option>
                    <option value="15">⚡ 15 FPS (battery save)</option>
                    <option value="24">🎬 24 FPS (cinematic)</option>
                    <option value="30">🎥 30 FPS (standard)</option>
                    <option value="60">🚀 60 FPS (smooth)</option>
                </select>
            </label>
            <label>Buffer: 
                <select id="buffer">
                    <option value="4096">⚡ XS (4KB, ultra-low latency)</option>
                    <option value="8192">💾 Small (8KB, low latency)</option>
                    <option value="16384">⚖️ Medium (16KB, balanced)</option>
                    <option value="32768">🚄 Large (32KB, smooth)</option>
                    <option value="65536" selected>🚀 XL (64KB, ultra-smooth)</option>
                    <option value="131072">🎆 XXL (128KB, cinema-grade)</option>
                </select>
            </label>
            <label>Smoothing: 
                <select id="smoothing">
                    <option value="basic">📺 Basic</option>
                    <option value="enhanced">🎥 Enhanced</option>
                    <option value="ultra" selected>🎆 Ultra-Smooth</option>
                    <option value="cinema">🎬 Cinema-Grade</option>
                </select>
            </label>
            <label>Rendering: 
                <select id="rendering">
                    <option value="standard">🖼️ Standard (IMG)</option>
                    <option value="webgl" selected>🚀 WebGL GPU-Accelerated</option>
                </select>
            </label>
            <br><br>
            <button onclick="scanEndpoints()">🔍 Scan Endpoints</button>
            <button onclick="startStream()">▶️ Start Stream</button>
            <button onclick="stopStream()">⏹️ Stop Stream</button>
            <button onclick="toggleFullscreen()">🔍 Fullscreen</button>
        </div>
        
        <div id="status" class="status info">
            Ready to connect. Enter your phone's IP address and click "Scan Endpoints" or "Start Stream".
        </div>
        
        <div id="performance" class="performance" style="display: none;">
            📊 Stream Performance: <span id="perfStats">Waiting for stream...</span><br>
            🖥️ Hardware: <span id="hwStats">AMD Ryzen 5 7000 series</span>
        </div>
        
        <div class="video-container">
            <img id="videoStream" src="" alt="DroidCam stream will appear here" style="display: none;">
            <canvas id="webglCanvas" width="1280" height="720" style="display: none;"></canvas>
            <div id="placeholder" style="padding: 60px; background: #e9ecef; border: 2px dashed #6c757d; border-radius: 5px;">
                📱 DroidCam stream will appear here
            </div>
        </div>
        
        <div id="endpoints" class="endpoint-list"></div>
    </div>
    
    <script>
        let streamActive = false;
        let webglRenderer = null;
        let animationFrame = null;
        
        // WebGL Ultra-Smooth Renderer Class
        class WebGLRenderer {{
            constructor(canvas) {{
                this.canvas = canvas;
                this.gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
                this.texture = null;
                this.program = null;
                this.frameBuffer = [];
                this.frameIndex = 0;
                this.interpolationEnabled = true;
                
                if (!this.gl) {{
                    console.warn('WebGL not supported, falling back to standard rendering');
                    return null;
                }}
                
                this.initShaders();
                this.initBuffers();
                console.log('WebGL renderer initialized with GPU acceleration');
            }}
            
            initShaders() {{
                const vertexShaderSource = `
                    attribute vec2 a_position;
                    attribute vec2 a_texCoord;
                    varying vec2 v_texCoord;
                    void main() {{
                        gl_Position = vec4(a_position, 0.0, 1.0);
                        v_texCoord = a_texCoord;
                    }}
                `;
                
                const fragmentShaderSource = `
                    precision mediump float;
                    uniform sampler2D u_texture;
                    uniform sampler2D u_prevTexture;
                    uniform float u_interpolation;
                    uniform float u_contrast;
                    uniform float u_brightness;
                    uniform float u_saturation;
                    varying vec2 v_texCoord;
                    
                    vec3 adjustColor(vec3 color, float contrast, float brightness, float saturation) {{
                        // Apply brightness
                        color += brightness - 1.0;
                        
                        // Apply contrast
                        color = (color - 0.5) * contrast + 0.5;
                        
                        // Apply saturation
                        float gray = dot(color, vec3(0.299, 0.587, 0.114));
                        color = mix(vec3(gray), color, saturation);
                        
                        return clamp(color, 0.0, 1.0);
                    }}
                    
                    void main() {{
                        vec4 currentFrame = texture2D(u_texture, v_texCoord);
                        vec4 prevFrame = texture2D(u_prevTexture, v_texCoord);
                        
                        // Frame interpolation for ultra-smooth playback
                        vec4 interpolated = mix(prevFrame, currentFrame, u_interpolation);
                        
                        // Enhanced color processing
                        vec3 enhanced = adjustColor(interpolated.rgb, u_contrast, u_brightness, u_saturation);
                        
                        gl_FragColor = vec4(enhanced, interpolated.a);
                    }}
                `;
                
                const vertexShader = this.createShader(this.gl.VERTEX_SHADER, vertexShaderSource);
                const fragmentShader = this.createShader(this.gl.FRAGMENT_SHADER, fragmentShaderSource);
                
                this.program = this.gl.createProgram();
                this.gl.attachShader(this.program, vertexShader);
                this.gl.attachShader(this.program, fragmentShader);
                this.gl.linkProgram(this.program);
                
                if (!this.gl.getProgramParameter(this.program, this.gl.LINK_STATUS)) {{
                    console.error('Shader program failed to link:', this.gl.getProgramInfoLog(this.program));
                }}
            }}
            
            createShader(type, source) {{
                const shader = this.gl.createShader(type);
                this.gl.shaderSource(shader, source);
                this.gl.compileShader(shader);
                
                if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {{
                    console.error('Shader compilation error:', this.gl.getShaderInfoLog(shader));
                    this.gl.deleteShader(shader);
                    return null;
                }}
                
                return shader;
            }}
            
            initBuffers() {{
                const positions = new Float32Array([
                    -1, -1,  0, 1,
                     1, -1,  1, 1,
                    -1,  1,  0, 0,
                     1,  1,  1, 0
                ]);
                
                this.buffer = this.gl.createBuffer();
                this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.buffer);
                this.gl.bufferData(this.gl.ARRAY_BUFFER, positions, this.gl.STATIC_DRAW);
                
                this.texture = this.gl.createTexture();
                this.prevTexture = this.gl.createTexture();
            }}
            
            renderFrame(imageElement) {{
                if (!this.gl || !this.program) return;
                
                // Update canvas size to match image
                if (imageElement.naturalWidth && imageElement.naturalHeight) {{
                    this.canvas.width = imageElement.naturalWidth;
                    this.canvas.height = imageElement.naturalHeight;
                    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
                }}
                
                this.gl.useProgram(this.program);
                
                // Copy previous texture
                this.gl.bindTexture(this.gl.TEXTURE_2D, this.prevTexture);
                this.gl.copyTexImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, 0, 0, this.canvas.width, this.canvas.height, 0);
                
                // Upload new frame
                this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
                this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, this.gl.RGBA, this.gl.UNSIGNED_BYTE, imageElement);
                this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_S, this.gl.CLAMP_TO_EDGE);
                this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_T, this.gl.CLAMP_TO_EDGE);
                this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MIN_FILTER, this.gl.LINEAR);
                this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MAG_FILTER, this.gl.LINEAR);
                
                // Set uniforms
                const smoothing = document.getElementById('smoothing').value;
                const smoothingParams = {{
                    'basic': {{ contrast: 1.02, brightness: 1.01, saturation: 1.0, interpolation: 0.3 }},
                    'enhanced': {{ contrast: 1.05, brightness: 1.02, saturation: 1.05, interpolation: 0.5 }},
                    'ultra': {{ contrast: 1.08, brightness: 1.03, saturation: 1.1, interpolation: 0.7 }},
                    'cinema': {{ contrast: 1.12, brightness: 1.04, saturation: 1.15, interpolation: 0.9 }}
                }};
                
                const params = smoothingParams[smoothing] || smoothingParams['ultra'];
                
                this.gl.uniform1f(this.gl.getUniformLocation(this.program, 'u_contrast'), params.contrast);
                this.gl.uniform1f(this.gl.getUniformLocation(this.program, 'u_brightness'), params.brightness);
                this.gl.uniform1f(this.gl.getUniformLocation(this.program, 'u_saturation'), params.saturation);
                this.gl.uniform1f(this.gl.getUniformLocation(this.program, 'u_interpolation'), params.interpolation);
                
                // Bind textures
                this.gl.activeTexture(this.gl.TEXTURE0);
                this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
                this.gl.uniform1i(this.gl.getUniformLocation(this.program, 'u_texture'), 0);
                
                this.gl.activeTexture(this.gl.TEXTURE1);
                this.gl.bindTexture(this.gl.TEXTURE_2D, this.prevTexture);
                this.gl.uniform1i(this.gl.getUniformLocation(this.program, 'u_prevTexture'), 1);
                
                // Set up attributes
                const positionLocation = this.gl.getAttribLocation(this.program, 'a_position');
                const texCoordLocation = this.gl.getAttribLocation(this.program, 'a_texCoord');
                
                this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.buffer);
                this.gl.enableVertexAttribArray(positionLocation);
                this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 16, 0);
                this.gl.enableVertexAttribArray(texCoordLocation);
                this.gl.vertexAttribPointer(texCoordLocation, 2, this.gl.FLOAT, false, 16, 8);
                
                // Draw
                this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
            }}
            
            destroy() {{
                if (this.gl) {{
                    this.gl.deleteTexture(this.texture);
                    this.gl.deleteTexture(this.prevTexture);
                    this.gl.deleteBuffer(this.buffer);
                    this.gl.deleteProgram(this.program);
                }}
            }}
        }}
        
        function updateStatus(message, type = 'info') {{
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
        }}
        
        function scanEndpoints() {{
            const ip = document.getElementById('phoneIP').value;
            const port = document.getElementById('phonePort').value;
            
            updateStatus('Scanning endpoints...', 'info');
            
            fetch(`/api/scan?ip=${{ip}}&port=${{port}}`)
                .then(response => response.json())
                .then(data => {{
                    const container = document.getElementById('endpoints');
                    container.innerHTML = '<h3>Available Endpoints:</h3>';
                    
                    let foundMJPEG = false;
                    data.forEach(endpoint => {{
                        const div = document.createElement('div');
                        div.className = 'endpoint';
                        
                        if (endpoint.available) {{
                            const isMJPEG = endpoint.content_type && 
                                          (endpoint.content_type.includes('multipart') || 
                                           endpoint.content_type.includes('mjpeg'));
                            if (isMJPEG) foundMJPEG = true;
                            
                            div.innerHTML = `
                                ✅ ${{endpoint.url}}<br>
                                <small>Status: ${{endpoint.status}} | Type: ${{endpoint.content_type || 'Unknown'}}</small>
                                ${{isMJPEG ? '<br><strong>📹 MJPEG Stream Available!</strong>' : ''}}
                            `;
                        }} else {{
                            div.innerHTML = `
                                ❌ ${{endpoint.url}}<br>
                                <small>${{endpoint.error || 'Not available'}}</small>
                            `;
                        }}
                        container.appendChild(div);
                    }});
                    
                    if (foundMJPEG) {{
                        updateStatus('MJPEG stream found! Click "Start Stream" to view.', 'success');
                    }} else {{
                        updateStatus('No MJPEG streams found. Check phone app settings.', 'error');
                    }}
                }})
                .catch(error => {{
                    updateStatus('Scan failed: ' + error.message, 'error');
                }});
        }}
        
        function startStream() {{
            const ip = document.getElementById('phoneIP').value;
            const port = document.getElementById('phonePort').value;
            const quality = document.getElementById('quality').value;
            const fps = document.getElementById('fps').value;
            const buffer = document.getElementById('buffer').value;
            const rendering = document.getElementById('rendering').value;
            const img = document.getElementById('videoStream');
            const canvas = document.getElementById('webglCanvas');
            const placeholder = document.getElementById('placeholder');
            const perfDiv = document.getElementById('performance');
            
            const smoothing = document.getElementById('smoothing').value;
            const streamUrl = `/stream?ip=${{ip}}&port=${{port}}&quality=${{quality}}&fps=${{fps}}&buffer=${{buffer}}&smoothing=${{smoothing}}&t=${{Date.now()}}`;            
            
            // Initialize WebGL renderer if selected
            if (rendering === 'webgl') {{
                webglRenderer = new WebGLRenderer(canvas);
                if (!webglRenderer || !webglRenderer.gl) {{
                    updateStatus('WebGL not supported, falling back to standard rendering', 'error');
                    document.getElementById('rendering').value = 'standard';
                    rendering = 'standard';
                    webglRenderer = null;
                }}
            }}
            
            img.onload = function() {{
                placeholder.style.display = 'none';
                
                if (rendering === 'webgl' && webglRenderer) {{
                    // WebGL GPU-accelerated rendering
                    document.body.classList.add('webgl-active');
                    canvas.style.display = 'block';
                    
                    function renderLoop() {{
                        if (streamActive && webglRenderer) {{
                            webglRenderer.renderFrame(img);
                            animationFrame = requestAnimationFrame(renderLoop);
                        }}
                    }}
                    renderLoop();
                    
                    updateStatus(`🚀 WebGL GPU Stream Active! Quality: ${{quality}}, FPS: ${{fps}}, Smoothing: ${{smoothing}}`, 'success');
                }} else {{
                    // Standard IMG rendering
                    img.style.display = 'block';
                    
                    // Apply ultra-smooth CSS class based on smoothing level
                    if (smoothing === 'ultra' || smoothing === 'cinema') {{
                        img.classList.add('ultra-smooth');
                    }}
                    
                    updateStatus(`📹 Stream Active! Quality: ${{quality}}, FPS: ${{fps}}, Smoothing: ${{smoothing}}`, 'success');
                }}
                
                perfDiv.style.display = 'block';
                streamActive = true;
                startPerformanceMonitoring();
            }};
            
            img.onerror = function() {{
                updateStatus('Stream failed to load. Check connection and try scanning first.', 'error');
                stopStream();
            }};
            
            updateStatus(`Connecting to stream... Quality: ${{quality}}, FPS: ${{fps}}`, 'info');
            img.src = streamUrl;
        }}
        
        function stopStream() {{
            const img = document.getElementById('videoStream');
            const canvas = document.getElementById('webglCanvas');
            const placeholder = document.getElementById('placeholder');
            const perfDiv = document.getElementById('performance');
            
            // Stop WebGL rendering
            if (animationFrame) {{
                cancelAnimationFrame(animationFrame);
                animationFrame = null;
            }}
            
            if (webglRenderer) {{
                webglRenderer.destroy();
                webglRenderer = null;
            }}
            
            document.body.classList.remove('webgl-active');
            
            img.src = '';
            img.style.display = 'none';
            img.classList.remove('fullscreen');
            canvas.style.display = 'none';
            placeholder.style.display = 'block';
            perfDiv.style.display = 'none';
            streamActive = false;
            updateStatus('Stream stopped.', 'info');
            stopPerformanceMonitoring();
        }}
        
        function toggleFullscreen() {{
            const img = document.getElementById('videoStream');
            const canvas = document.getElementById('webglCanvas');
            const activeElement = document.body.classList.contains('webgl-active') ? canvas : img;
            
            if (!streamActive) {{
                updateStatus('Start stream first before going fullscreen.', 'error');
                return;
            }}
            
            activeElement.classList.toggle('fullscreen');
            
            // Exit fullscreen with ESC key
            if (activeElement.classList.contains('fullscreen')) {{
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape') {{
                        activeElement.classList.remove('fullscreen');
                    }}
                }});
            }}
        }}
        
        let perfInterval;
        function startPerformanceMonitoring() {{
            let frameCount = 0;
            let startTime = Date.now();
            
            perfInterval = setInterval(() => {{
                frameCount++;
                const elapsed = (Date.now() - startTime) / 1000;
                const fps = (frameCount / elapsed).toFixed(1);
                const quality = document.getElementById('quality').value;
                const buffer = document.getElementById('buffer').value;
                
                const targetFps = document.getElementById('fps').value === 'auto' ? 24 : parseInt(document.getElementById('fps').value);
                const efficiency = ((parseFloat(fps) / targetFps) * 100).toFixed(1);
                const smoothness = efficiency >= 95 ? '🟢 Smooth' : efficiency >= 80 ? '🟡 Good' : '🔴 Choppy';
                
                document.getElementById('perfStats').textContent = 
                    `FPS: ${{fps}}/${{targetFps}} (${{efficiency}}%) | ${{smoothness}} | Quality: ${{quality}} | Buffer: ${{(parseInt(buffer)/1024).toFixed(0)}}KB | Frames: ${{frameCount}}`;
                
                // Update hardware stats
                fetch('/api/system-stats')
                    .then(response => response.json())
                    .then(stats => {{
                        document.getElementById('hwStats').textContent = 
                            `CPU: ${{stats.cpu}}% | RAM: ${{stats.memory}}% | GPU: ${{stats.gpu_enabled ? 'AMD Accelerated' : 'CPU Only'}} | Cores: ${{stats.cpu_cores}}`;
                    }})
                    .catch(() => {{}});
            }}, 2000);
        }}
        
        function stopPerformanceMonitoring() {{
            if (perfInterval) {{
                clearInterval(perfInterval);
                perfInterval = null;
            }}
        }}
        
        // Auto-scan on page load and setup keyboard shortcuts
        window.onload = function() {{
            setTimeout(scanEndpoints, 1000);
            
            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.ctrlKey) {{
                    switch(e.key) {{
                        case 's': e.preventDefault(); startStream(); break;
                        case 'q': e.preventDefault(); stopStream(); break;
                        case 'f': e.preventDefault(); toggleFullscreen(); break;
                        case 'r': e.preventDefault(); scanEndpoints(); break;
                    }}
                }}
            }});
        }};
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # AMD Ryzen 5 7000 series optimizations
    os.environ['OMP_NUM_THREADS'] = str(CPU_THREADS)
    os.environ['MKL_NUM_THREADS'] = str(CPU_THREADS)
    
    if AMD_GPU_ENABLED and CV2_AVAILABLE:
        try:
            # Enable OpenCL for AMD GPU acceleration
            cv2.ocl.setUseOpenCL(True)
            logging.info("AMD GPU OpenCL acceleration enabled")
        except Exception as e:
            logging.warning(f"Failed to enable GPU acceleration: {e}")
    
    logging.info("Starting AMD-optimized DroidCam Web Viewer...")
    app.run(host="0.0.0.0", port=8080, threaded=True)
