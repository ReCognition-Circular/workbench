import os
import logging
import tempfile
from PIL import Image, ImageDraw, ImageFont
import qrcode
import barcode
from barcode.writer import ImageWriter

from .config import config

logger = logging.getLogger(__name__)

class LabelGenerator:
    def __init__(self):
        self.font = self._load_font()
        # 29x90mm label dimensions
        self.label_width = 306   # pixels for 29mm
        self.label_height = 991  # pixels for 90mm
        
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
    
    def create_simple_label(self, text_lines, width=None, height=None):
        """Create a simple text label"""
        if width is None:
            width = self.label_width
        if height is None:
            height = self.label_height
            
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Draw text lines
        y_position = 20
        line_height = 30
        
        for line in text_lines:
            if line:  # Skip empty lines
                draw.text((20, y_position), line, fill='black', font=self.font)
                y_position += line_height
        
        return img
    
    def generate_barcode(self, data, barcode_type='code128'):
        """Generate a barcode image"""
        try:
            # Create barcode
            barcode_class = barcode.get_barcode_class(barcode_type)
            barcode_image = barcode_class(data, writer=ImageWriter())
            
            # Use tempfile for safe temporary file handling
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                temp_path = tmp.name
            
            try:
                barcode_image.save(temp_path)
                
                # Load and resize for 29mm label (approx 250px wide)
                img = Image.open(temp_path)
                img = img.resize((250, 100))  # Adjusted for 29mm label
                
                return img
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Failed to generate barcode: {e}")
            # Fallback to text representation
            return self._create_barcode_fallback(data)
    
    def _create_barcode_fallback(self, data):
        """Create a simple barcode-like representation"""
        width = 250
        height = 80
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Draw barcode text
        draw.text((10, 10), f"CODE: {data}", fill='black', font=self.font)
        
        # Draw simple bars
        bar_width = 3
        x = 10
        for char in data:
            bar_height = (ord(char) % 40) + 30
            draw.rectangle([x, 30, x + bar_width, 30 + bar_height], fill='black')
            x += bar_width + 1
        
        return img
    
    def generate_qrcode(self, data, size=100):
        """Generate a QR code image"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.resize((size, size))
            
            return qr_img
            
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            return self._create_qrcode_fallback(data)
    
    def _create_qrcode_fallback(self, data):
        """Create a simple QR code fallback"""
        size = 100
        img = Image.new('RGB', (size, size), 'white')
        draw = ImageDraw.Draw(img)
        
        draw.text((10, 10), "QR", fill='black', font=self.font)
        draw.text((10, 40), data[:15], fill='black', font=self.font)
        
        return img
    
    def create_asset_label(self, inventory_number, serial_number=None):
        """Create a complete asset label with barcode"""
        # Create text content
        lines = [f"INV: {inventory_number}"]
        if serial_number:
            lines.append(f"S/N: {serial_number}")
        
        # Generate barcode
        barcode_img = self.generate_barcode(inventory_number)
        
        # Create main label area (top portion)
        label_img = self.create_simple_label(lines, width=self.label_width, height=150)
        
        # Combine barcode with label
        combined = Image.new('RGB', (self.label_width, self.label_height), 'white')
        combined.paste(label_img, (0, 20))
        combined.paste(barcode_img, (28, 120))  # Center barcode (306-250)/2 = 28
        
        return combined
    
    def create_location_label(self, location_code, description=None):
        """Create a location label"""
        lines = [f"LOC: {location_code}"]
        if description:
            lines.append(description)
        
        # Generate barcode for location
        barcode_img = self.generate_barcode(location_code)
        
        # Create combined label
        label_img = self.create_simple_label(lines, width=self.label_width, height=150)
        combined = Image.new('RGB', (self.label_width, self.label_height), 'white')
        combined.paste(label_img, (0, 20))
        combined.paste(barcode_img, (28, 120))
        
        return combined
    
    def create_postage_label(self, recipient_name, address_line_1, 
                           address_line_2, city, postcode, tracking_reference=None):
        """Create a postage/shipping label"""
        lines = [
            f"TO: {recipient_name}",
            address_line_1,
            address_line_2 if address_line_2 else "",
            f"{city} {postcode}",
        ]
        
        if tracking_reference:
            lines.append(f"TRACK: {tracking_reference}")
            # Add QR code for tracking
            qr_img = self.generate_qrcode(tracking_reference, size=80)
        
        # Filter out empty lines
        lines = [line for line in lines if line]
        
        # Create label
        label_img = self.create_simple_label(lines, width=self.label_width, height=200)
        
        if tracking_reference:
            # Add QR code to label
            combined = Image.new('RGB', (self.label_width, self.label_height), 'white')
            combined.paste(label_img, (0, 20))
            combined.paste(qr_img, (113, 250))  # Center QR (306-80)/2 = 113
            return combined
        
        return label_img

# Global label generator instance
label_generator = LabelGenerator()
