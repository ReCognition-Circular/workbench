import logging
from datetime import date

from django.utils import timezone

from integrations.erpnext_client import ERPNextClient, ERPNextClientError
from integrations.models import IntegrationLog

logger = logging.getLogger(__name__)


def create_stock_entry(device):
    """
    Create a Stock Entry (Material Receipt) in ERPNext for a device at intake.
    
    This creates the Serial No in ERPNext with warehouse assignment.
    Returns the Stock Entry name on success, raises on failure.
    """
    client = ERPNextClient()
    inventory_number = device.inventory_number
    posting_date = device.created_at.strftime("%Y-%m-%d") if device.created_at else date.today().isoformat()

    payload = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": "ReCognition Circular CIC",
        "to_warehouse": "Stores - RCC",
        "items": [
            {
                "item_code": "LAPTOP-UNSPECIFIED",
                "qty": 1,
                "serial_no": inventory_number,
                "t_warehouse": "Stores - RCC",
                "basic_rate": 0,
                "allow_zero_valuation_rate": 1,
            }
        ],
        "posting_date": posting_date,
    }

    log = IntegrationLog.objects.create(
        direction="OUTBOUND",
        doctype="Stock Entry",
        action="create_stock_entry",
        request_payload=payload,
        status="PENDING",
    )

    try:
        # Step 1: Create the Stock Entry (Draft)
        resp = client.create("Stock Entry", payload)
        doc_name = resp.get("data", {}).get("name")

        # Step 2: Submit it
        doc = client.get("Stock Entry", doc_name)
        submit_resp = client._request("POST", "/api/method/frappe.client.submit", json={"doc": doc["data"]})

        # Update log
        log.doc_name = doc_name
        log.response_code = 200
        log.response_body = str(submit_resp)
        log.status = "SUCCESS"
        log.completed_at = timezone.now()
        log.save()

        # Store the Stock Entry name on the device
        device.erpnext_stock_entry = doc_name
        device.save(update_fields=["erpnext_stock_entry"])

        logger.info(f"Stock Entry {doc_name} created and submitted for device {inventory_number}")
        return doc_name

    except ERPNextClientError as e:
        log.status = "FAILED"
        log.response_body = str(e)
        log.completed_at = timezone.now()
        log.save()
        logger.error(f"Failed to create Stock Entry for device {inventory_number}: {e}")
        raise
