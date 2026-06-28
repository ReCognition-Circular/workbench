import json
import logging
import re

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from devices.models import Recipient, FulfilmentRequest
from integrations.models import IntegrationLog

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def sales_order_webhook(request):
    """Receive Sales Order from ERPNext, create/update FulfilmentRequest."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        doc = data.get("doc", data)

        customer_name = doc.get("customer_name", "")
        if not customer_name:
            return JsonResponse({"error": "customer_name is required"}, status=400)

        recipient, created = Recipient.objects.get_or_create(
            name=customer_name,
            defaults={"recipient_type": "BUSINESS"},
        )

        items = doc.get("items", [])
        if not items:
            return JsonResponse({"error": "order has no items"}, status=400)

        item = items[0]
        item_code = item.get("item_code", "")
        qty = item.get("qty", 0)
        description = item.get("description", "")

        spec_requirements = {}
        if description:
            clean_desc = re.sub(r'<[^>]+>', '', description).strip()
            try:
                spec_requirements = json.loads(clean_desc)
            except json.JSONDecodeError:
                spec_requirements = {"description": clean_desc}

        order_id = doc.get("name", "")
        if not order_id:
            return JsonResponse({"error": "order has no name"}, status=400)

        fr, fr_created = FulfilmentRequest.objects.update_or_create(
            erpnext_order_id=order_id,
            defaults={
                "recipient": recipient,
                "item_code": item_code,
                "quantity": qty,
                "summary": (description or f"{qty} x {item_code} for {customer_name}")[:200],
                "requested_spec": spec_requirements,
                "status": "PENDING",
            },
        )

        IntegrationLog.objects.create(
            direction="INBOUND",
            doctype="Sales Order",
            doc_name=order_id,
            action="webhook_received",
            status="SUCCESS",
            completed_at=timezone.now(),
        )

        return JsonResponse({
            "status": "ok",
            "fulfilment_request_id": fr.id,
            "created": fr_created,
        })

    except Exception as e:
        logger.exception("Webhook error")
        IntegrationLog.objects.create(
            direction="INBOUND",
            doctype="Sales Order",
            doc_name=data.get("doc", data).get("name", "unknown"),
            action="webhook_received",
            status="FAILED",
            error_message=str(e),
            completed_at=timezone.now(),
        )
        return JsonResponse({"error": str(e)}, status=500)
