import os
import logging
from PIL import Image, ImageDraw, ImageFont
import qrcode

from .config import config

logger = logging.getLogger(__name__)

class SimpleLabelGenerator:
    def __init__(self):
        self.font = self._load_font()
        
    def _load_font(self):
        """Load font with fallback options"""
        font_paths = [
            config.FONT_PATH,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf',
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, config.FONT_SIZE)
                    logger.info(f"Loaded font: {font_path}")
                    return font
                except Exception as e:
                    logger.warning(f"Failed to load font {font_path}: {e}")
        
        logger.warning("Using default font")
        return ImageFont.load_default()
    
    def create_simple_label(self, text_lines, width=696, height=200):
        """Create a simple text label"""
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Draw text lines
        y_position = 10
        line_height = 30
        
        for line in text_lines:
            if line:  # Skip empty lines
                draw.text((10, y_position), line, fill='black', font=self.font)
                y_position += line_height
        
        return img
    
    def create_text_barcode(self, data, width=600, height=100):
        """Create a simple text-based barcode representation"""
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Draw barcode text
        draw.text((10, 10), f"CODE: {data}", fill='black', font=self.font)
        
        # Draw simple bars based on data
        bar_width = 3
        x = 10
        for char in data:
            # Create visual representation from character code
            bar_height = (ord(char) % 40) + 30
            draw.rectangle([x, 40, x + bar_width, 40 + bar_height], fill='black')
            x += bar_width + 1
        
        # Draw the data again at bottom
        draw.text((10, 70), data, fill='black', font=self.font)
        
        return img
    
    def generate_qrcode(self, data, size=150):
        """Generate a QR code image"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.resize((size, size))
            
            return qr_img
            
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            # Fallback
            img = Image.new('RGB', (size, size), 'white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "QR", fill='black', font=self.font)
            draw.text((10, 50), data[:20], fill='black', font=self.font)
            return img
    
    def create_asset_label(self, inventory_number, serial_number=None):
        """Create a complete asset label"""
        # Create text content
        lines = [f"INV: {inventory_number}"]
        if serial_number:
            lines.append(f"S/N: {serial_number}")
        
        # Generate simple barcode
        barcode_img = self.create_text_barcode(inventory_number)
        
        # Create main label
        label_img = self.create_simple_label(lines, width=696, height=150)
        
        # Combine barcode with label
        combined = Image.new('RGB', (696, 300), 'white')
        combined.paste(label_img, (0, 0))
        combined.paste(barcode_img, (48, 120))  # Position barcode
        
        return combined

# Global simple label generator instance
simple_label_generator = SimpleLabelGenerator()
