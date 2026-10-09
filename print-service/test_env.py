#!/usr/bin/env python3
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/opt/print-service')

print("Testing print service setup...")
print(f"Python: {sys.version}")
print(f"Working directory: {os.getcwd()}")

try:
    # Test basic imports
    from app.config import config
    print(f"✓ Config loaded: PORT={config.PORT}, DEBUG={config.DEBUG}")
    
    # Test PIL/Pillow
    from PIL import Image, ImageDraw, ImageFont
    print("✓ PIL/Pillow imported")
    
    # Create test image
    test_img = Image.new('RGB', (100, 50), 'white')
    draw = ImageDraw.Draw(test_img)
    draw.text((10, 10), "Test", fill='black')
    print("✓ Test image created")
    
    # Test brother_ql
    import brother_ql
    from brother_ql.raster import BrotherQLRaster
    print("✓ brother_ql imported")
    
    # Test barcode library
    import barcode
    print("✓ barcode library imported")
    
    # Test qrcode library
    import qrcode
    print("✓ qrcode library imported")
    
    print("\n✅ All dependencies are properly installed!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Try: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
