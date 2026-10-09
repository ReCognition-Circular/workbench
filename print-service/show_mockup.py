#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

from app.label_generator import LabelGenerator
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import numpy as np

print("Creating label mockup for 29x90mm label...")

# Create label generator
generator = LabelGenerator()

# Create a test label
label = generator.create_asset_label("INV-12040051", "SN-ABC123XYZ")

print(f"Label dimensions: {label.size} pixels")
print(f"Label mode: {label.mode}")

# Save the image
label.save("/tmp/label_mockup.png")
print("Label saved to /tmp/label_mockup.png")

# Try to display it if we have display
try:
    # Show image dimensions
    print(f"\nLabel layout:")
    print(f"Total size: {label.width} x {label.height} pixels")
    print(f"Physical size: 29mm x 90mm")
    print(f"Resolution: {label.width/29:.1f} x {label.height/90:.1f} pixels/mm")
    
    # Create a simple ASCII representation
    print("\nSimple ASCII representation (scaled down):")
    width, height = label.size
    scale = 20  # Scale down for ASCII
    
    # Convert to grayscale and get pixel values
    gray = label.convert('L')
    pixels = list(gray.getdata())
    
    # Create ASCII art
    ascii_chars = "@%#*+=-:. "
    
    for y in range(0, height, scale):
        line = ""
        for x in range(0, width, scale):
            idx = y * width + x
            if idx < len(pixels):
                brightness = pixels[idx]
                char_idx = min(int(brightness / 25.6), 9)  # 0-9
                line += ascii_chars[char_idx]
            else:
                line += " "
        print(line)
    
    print("\nLegend:")
    print("@ = Darkest (text, barcode)")
    print(". = Light")
    print("  = White")
    
except Exception as e:
    print(f"Could not create visual display: {e}")
    print("Check /tmp/label_mockup.png for the actual image")

print("\nTo view the image, you can:")
print("1. scp it to your local machine: scp recog@workbench:/tmp/label_mockup.png .")
print("2. Or use an image viewer if available on the server")
