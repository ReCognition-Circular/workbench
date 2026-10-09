#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/opt/print-service')

try:
    print("Testing Flask application startup...")
    
    # Import the app
    from app.main import app
    
    print("✓ Flask app imported successfully")
    
    # Test configuration
    from app.config import config
    print(f"✓ Config: HOST={config.HOST}, PORT={config.PORT}, DEBUG={config.DEBUG}")
    
    # Test that all routes are registered
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(rule.rule)
    
    print(f"✓ Routes registered: {len(routes)}")
    for route in sorted(routes):
        print(f"  - {route}")
    
    print("\n✅ Flask application test passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
