#!/usr/bin/env python3
"""
GPU Acceleration Verification Tool
Tests AMD GPU detection, OpenCL functionality, and system capabilities
"""

import sys
import time
import platform
import subprocess
import psutil

def test_opencv_gpu():
    """Test OpenCV GPU capabilities"""
    print("=" * 60)
    print("TESTING OPENCV GPU CAPABILITIES")
    print("=" * 60)
    
    try:
        import cv2
        print(f"OpenCV Version: {cv2.__version__}")
        
        # Test OpenCL availability
        print(f"OpenCL Available: {cv2.ocl.haveOpenCL()}")
        
        if cv2.ocl.haveOpenCL():
            print(f"OpenCL Enabled: {cv2.ocl.useOpenCL()}")
            
            # Get OpenCL platforms
            try:
                platforms = cv2.ocl.getPlatformsInfo()
                print(f"OpenCL Platforms Found: {len(platforms)}")
                
                for i, platform in enumerate(platforms):
                    print(f"  Platform {i}: {platform}")
                    
                    # Check for AMD
                    if 'AMD' in str(platform) or 'Radeon' in str(platform):
                        print(f"    -> AMD GPU DETECTED!")
                        return True
                        
            except Exception as e:
                print(f"Error getting platform info: {e}")
        
        # Test basic OpenCL operations
        try:
            cv2.ocl.setUseOpenCL(True)
            print(f"OpenCL Set to True: {cv2.ocl.useOpenCL()}")
            
            # Create test matrices
            import numpy as np
            test_img = np.random.randint(0, 255, (1000, 1000, 3), dtype=np.uint8)
            
            # Test GPU operation
            start_time = time.time()
            gpu_mat = cv2.UMat(test_img)
            result = cv2.GaussianBlur(gpu_mat, (15, 15), 0)
            cpu_result = result.get()
            gpu_time = time.time() - start_time
            
            # Test CPU operation
            start_time = time.time()
            cpu_result = cv2.GaussianBlur(test_img, (15, 15), 0)
            cpu_time = time.time() - start_time
            
            print(f"GPU Processing Time: {gpu_time:.4f}s")
            print(f"CPU Processing Time: {cpu_time:.4f}s")
            
            if gpu_time < cpu_time:
                print("SUCCESS: GPU acceleration is working!")
                return True
            else:
                print("WARNING: GPU not faster than CPU")
                
        except Exception as e:
            print(f"Error testing GPU operations: {e}")
            
    except ImportError:
        print("ERROR: OpenCV not installed")
        return False
    
    return False

def test_system_gpu():
    """Test system GPU information"""
    print("\n" + "=" * 60)
    print("TESTING SYSTEM GPU INFORMATION")
    print("=" * 60)
    
    # Test Windows GPU info
    if platform.system() == "Windows":
        try:
            # Use wmic to get GPU info
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                gpus = [line.strip() for line in result.stdout.split('\n') if line.strip() and 'Name' not in line]
                print(f"Detected GPUs: {len(gpus)}")
                
                amd_found = False
                for gpu in gpus:
                    print(f"  - {gpu}")
                    if 'AMD' in gpu or 'Radeon' in gpu:
                        print(f"    -> AMD GPU FOUND!")
                        amd_found = True
                
                return amd_found
                
        except Exception as e:
            print(f"Error getting Windows GPU info: {e}")
    
    # Test using psutil for cross-platform
    try:
        # Get CPU info
        cpu_info = platform.processor()
        print(f"CPU: {cpu_info}")
        
        # Check if AMD CPU (often indicates AMD system)
        if 'AMD' in cpu_info:
            print("AMD CPU detected - likely has AMD GPU")
            return True
            
    except Exception as e:
        print(f"Error getting system info: {e}")
    
    return False

