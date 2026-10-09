#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

import tempfile
import barcode
from barcode.writer import ImageWriter
from PIL import Image

print("Testing barcode generation directly...")

try:
    # Test with code128 barcode
    barcode_class = barcode.get_barcode_class('code128')
    print(f"Barcode class: {barcode_class}")
    
    # Create barcode
    barcode_image = barcode_class('TEST123', writer=ImageWriter())
    print(f"Barcode image created: {barcode_image}")
    
    # Save to file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        temp_path = tmp.name
    
    print(f"Saving to: {temp_path}")
    barcode_image.save(temp_path)
    
    # Try to open it
    img = Image.open(temp_path)
    print(f"Image opened successfully: {img.size}, {img.mode}")
    
    import os
    os.unlink(temp_path)
    print("✓ Barcode generation test passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
