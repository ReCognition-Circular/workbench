#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

import requests
import json
from PIL import Image, ImageDraw
import base64
import io
import time

def test_service():
    base_url = "http://localhost:5000"
    
    print("=== Testing Print Service v2 ===")
    
    # Test 1: Health endpoint
    print("\n1. Testing /health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   Response: {json.dumps(health_data, indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Failed: {e}")
    
    # Test 2: Test print endpoint
    print("\n2. Testing /print/test endpoint...")
    try:
        response = requests.get(f"{base_url}/print/test", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
            print("   ✓ Test label should be printing now...")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Failed: {e}")
    
    # Wait for print to complete
    time.sleep(5)
    
    # Test 3: Create and send a base64 image
    print("\n3. Testing /print/image with base64...")
    
    # Create a simple test image
    img = Image.new('RGB', (306, 991), 'white')
    draw = ImageDraw.Draw(img)
    
    # Draw test content
    draw.rectangle([10, 10, 296, 981], outline='black', width=2)
    draw.text((50, 50), "BASE64 TEST", fill='black')
    draw.text((50, 100), "From Python Script", fill='black')
    draw.text((50, 150), "29x90mm Label", fill='black')
    
    # Simple barcode
    x = 50
    for i, char in enumerate("TEST123"):
        bar_height = 80 + (ord(char) % 40)
        draw.rectangle([x, 250, x + 6, 250 + bar_height], fill='black')
        x += 8
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    print(f"   Image size: {img.size}")
    print(f"   Base64 length: {len(img_base64)} chars")
    
    # Send to print service
    payload = {
        "image_base64": img_base64,
        "printer_model": "QL-700"
    }
    
    try:
        response = requests.post(
            f"{base_url}/print/image",
            json=payload,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
            print("   ✓ Base64 image should be printing now...")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Failed: {e}")
    
    print("\n=== Test Complete ===")
    print("Check the printer for:")
    print("1. Test label from /print/test")
    print("2. Base64 test label")

if __name__ == "__main__":
    # Start the service in background
    import subprocess
    import os
    import signal
    
    print("Starting print service...")
    
    # Change to app directory
    os.chdir('/opt/print-service')
    
    # Start Flask
    flask_proc = subprocess.Popen(
        ["python3", "-m", "app.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    
    # Wait for service to start
    time.sleep(3)
    
    try:
        # Run tests
        test_service()
        
        # Wait for prints
        time.sleep(5)
        
    finally:
        # Kill Flask
        print("\nStopping print service...")
        os.killpg(os.getpgid(flask_proc.pid), signal.SIGTERM)
        flask_proc.wait()
