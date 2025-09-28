#!/usr/bin/env python3
"""
DroidCam IP Scanner - Find DroidCam on your network
"""

import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor

def test_ip(ip):
    """Test if DroidCam is running on this IP"""
    try:
        # Quick test with short timeout
        response = requests.head(f"http://{ip}:4747/video", timeout=2)
        if response.status_code == 200:
            return ip, "SUCCESS - DroidCam found!"
        else:
            return ip, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return ip, "Timeout"
    except requests.exceptions.ConnectionError:
        return ip, "No connection"
    except Exception as e:
        return ip, f"Error: {e}"

def scan_network(base_ip="192.168.8"):
    """Scan network for DroidCam"""
    print(f"Scanning {base_ip}.1-254 for DroidCam...")
    print("This may take 30-60 seconds...")
    print("=" * 50)
    
    # Test common IPs first
    priority_ips = [f"{base_ip}.{i}" for i in [100, 101, 102, 103, 104, 105, 150, 200, 10, 20, 50]]
    regular_ips = [f"{base_ip}.{i}" for i in range(1, 255) if f"{base_ip}.{i}" not in priority_ips]
    
    all_ips = priority_ips + regular_ips
    found_devices = []
    
    # Use threading for faster scanning
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(test_ip, all_ips)
        
        for ip, status in results:
            if "SUCCESS" in status:
                print(f"FOUND: {ip} - {status}")
                found_devices.append(ip)
            elif "HTTP" in status:
                print(f"Device: {ip} - {status}")
            # Skip printing timeouts/no connections to reduce noise
    
    print("=" * 50)
    if found_devices:
        print(f"DroidCam found at: {found_devices}")
        return found_devices[0]
    else:
        print("No DroidCam devices found on network")
        print("\nTroubleshooting:")
        print("1. Make sure DroidCam app is running on phone")
        print("2. Check phone and PC are on same WiFi")
        print("3. Try restarting DroidCam app")
        print("4. Check phone's IP in WiFi settings")
        return None

if __name__ == "__main__":
    import sys
    
    # Allow custom network base (e.g., "192.168.1" or "10.0.0")
    base = sys.argv[1] if len(sys.argv) > 1 else "192.168.8"
    
    found_ip = scan_network(base)
    
    if found_ip:
        print(f"\nTesting connection to {found_ip}...")
        # Import and run the connection test
        import test_droidcam
        test_droidcam.test_droidcam_connection(found_ip, "4747")
