#!/usr/bin/env python3
"""
DroidCam Connection Diagnostic Tool
Tests direct connection to DroidCam endpoints to identify issues
"""

import requests
import time
import sys

def test_droidcam_connection(ip="192.168.8.253", port="4747"):
    """Test DroidCam connection and diagnose issues"""
    print(f"Testing DroidCam connection to {ip}:{port}")
    print("=" * 50)
    
    endpoints = [
        f"http://{ip}:{port}/video",
        f"http://{ip}:{port}/mjpegfeed", 
        f"http://{ip}:{port}",
        f"http://{ip}:{port}/jpg",
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting: {endpoint}")
        try:
            # Test HEAD request first
            print("  -> HEAD request...")
            head_resp = requests.head(endpoint, timeout=5)
            print(f"    Status: {head_resp.status_code}")
            print(f"    Headers: {dict(head_resp.headers)}")
            
            if head_resp.status_code == 200:
                # Test GET request
                print("  -> GET request (first 1KB)...")
                get_resp = requests.get(endpoint, stream=True, timeout=5)
                
                if get_resp.status_code == 200:
                    content_type = get_resp.headers.get('Content-Type', '')
                    print(f"    Content-Type: {content_type}")
                    
                    # Read first chunk
                    try:
                        first_chunk = next(get_resp.iter_content(chunk_size=1024))
                        print(f"    First chunk size: {len(first_chunk)} bytes")
                        print(f"    First 100 chars: {first_chunk[:100]}")
                        
                        if "multipart" in content_type.lower() or "mjpeg" in content_type.lower():
                            print("    SUCCESS: MJPEG stream detected!")
                            
                            # Test streaming for 5 seconds
                            print("  -> Testing stream for 5 seconds...")
                            start_time = time.time()
                            chunk_count = 0
                            total_bytes = 0
                            
                            for chunk in get_resp.iter_content(chunk_size=8192):
                                if chunk:
                                    chunk_count += 1
                                    total_bytes += len(chunk)
                                    
                                    if time.time() - start_time > 5:
                                        break
                            
                            elapsed = time.time() - start_time
                            print(f"    Chunks received: {chunk_count}")
                            print(f"    Total bytes: {total_bytes}")
                            print(f"    Average rate: {total_bytes/elapsed:.1f} bytes/sec")
                            print(f"    Estimated FPS: {chunk_count/elapsed:.1f}")
                            
                            if chunk_count > 0:
                                print("    SUCCESS: Stream is working!")
                                return endpoint
                        else:
                            print(f"    ERROR: Not MJPEG stream: {content_type}")
                    except Exception as e:
                        print(f"    ERROR: Stream read error: {e}")
                else:
                    print(f"    ERROR: GET failed: {get_resp.status_code}")
                
                get_resp.close()
            else:
                print(f"    ERROR: HEAD failed: {head_resp.status_code}")
                
        except requests.exceptions.Timeout:
            print("    ERROR: Timeout - DroidCam not responding")
        except requests.exceptions.ConnectionError:
            print("    ERROR: Connection failed - check IP/port")
        except Exception as e:
            print(f"    ERROR: {e}")
    
    print("\nERROR: No working MJPEG stream found!")
    print("\nTroubleshooting tips:")
    print("1. Make sure DroidCam app is running on your phone")
    print("2. Check that WiFi IP matches (phone settings -> about)")
    print("3. Ensure phone and PC are on same network")
    print("4. Try restarting DroidCam app")
    print("5. Check if firewall is blocking connection")
    
    return None

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.8.253"
    port = sys.argv[2] if len(sys.argv) > 2 else "4747"
    
    working_endpoint = test_droidcam_connection(ip, port)
    
    if working_endpoint:
        print(f"\nSUCCESS! Use this endpoint: {working_endpoint}")
    else:
        print(f"\nERROR: No working endpoints found for {ip}:{port}")
