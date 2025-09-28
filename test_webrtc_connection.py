#!/usr/bin/env python3
"""
Simple WebRTC connection test to verify WebSocket connectivity
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_webrtc_websocket():
    """Test WebSocket connection to WebRTC viewer"""
    uri = "ws://127.0.0.1:8083/ws/test_session_123"
    
    try:
        logger.info(f"Attempting to connect to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket connected successfully!")
            
            # Send a test message
            test_message = {
                "type": "create_offer",
                "ip": "192.168.8.253",
                "port": 4747,
                "fps": 30
            }
            
            logger.info("Sending test message...")
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            logger.info("Waiting for response...")
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            
            logger.info(f"✅ Received response: {response}")
            
            return True
            
    except websockets.exceptions.ConnectionRefused as e:
        logger.error(f"❌ Connection refused: {e}")
        return False
    except asyncio.TimeoutError:
        logger.error("❌ Timeout waiting for response")
        return False
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🧪 Testing WebRTC WebSocket Connection...")
    logger.info("WebRTC Server should be running on http://127.0.0.1:8083/")
    
    success = await test_webrtc_websocket()
    
    if success:
        logger.info("🎉 WebRTC WebSocket test PASSED!")
    else:
        logger.error("💥 WebRTC WebSocket test FAILED!")
        logger.info("Troubleshooting tips:")
        logger.info("1. Make sure WebRTC viewer is running on port 8083")
        logger.info("2. Check if there are any firewall issues")
        logger.info("3. Verify WebSocket endpoint is correctly implemented")

if __name__ == "__main__":
    asyncio.run(main())
