#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

from app.label_generator_simple import simple_label_generator
from PIL import Image

print("Testing simple label generator...")

try:
    # Generate a simple label
    label = simple_label_generator.create_asset_label("TEST123", "SN456")
    print(f"✓ Label created: {label.size}")
    
    # Save it to see what it looks like
    label.save("/tmp/test_label.png")
    print("✓ Label saved to /tmp/test_label.png")
    
    print("\n✅ Simple label generation works!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
