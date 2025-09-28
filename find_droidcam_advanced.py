import socket
import threading
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_local_network():
    """Get the local network range"""
    try:
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Extract network base (e.g., 192.168.1.x)
        network_base = '.'.join(local_ip.split('.')[:-1])
        return network_base, local_ip
    except:
        return "192.168.1", "192.168.1.100"

def test_droidcam_ip(ip, port=4747, timeout=2):
    """Test if DroidCam is running at given IP"""
    endpoints = ['/video', '/mjpegfeed', '/', '/cam/1/stream']
    
    for endpoint in endpoints:
        try:
            url = f"http://{ip}:{port}{endpoint}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'multipart/x-mixed-replace,*/*',
                'Connection': 'close'
            }
            
            response = requests.head(url, headers=headers, timeout=timeout)
            content_type = response.headers.get('content-type', '').lower()
            
            if response.status_code == 200:
                if 'multipart/x-mixed-replace' in content_type:
                    return {
                        'ip': ip,
                        'port': port,
                        'endpoint': endpoint,
                        'status': 'MJPEG_READY',
                        'content_type': content_type,
                        'url': url
                    }
                elif 'text/html' in content_type:
                    return {
                        'ip': ip,
                        'port': port,
                        'endpoint': endpoint,
                        'status': 'HTML_RESPONSE',
                        'content_type': content_type,
                        'url': url
                    }
                else:
                    return {
                        'ip': ip,
                        'port': port,
                        'endpoint': endpoint,
                        'status': 'UNKNOWN_CONTENT',
                        'content_type': content_type,
                        'url': url
                    }
        except:
            continue
    
    return None

def scan_network_for_droidcam():
    """Scan local network for DroidCam instances"""
    print("Advanced DroidCam Network Scanner")
    print("=" * 50)
    
    network_base, local_ip = get_local_network()
    print(f"Local IP: {local_ip}")
    print(f"Scanning network: {network_base}.1-254")
    print("This may take 30-60 seconds...")
    print()
    
    found_devices = []
    
    # Test common DroidCam ports
    ports_to_test = [4747, 4748, 8080, 8081]
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        
        for port in ports_to_test:
            for i in range(1, 255):
                ip = f"{network_base}.{i}"
                if ip != local_ip:  # Skip our own IP
                    future = executor.submit(test_droidcam_ip, ip, port)
                    futures.append(future)
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0:
                print(f"Scanned {completed}/{len(futures)} addresses...")
            
            result = future.result()
            if result:
                found_devices.append(result)
                print(f"FOUND: {result['ip']}:{result['port']} - {result['status']}")
    
    print("\n" + "=" * 50)
    print("SCAN RESULTS:")
    print("=" * 50)
    
    if not found_devices:
        print("No DroidCam devices found on network")
        print("\nTroubleshooting:")
        print("1. Make sure DroidCam app is running on phone")
        print("2. Check phone and PC are on same WiFi")
        print("3. Try restarting DroidCam app")
        print("4. Check phone's IP in WiFi settings")
    else:
        for device in found_devices:
            print(f"\nDevice: {device['ip']}:{device['port']}")
            print(f"Endpoint: {device['endpoint']}")
            print(f"Status: {device['status']}")
            print(f"Content-Type: {device['content_type']}")
            print(f"Full URL: {device['url']}")
            
            if device['status'] == 'MJPEG_READY':
                print("✅ READY FOR STREAMING!")
            elif device['status'] == 'HTML_RESPONSE':
                print("⚠️  DroidCam found but returning HTML (check app status)")
            else:
                print("❓ Unknown response type")
    
    return found_devices

if __name__ == "__main__":
    found = scan_network_for_droidcam()
    
    if found:
        print(f"\n🎯 RECOMMENDATION:")
        mjpeg_ready = [d for d in found if d['status'] == 'MJPEG_READY']
        if mjpeg_ready:
            best = mjpeg_ready[0]
            print(f"Use IP: {best['ip']}")
            print(f"Use Port: {best['port']}")
            print(f"Test URL: {best['url']}")
        else:
            html_devices = [d for d in found if d['status'] == 'HTML_RESPONSE']
            if html_devices:
                device = html_devices[0]
                print(f"DroidCam found at {device['ip']}:{device['port']} but not streaming")
                print("Try restarting DroidCam app or check camera permissions")
