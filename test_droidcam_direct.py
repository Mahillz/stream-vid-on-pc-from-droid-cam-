import requests
import time

def test_droidcam_endpoint(ip="192.168.8.253", port=4747):
    """Test DroidCam endpoint directly to see what it returns"""
    
    url = f"http://{ip}:{port}/video"
    print(f"Testing DroidCam at: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'multipart/x-mixed-replace,*/*',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache'
    }
    
    try:
        print("Making request...")
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            
            if 'text/html' in content_type:
                print("\nERROR: DroidCam returned HTML instead of video stream")
                print("First 500 chars of response:")
                print("-" * 50)
                print(response.text[:500])
                print("-" * 50)
                print("\nThis usually means:")
                print("1. DroidCam app is not started or camera not active")
                print("2. Camera permission not granted to DroidCam")
                print("3. Another app is using the camera")
                print("4. DroidCam is in 'Busy' state")
                
            elif 'multipart/x-mixed-replace' in content_type:
                print("\n✅ SUCCESS: DroidCam is serving MJPEG stream")
                print("Reading first few chunks...")
                
                chunk_count = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        chunk_count += 1
                        print(f"Chunk {chunk_count}: {len(chunk)} bytes")
                        
                        if chunk_count >= 3:  # Read first 3 chunks
                            break
                            
                print("✅ Stream is working!")
                
            else:
                print(f"\n⚠️  WARNING: Unexpected content type: {content_type}")
                
        else:
            print(f"\n❌ ERROR: HTTP {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"\nCONNECTION ERROR: Cannot connect to {url}")
        print("Check:")
        print("1. DroidCam app is running on phone")
        print("2. Phone and PC are on same WiFi network")
        print("3. IP address is correct")
        
    except requests.exceptions.Timeout:
        print(f"\nTIMEOUT: {url} did not respond within 10 seconds")
        
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    print("DroidCam Direct Test")
    print("=" * 50)
    test_droidcam_endpoint()
