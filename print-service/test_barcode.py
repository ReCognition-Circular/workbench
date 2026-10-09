#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

try:
    from app.label_generator import LabelGenerator
    
    print("Testing barcode generation...")
    generator = LabelGenerator()
    
    # Test creating a simple label
    img = generator.create_simple_label(["Test Label", "INV: 12345"])
    print(f"✓ Simple label created: {img.size}")
    
    # Try to generate a barcode
    barcode_img = generator.generate_barcode("12345")
    print(f"✓ Barcode generated: {barcode_img.size}")
    
    # Try to generate a QR code
    qr_img = generator.generate_qrcode("https://example.com")
    print(f"✓ QR code generated: {qr_img.size}")
    
    print("\n✅ All label generation tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
