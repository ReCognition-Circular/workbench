#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

import requests
import json
import time

def main():
    print("Testing Print Service...")
    
    # Start the service
    import subprocess
    import os
    
    print("1. Starting Flask service...")
    flask_proc = subprocess.Popen(
        ["python3", "-m", "app.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for startup
    time.sleep(3)
    
    base_url = "http://localhost:5000"
    
    try:
        # Test health endpoint
        print("\n2. Testing /health...")
        resp = requests.get(f"{base_url}/health", timeout=5)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print("   ✓ Health endpoint works")
            print(f"   Service: {resp.json().get('service')}")
            print(f"   Version: {resp.json().get('version')}")
        else:
            print(f"   ✗ Failed: {resp.text}")
            return
        
        # Test print test endpoint
        print("\n3. Testing /print/test...")
        resp = requests.get(f"{base_url}/print/test", timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print("   ✓ Test print endpoint works")
            print(f"   Response: {resp.json()}")
            print("   A test label should be printing now...")
        else:
            print(f"   ✗ Failed: {resp.text}")
        
        # Wait for print
        time.sleep(5)
        
        print("\n4. Service test complete!")
        print("Check the printer for the test label.")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop Flask
        print("\n5. Stopping Flask service...")
        flask_proc.terminate()
        flask_proc.wait()

if __name__ == "__main__":
    main()
