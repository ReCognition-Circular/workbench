import os, logging, io, urllib.request
from flask import Flask, request, jsonify, render_template
from PIL import Image, ImageDraw, ImageFont, ImageChops
from pdf2image import convert_from_bytes

from .config import config
from .printer import printer_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

LABEL_W, LABEL_H = 306, 991

def get_font(size=48):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()

def fetch_barcode(data):
    url = f"https://barcode.tec-it.com/barcode.ashx?data={data}&code=Code128&translate-esc=true&dpi=96&imagetype=png"
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        return Image.open(io.BytesIO(resp.read()))
    except Exception as e:
        logger.error(f"Barcode API failed: {e}")
        return None

def make_label(inv_num, model_name=""):
    img = Image.new('RGB', (LABEL_W, LABEL_H), 'white')
    draw = ImageDraw.Draw(img)
    font = get_font(48)
    draw.rectangle([5, 5, LABEL_W-5, LABEL_H-5], outline='black', width=4)
    display_text = model_name if model_name else inv_num
    txt = Image.new('RGB', (280, 60), 'white')
    d = ImageDraw.Draw(txt)
    d.text((0, 0), display_text, fill='black', font=font)
    txt_r = txt.rotate(90, expand=True)
    img.paste(txt_r, (15, 30))
    bc = fetch_barcode(inv_num)
    if bc:
        bc = bc.rotate(90, expand=True)
        target_w = 170
        aspect = bc.height / bc.width
        target_h = int(target_w * aspect)
        if target_h > 750:
            target_h = 750
        bc = bc.resize((target_w, target_h), Image.Resampling.LANCZOS)
        if bc.mode != 'RGB':
            bc = bc.convert('RGB')
        img.paste(bc, (100, (LABEL_H - target_h) // 2))
    else:
        for i in range(20):
            y = 200 + i * 35
            draw.rectangle([90, y, 270, y + 18], fill='black')
    return img

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/print/label', methods=['POST'])
def print_label():
    try:
        d = request.json or {}
        inv = d.get('inventory_number', '')
        model = d.get('model_name', '')
        if not inv:
            return jsonify({"error": "inventory_number required"}), 400
        logger.info(f"Printing: {inv} / model: {model}")
        img = make_label(inv, model)
        ok = printer_service.print_image(img, printer_model='QL-700')
        return jsonify({"status": "printed" if ok else "failed"}), (200 if ok else 500)
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/print/postage', methods=['POST'])
def print_postage():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        f = request.files['file']
        file_bytes = f.read()
        
        # 1. Convert PDF or open image
        if file_bytes.startswith(b'%PDF'):
            pages = convert_from_bytes(file_bytes, dpi=300)
            img = pages[0]
        else:
            img = Image.open(io.BytesIO(file_bytes))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # 2. Auto-crop the whitespace to enlarge the actual label
        bg = Image.new(img.mode, img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)
            
        # 3. Smart Rotation: force portrait orientation so it fills the tall label perfectly
        if img.width > img.height:
            img = img.rotate(90, expand=True)
            
        # 4. Resize proportionally (maintains aspect ratio)
        img.thumbnail((1200, 1822), Image.Resampling.LANCZOS)
        
        # 5. Paste onto a perfect 1200x1822 white background
        final_img = Image.new('RGB', (1200, 1822), 'white')
        offset_x = (1200 - img.width) // 2
        offset_y = (1822 - img.height) // 2
        final_img.paste(img, (offset_x, offset_y))
        img = final_img
        
        logger.info(f"Printing postage label, final size: {img.size}")
        ok = printer_service.print_image(img, printer_model='QL-1100')
        return jsonify({"status": "printed" if ok else "failed"}), (200 if ok else 500)
    except Exception as e:
        logger.error(f"Postage error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/print/test', methods=['GET'])
def test():
    img = make_label("TEST-001", "EliteBook 840 G3")
    ok = printer_service.print_image(img, printer_model='QL-700')
    return jsonify({"status": "printed" if ok else "failed"}), (200 if ok else 500)
