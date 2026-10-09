import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    """Application configuration"""
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    PORT: int = int(os.getenv('PORT', '5000'))
    HOST: str = os.getenv('HOST', '0.0.0.0')
    
    # Printer settings - UPDATED for 29x90mm labels
    PRINTER_MODEL_ASSET: str = os.getenv('PRINTER_MODEL_ASSET', 'QL-700')
    PRINTER_MODEL_POSTAGE: str = os.getenv('PRINTER_MODEL_POSTAGE', 'QL-1100')
    LABEL_SIZE: str = os.getenv('LABEL_SIZE', '29x90')  # CHANGED: 29x90mm die-cut labels
    CUT_AFTER_PRINT: bool = os.getenv('CUT_AFTER_PRINT', 'True').lower() == 'true'
    
    # Font settings
    FONT_PATH: str = os.getenv('FONT_PATH', '/app/fonts/DejaVuSans.ttf')
    FONT_SIZE: int = int(os.getenv('FONT_SIZE', '24'))
    
    # USB device paths to check - using default_factory for mutable list
    USB_DEVICE_PATHS: List[str] = field(default_factory=lambda: [
        '/dev/usb/lp0',
        '/dev/usb/lp1',
        '/dev/bus/usb/002/006',  # QL-700
        '/dev/bus/usb/002/007',  # QL-1100
    ])

config = Config()
