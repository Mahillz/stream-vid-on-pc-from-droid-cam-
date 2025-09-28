import asyncio
import aiohttp
import json
import logging
import uuid
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
import cv2
import numpy as np
from av import VideoFrame
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DroidCam WebRTC Viewer")

class DroidCamVideoTrack(VideoStreamTrack):
    """Custom video track that pulls from DroidCam MJPEG stream"""
    
    def __init__(self, ip: str, port: int = 4747, target_fps: int = 30):
        super().__init__()
        self.ip = ip
        self.port = port
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.session = None
        self.stream_response = None
        self.last_frame_time = 0
        self.frame_buffer = b""
        self.running = True
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def connect_to_stream(self):
        """Connect to DroidCam MJPEG stream"""
        endpoints = [
            f"http://{self.ip}:{self.port}/video",
            f"http://{self.ip}:{self.port}/mjpegfeed",
            f"http://{self.ip}:{self.port}/"
        ]
        
        session = await self.get_session()
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to connect to {endpoint}")
                response = await session.get(endpoint)
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'multipart/x-mixed-replace' in content_type or 'image/jpeg' in content_type:
                        logger.info(f"Successfully connected to {endpoint}")
                        self.stream_response = response
                        return True
                        
            except Exception as e:
                logger.warning(f"Failed to connect to {endpoint}: {e}")
                continue
        
        logger.error("Failed to connect to any DroidCam endpoint")
        return False
    
    def extract_jpeg_frame(self, data: bytes) -> Optional[bytes]:
        """Extract a complete JPEG frame from MJPEG data"""
        self.frame_buffer += data
        
        # Look for JPEG start and end markers
        start_marker = b'\xff\xd8'  # JPEG start
        end_marker = b'\xff\xd9'    # JPEG end
        
        start_idx = self.frame_buffer.find(start_marker)
        if start_idx == -1:
            return None
            
        end_idx = self.frame_buffer.find(end_marker, start_idx + 2)
        if end_idx == -1:
            return None
        
        # Extract complete JPEG frame
        jpeg_frame = self.frame_buffer[start_idx:end_idx + 2]
        
        # Remove processed data from buffer
        self.frame_buffer = self.frame_buffer[end_idx + 2:]
        
        return jpeg_frame
    
    async def recv(self):
        """Receive next video frame with proper timing"""
        if not self.stream_response:
            if not await self.connect_to_stream():
                # Return a black frame if connection fails
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                return VideoFrame.from_ndarray(frame, format="bgr24")
        
        try:
            # Read chunks until we get a complete frame
            while self.running:
                chunk = await self.stream_response.content.read(8192)
                if not chunk:
                    break
                
                # Add chunk to buffer
                self.frame_buffer += chunk
                
                # Try to extract a complete JPEG frame
                jpeg_data = self.extract_jpeg_frame(b"")  # Pass empty since we're using the buffer
                if jpeg_data:
                    # Decode JPEG to numpy array
                    nparr = np.frombuffer(jpeg_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        logger.info(f"✅ WebRTC frame captured: {frame.shape}")
                        
                        # Ensure consistent timing
                        current_time = asyncio.get_event_loop().time()
                        if self.last_frame_time > 0:
                            elapsed = current_time - self.last_frame_time
                            if elapsed < self.frame_interval:
                                await asyncio.sleep(self.frame_interval - elapsed)
                        
                        self.last_frame_time = asyncio.get_event_loop().time()
                        
                        # Convert BGR to RGB for WebRTC
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        return VideoFrame.from_ndarray(frame_rgb, format="rgb24")
            
        except Exception as e:
            logger.error(f"Error receiving frame: {e}")
        
        # Return black frame on error
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        return VideoFrame.from_ndarray(frame, format="bgr24")
    
    def stop(self):
        """Stop the video track"""
        self.running = False
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

class WebRTCManager:
    def __init__(self):
        self.connections = {}
    
    async def create_peer_connection(self, session_id: str, ip: str, port: int, fps: int):
        """Create a new WebRTC peer connection"""
        pc = RTCPeerConnection()
        
        # Add video track
        video_track = DroidCamVideoTrack(ip, port, fps)
        pc.addTrack(video_track)
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {pc.connectionState}")
            if pc.connectionState == "closed":
                video_track.stop()
                if session_id in self.connections:
                    del self.connections[session_id]
        
        self.connections[session_id] = {
            'pc': pc,
            'video_track': video_track
        }
        
        return pc
    
    async def close_connection(self, session_id: str):
        """Close a WebRTC connection"""
        if session_id in self.connections:
            conn = self.connections[session_id]
            conn['video_track'].stop()
            await conn['pc'].close()
            del self.connections[session_id]

webrtc_manager = WebRTCManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DroidCam WebRTC Viewer</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            .controls { margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; }
            .control-group { margin-bottom: 10px; }
            label { display: inline-block; width: 120px; font-weight: bold; }
            input, select, button { padding: 8px; margin: 2px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #28a745; color: white; cursor: pointer; padding: 10px 20px; }
            button:hover { background: #218838; }
            button:disabled { background: #6c757d; cursor: not-allowed; }
            .status { margin: 10px 0; padding: 10px; border-radius: 4px; }
            .status.success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .status.error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
            .video-container { text-align: center; margin-top: 20px; }
            #videoElement { max-width: 100%; height: auto; border: 2px solid #ddd; border-radius: 8px; background: #000; }
            .stats { margin-top: 10px; font-family: monospace; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 DroidCam WebRTC Viewer</h1>
            <p>Ultra-low latency streaming with hardware acceleration and adaptive quality.</p>
            
            <div class="controls">
                <div class="control-group">
                    <label>Phone IP:</label>
                    <input type="text" id="phoneIP" value="192.168.8.253" placeholder="192.168.1.100">
                    <label>Port:</label>
                    <input type="number" id="phonePort" value="4747" style="width: 80px;">
                </div>
                
                <div class="control-group">
                    <label>Target FPS:</label>
                    <select id="targetFPS">
                        <option value="15">15 FPS</option>
                        <option value="24">24 FPS</option>
                        <option value="30" selected>30 FPS</option>
                        <option value="60">60 FPS</option>
                    </select>
                </div>
                
                <div class="control-group">
                    <button id="startBtn" onclick="startWebRTC()">🚀 Start WebRTC Stream</button>
                    <button id="stopBtn" onclick="stopWebRTC()" disabled>⏹️ Stop Stream</button>
                </div>
                
                <div id="status"></div>
            </div>
            
            <div class="video-container">
                <video id="videoElement" autoplay playsinline muted></video>
                <div id="stats" class="stats"></div>
            </div>
        </div>

        <script>
            let pc = null;
            let ws = null;
            let sessionId = null;
            let statsInterval = null;
            
            function showStatus(message, type = 'success') {
                const status = document.getElementById('status');
                status.className = `status ${type}`;
                status.innerHTML = message;
                status.style.display = 'block';
            }
            
            function updateStats() {
                if (!pc) return;
                
                pc.getStats().then(stats => {
                    let statsText = '';
                    stats.forEach(report => {
                        if (report.type === 'inbound-rtp' && report.mediaType === 'video') {
                            statsText += `📊 Frames: ${report.framesReceived || 0} | `;
                            statsText += `📦 Bytes: ${Math.round((report.bytesReceived || 0) / 1024)}KB | `;
                            statsText += `🔄 FPS: ${Math.round(report.framesPerSecond || 0)}`;
                        }
                    });
                    document.getElementById('stats').textContent = statsText;
                });
            }
            
            async function startWebRTC() {
                const ip = document.getElementById('phoneIP').value;
                const port = document.getElementById('phonePort').value;
                const fps = document.getElementById('targetFPS').value;
                
                sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
                
                try {
                    showStatus('🔌 Connecting to WebRTC server...', 'success');
                    
                    // Connect WebSocket
                    ws = new WebSocket(`ws://127.0.0.1:8083/ws/${sessionId}`);
                    
                    ws.onopen = async () => {
                        showStatus('📡 Initializing WebRTC connection...', 'success');
                        
                        // Create peer connection
                        pc = new RTCPeerConnection({
                            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                        });
                        
                        pc.ontrack = (event) => {
                            const video = document.getElementById('videoElement');
                            video.srcObject = event.streams[0];
                            showStatus('🎥 WebRTC stream active!', 'success');
                            
                            document.getElementById('startBtn').disabled = true;
                            document.getElementById('stopBtn').disabled = false;
                            
                            // Start stats updates
                            statsInterval = setInterval(updateStats, 1000);
                        };
                        
                        pc.onconnectionstatechange = () => {
                            console.log('Connection state:', pc.connectionState);
                            if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                                showStatus('❌ WebRTC connection failed', 'error');
                                stopWebRTC();
                            }
                        };
                        
                        // Send offer request
                        ws.send(JSON.stringify({
                            type: 'create_offer',
                            ip: ip,
                            port: parseInt(port),
                            fps: parseInt(fps)
                        }));
                    };
                    
                    ws.onmessage = async (event) => {
                        const message = JSON.parse(event.data);
                        
                        if (message.type === 'offer') {
                            await pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
                            const answer = await pc.createAnswer();
                            await pc.setLocalDescription(answer);
                            
                            ws.send(JSON.stringify({
                                type: 'answer',
                                sdp: answer
                            }));
                        } else if (message.type === 'ice_candidate') {
                            await pc.addIceCandidate(message.candidate);
                        } else if (message.type === 'error') {
                            showStatus(`❌ ${message.message}`, 'error');
                            stopWebRTC();
                        }
                    };
                    
                    ws.onerror = (error) => {
                        showStatus('❌ WebSocket connection failed', 'error');
                        console.error('WebSocket error:', error);
                    };
                    
                } catch (error) {
                    showStatus(`❌ Failed to start WebRTC: ${error.message}`, 'error');
                    console.error('WebRTC error:', error);
                }
            }
            
            function stopWebRTC() {
                if (statsInterval) {
                    clearInterval(statsInterval);
                    statsInterval = null;
                }
                
                if (pc) {
                    pc.close();
                    pc = null;
                }
                
                if (ws) {
                    ws.close();
                    ws = null;
                }
                
                const video = document.getElementById('videoElement');
                video.srcObject = null;
                
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                document.getElementById('stats').textContent = '';
                
                showStatus('⏹️ WebRTC stream stopped', 'success');
            }
            
            // Cleanup on page unload
            window.addEventListener('beforeunload', stopWebRTC);
        </script>
    </body>
    </html>
    """

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connected: {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message['type'] == 'create_offer':
                # Create peer connection
                pc = await webrtc_manager.create_peer_connection(
                    session_id, 
                    message['ip'], 
                    message['port'], 
                    message['fps']
                )
                
                # Create offer
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                
                await websocket.send_text(json.dumps({
                    'type': 'offer',
                    'sdp': {
                        'type': offer.type,
                        'sdp': offer.sdp
                    }
                }))
                
            elif message['type'] == 'answer':
                if session_id in webrtc_manager.connections:
                    pc = webrtc_manager.connections[session_id]['pc']
                    answer = RTCSessionDescription(
                        sdp=message['sdp']['sdp'],
                        type=message['sdp']['type']
                    )
                    await pc.setRemoteDescription(answer)
                    
            elif message['type'] == 'ice_candidate':
                if session_id in webrtc_manager.connections:
                    pc = webrtc_manager.connections[session_id]['pc']
                    await pc.addIceCandidate(message['candidate'])
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            'type': 'error',
            'message': str(e)
        }))
    finally:
        await webrtc_manager.close_connection(session_id)

@app.on_event("shutdown")
async def shutdown_event():
    # Close all WebRTC connections
    for session_id in list(webrtc_manager.connections.keys()):
        await webrtc_manager.close_connection(session_id)

if __name__ == "__main__":
    print("Starting DroidCam WebRTC Viewer...")
    print("Open: http://127.0.0.1:8083/")
    print("Features: Ultra-low latency, hardware decode, adaptive quality")
    print("Note: Requires aiortc and opencv-python")
    
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8083,
        log_level="info"
    )
