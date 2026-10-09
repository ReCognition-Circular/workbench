import os
import logging
import usb.core
import usb.util
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory
from PIL import Image

from .config import config

logger = logging.getLogger(__name__)

PRINTER_IDS = {
    'QL-700':  {'vid': 0x04f9, 'pid': 0x2042},
    'QL-1100': {'vid': 0x04f9, 'pid': 0x20a7},
}

class PrinterService:
    def __init__(self):
        self.device_paths = {}

    def find_printer_pyusb(self, printer_model):
        ids = PRINTER_IDS.get(printer_model)
        if not ids:
            logger.error(f"Unknown printer model: {printer_model}")
            return None
        dev = usb.core.find(idVendor=ids['vid'], idProduct=ids['pid'])
        if dev is None:
            logger.error(f"{printer_model} not found via USB")
            return None
        logger.info(f"Found {printer_model} via USB: {ids['vid']:04x}:{ids['pid']:04x}")
        return dev

    def print_image(self, image: Image.Image, printer_model: str = None):
        try:
            if not printer_model:
                printer_model = config.PRINTER_MODEL_ASSET

            dev = self.find_printer_pyusb(printer_model)
            if dev is None:
                raise RuntimeError(f"{printer_model} not found")

            usb_id = f"usb://0x{dev.idVendor:04x}:0x{dev.idProduct:04x}"
            logger.info(f"Printing to {printer_model} via {usb_id}")

            qlr = BrotherQLRaster(printer_model)
            label_size = '103x164' if printer_model == 'QL-1100' else config.LABEL_SIZE

            convert(
                qlr=qlr,
                images=[image],
                label=label_size,
                cut=config.CUT_AFTER_PRINT,
            )

            be = backend_factory('pyusb')
            printer = be['backend_class'](usb_id)
            printer.write(qlr.data)

            logger.info("Print successful")
            return True

        except Exception as e:
            logger.error(f"Print failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

printer_service = PrinterService()
