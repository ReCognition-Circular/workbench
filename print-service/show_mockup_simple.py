#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/print-service')

from app.label_generator import LabelGenerator
from PIL import Image, ImageDraw
import os

print("Creating label mockup for 29x90mm label...")

# Create label generator
generator = LabelGenerator()

# Create a test label
label = generator.create_asset_label("INV-12040051", "SN-ABC123XYZ")

print(f"Label dimensions: {label.size} pixels (29x90mm)")
print(f"Label mode: {label.mode}")

# Save the image
output_path = "/tmp/label_mockup.png"
label.save(output_path)
print(f"Label saved to {output_path}")

# Show file info
file_size = os.path.getsize(output_path)
print(f"File size: {file_size / 1024:.1f} KB")

# Create a text representation of the layout
print("\n=== LABEL LAYOUT ===")
print(f"Total: {label.width} x {label.height} pixels")
print(f"Physical: 29mm x 90mm")
print(f"Resolution: {label.width/29:.1f} x {label.height/90:.1f} pixels/mm")
print()

# Analyze the image
pixels = list(label.getdata())
white = sum(1 for p in pixels if p == (255, 255, 255))
black = sum(1 for p in pixels if p == (0, 0, 0))
other = len(pixels) - white - black

print(f"Pixel analysis:")
print(f"  White pixels: {white:,} ({white/len(pixels)*100:.1f}%)")
print(f"  Black pixels: {black:,} ({black/len(pixels)*100:.1f}%)")
print(f"  Other colors: {other:,} ({other/len(pixels)*100:.1f}%)")

# Create a simple grid representation
print("\nSimplified layout (each char = ~30x30 pixels):")
width, height = label.size
grid_width = 10
grid_height = 30
cell_w = width // grid_width
cell_h = height // grid_height

# Sample pixels in a grid
for gy in range(grid_height):
    line = ""
    for gx in range(grid_width):
        # Sample center of cell
        x = gx * cell_w + cell_w // 2
        y = gy * cell_h + cell_h // 2
        
        if x < width and y < height:
            pixel = label.getpixel((x, y))
            # Check if pixel is dark (text/barcode)
            if sum(pixel) < 384:  # Dark if sum < 384 (3*128)
                line += "█"
            else:
                line += " "
        else:
            line += " "
    print(line)

print("\nLegend:")
print("█ = Text, barcode, or border")
print("  = White background")
print(f"\nEach character represents ~{cell_w}x{cell_h} pixels")

print("\n=== SUGGESTED IMPROVEMENTS ===")
print("1. Text size: Current font may be too small")
print("2. Barcode size: Should fill more width")
print("3. Layout: More spacing between elements")
print("4. Borders: Consider thinner borders")

print(f"\nTo view the actual image:")
print(f"1. Download: scp recog@workbench:{output_path} .")
print(f"2. Or check if you have an image viewer on the server")