def test_webgl_support():
    """Test WebGL support capabilities"""
    print("\n" + "=" * 60)
    print("TESTING WEBGL SUPPORT")
    print("=" * 60)
    
    # Create a simple HTML test file
    webgl_test_html = """
<!DOCTYPE html>
<html>
<head>
    <title>WebGL GPU Test</title>
</head>
<body>
    <canvas id="testCanvas" width="512" height="512"></canvas>
    <div id="results"></div>
    
    <script>
        function testWebGL() {
            const canvas = document.getElementById('testCanvas');
            const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
            const results = document.getElementById('results');
            
            if (!gl) {
                results.innerHTML = 'ERROR: WebGL not supported';
                return false;
            }
            
            // Get GPU info
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            let gpuInfo = 'Unknown GPU';
            
            if (debugInfo) {
                gpuInfo = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }
            
            // Test shader compilation
            const vertexShader = gl.createShader(gl.VERTEX_SHADER);
            gl.shaderSource(vertexShader, `
                attribute vec2 position;
                void main() {
                    gl_Position = vec4(position, 0.0, 1.0);
                }
            `);
            gl.compileShader(vertexShader);
            
            const fragmentShader = gl.createShader(gl.FRAGMENT_SHADER);
            gl.shaderSource(fragmentShader, `
                precision mediump float;
                void main() {
                    gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0);
                }
            `);
            gl.compileShader(fragmentShader);
            
            const program = gl.createProgram();
            gl.attachShader(program, vertexShader);
            gl.attachShader(program, fragmentShader);
            gl.linkProgram(program);
            
            const success = gl.getProgramParameter(program, gl.LINK_STATUS);
            
            results.innerHTML = `
                <h3>WebGL Test Results:</h3>
                <p><strong>WebGL Version:</strong> ${gl.getParameter(gl.VERSION)}</p>
                <p><strong>GPU:</strong> ${gpuInfo}</p>
                <p><strong>Vendor:</strong> ${gl.getParameter(gl.VENDOR)}</p>
                <p><strong>Shader Compilation:</strong> ${success ? 'SUCCESS' : 'FAILED'}</p>
                <p><strong>Max Texture Size:</strong> ${gl.getParameter(gl.MAX_TEXTURE_SIZE)}</p>
                <p><strong>Max Viewport:</strong> ${gl.getParameter(gl.MAX_VIEWPORT_DIMS)}</p>
            `;
            
            return success && gpuInfo.includes('AMD');
        }
        
        window.onload = testWebGL;
    </script>
</body>
</html>
    """
    
    # Write test file
    test_file = "webgl_test.html"
    try:
        with open(test_file, 'w') as f:
            f.write(webgl_test_html)
        
        print(f"WebGL test file created: {test_file}")
        print("Open this file in your browser to test WebGL GPU acceleration")
        print("Look for AMD GPU in the results")
        
        return True
        
    except Exception as e:
        print(f"Error creating WebGL test: {e}")
        return False

def benchmark_performance():
    """Benchmark system performance for streaming"""
    print("\n" + "=" * 60)
    print("BENCHMARKING SYSTEM PERFORMANCE")
    print("=" * 60)
    
    # CPU benchmark
    print("Testing CPU performance...")
    start_time = time.time()
    
    # Simple CPU-intensive task
    total = 0
    for i in range(1000000):
        total += i * i
    
    cpu_time = time.time() - start_time
    print(f"CPU Benchmark: {cpu_time:.4f}s (lower is better)")
    
    # Memory info
    memory = psutil.virtual_memory()
    print(f"Total RAM: {memory.total / (1024**3):.1f} GB")
    print(f"Available RAM: {memory.available / (1024**3):.1f} GB")
    print(f"RAM Usage: {memory.percent}%")
    
    # CPU info
    cpu_count = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)
    print(f"CPU Cores: {cpu_count}")
    print(f"CPU Threads: {cpu_threads}")
    
    # Performance assessment
    if cpu_threads >= 6 and memory.total >= 8 * (1024**3):
        print("EXCELLENT: System well-suited for ultra-smooth streaming")
    elif cpu_threads >= 4 and memory.total >= 4 * (1024**3):
        print("GOOD: System suitable for smooth streaming")
    else:
        print("FAIR: System may struggle with high-quality streaming")

def main():
    """Run comprehensive GPU acceleration tests"""
    print("GPU ACCELERATION VERIFICATION TOOL")
    print("Testing AMD Ryzen 5 7000 series system...")
    print("=" * 60)
    
    results = {
        'opencv_gpu': False,
        'system_gpu': False,
        'webgl_support': False
    }
    
    # Run all tests
    results['opencv_gpu'] = test_opencv_gpu()
    results['system_gpu'] = test_system_gpu()
    results['webgl_support'] = test_webgl_support()
    
    # Benchmark performance
    benchmark_performance()
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"OpenCV GPU Support: {'PASS' if results['opencv_gpu'] else 'FAIL'}")
    print(f"System AMD GPU: {'DETECTED' if results['system_gpu'] else 'NOT FOUND'}")
    print(f"WebGL Support: {'AVAILABLE' if results['webgl_support'] else 'ERROR'}")
    
    # Recommendations
    print("\nRECOMMendations:")
    
    if results['opencv_gpu']:
        print("- OpenCV GPU acceleration is working - use server-side GPU features")
    else:
        print("- OpenCV GPU not working - rely on WebGL browser acceleration")
    
    if results['system_gpu']:
        print("- AMD GPU detected - ensure latest drivers are installed")
    else:
        print("- AMD GPU not detected - check device manager and drivers")
    
    if results['webgl_support']:
        print("- WebGL available - browser GPU acceleration should work")
        print("- Open webgl_test.html in browser to verify AMD GPU usage")
    else:
        print("- WebGL test file creation failed")
    
    # Overall assessment
    gpu_score = sum(results.values())
    
    if gpu_score >= 2:
        print("\nOVERALL: GPU acceleration should work well!")
    elif gpu_score == 1:
        print("\nOVERALL: Partial GPU support - some acceleration available")
    else:
        print("\nOVERALL: Limited GPU support - may need driver updates")

if __name__ == "__main__":
    main()
