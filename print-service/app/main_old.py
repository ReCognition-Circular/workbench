import os
import logging
from flask import Flask, request, jsonify

from .config import config
from .printer import printer_service
from .label_generator import label_generator

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "print-service",
        "version": "1.0.0"
    }), 200

@app.route('/print/asset-label', methods=['POST'])
def print_asset():
    """Print asset barcode label"""
    try:
        data = request.json
        if not data or 'inventory_number' not in data:
            return jsonify({"error": "inventory_number required"}), 400
        
        inventory_number = data['inventory_number']
        serial_number = data.get('serial_number')
        
        logger.info(f"Printing asset label for: {inventory_number}")
        
        # Generate label image
        label_image = label_generator.create_asset_label(
            inventory_number, 
            serial_number
        )
        
        # Print the label
        success = printer_service.print_image(
            label_image, 
            config.PRINTER_MODEL_ASSET
        )
        
        if success:
            return jsonify({
                "status": "printed",
                "inventory_number": inventory_number,
                "serial_number": serial_number
            }), 200
        else:
            return jsonify({"error": "print failed"}), 500
            
    except Exception as e:
        logger.error(f"Asset label print error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/print/postage-label', methods=['POST'])
def print_postage():
    """Print postage/shipping label"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        # Validate required fields
        required_fields = ['recipient_name', 'address_line_1', 'city', 'postcode']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} required"}), 400
        
        logger.info(f"Printing postage label for: {data['recipient_name']}")
        
        # Generate label image
        label_image = label_generator.create_postage_label(
            data['recipient_name'],
            data['address_line_1'],
            data.get('address_line_2'),
            data['city'],
            data['postcode'],
            data.get('tracking_reference')
        )
        
        # Print the label
        success = printer_service.print_image(
            label_image, 
            config.PRINTER_MODEL_POSTAGE
        )
        
        if success:
            return jsonify({
                "status": "printed",
                "recipient": data['recipient_name']
            }), 200
        else:
            return jsonify({"error": "print failed"}), 500
            
    except Exception as e:
        logger.error(f"Postage label print error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/print/location-label', methods=['POST'])
def print_location():
    """Print location barcode label"""
    try:
        data = request.json
        if not data or 'location_code' not in data:
            return jsonify({"error": "location_code required"}), 400
        
        location_code = data['location_code']
        description = data.get('description')
        
        logger.info(f"Printing location label: {location_code}")
        
        # Generate label image
        label_image = label_generator.create_location_label(
            location_code, 
            description
        )
        
        # Print the label
        success = printer_service.print_image(
            label_image, 
            config.PRINTER_MODEL_ASSET
        )
        
        if success:
            return jsonify({
                "status": "printed",
                "location_code": location_code,
                "description": description
            }), 200
        else:
            return jsonify({"error": "print failed"}), 500
            
    except Exception as e:
        logger.error(f"Location label print error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test/print', methods=['GET'])
def test_print():
    """Test endpoint to verify printing works"""
    try:
        # Create a simple test label
        from PIL import Image, ImageDraw
        test_img = Image.new('RGB', (696, 100), 'white')
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 10), "TEST PRINT - ReCognition Circular", fill='black')
        draw.text((10, 40), "If you can read this, printing works!", fill='black')
        
        # Try to print
        success = printer_service.print_image(test_img)
        
        if success:
            return jsonify({"status": "test_print_successful"}), 200
        else:
            return jsonify({"error": "test_print_failed"}), 500
            
    except Exception as e:
        logger.error(f"Test print error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting print service on {config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
