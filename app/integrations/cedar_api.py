import logging
from datetime import timedelta
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils import timezone

from integrations.models import CedarAuthToken

logger = logging.getLogger(__name__)

CEDAR_BASE = getattr(settings, 'CEDAR_API_BASE', 'https://portal.cedar-enterprise.com/api/v1')
TOKEN_BUFFER_DAYS = 3  # refresh if expiring within 3 days


class CedarAPIError(Exception):
    """Raised when the Cedar API returns an error."""
    pass


def _get_or_refresh_token():
    """
    Return a valid bearer token.
    Reuses existing token if not near expiry; otherwise authenticates and upserts.
    """
    try:
        obj = CedarAuthToken.objects.latest('refreshed_at')
        if obj.expires_at > timezone.now() + timedelta(days=TOKEN_BUFFER_DAYS):
            return obj.token
        logger.info("Cedar token near expiry — re-authenticating")
    except CedarAuthToken.DoesNotExist:
        logger.info("No Cedar token found — authenticating")

    resp = requests.post(
        CEDAR_BASE.rstrip('/') + '/authenticate/client',
        json={
            'cloud_code': settings.CEDAR_CLOUD_CODE,
            'cloud_pass': settings.CEDAR_CLOUD_PASS,
        },
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        timeout=30,
    )

    if resp.status_code != 200:
        raise CedarAPIError(f"Auth failed: {resp.status_code} — {resp.text}")

    data = resp.json()
    token = data['token']

    CedarAuthToken.objects.update_or_create(
        pk=1,
        defaults={
            'token': token,
            'expires_at': timezone.now() + timedelta(days=27),
        },
    )
    logger.info("Cedar token refreshed successfully")
    return token


def _cedar_get(endpoint, params=None):
    """Make an authenticated GET request to the Cedar API."""
    token = _get_or_refresh_token()
    url = CEDAR_BASE.rstrip('/') + '/' + endpoint.lstrip('/')
    resp = requests.get(
        url,
        params=params or {},
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise CedarAPIError(f"Cedar {endpoint} returned {resp.status_code}: {resp.text}")
    return resp.json()


def search_erasure_certificates(drive_serial):
    """
    Search Cedar for erasure certificates matching a drive serial.
    Returns the JSON response data.
    """
    return _cedar_get('/search-erasure-certificates', {
        'serial_number': drive_serial,
        'metadata': 'true',
    })


def search_asset_certificates(drive_serial):
    """
    Search Cedar for asset (audit) certificates matching a drive serial.
    Returns the JSON response data.
    """
    return _cedar_get('/search-asset-certificates', {
        'serial_number': drive_serial,
        'metadata': 'true',
    })
def search_asset_certificates_by_serials(serials):
    """
    Search Cedar for asset (audit) certificates matching any of the given
    serial variants. Uses the comma-separated `serial_numbers` filter so
    raw + normalised serials are covered in a single request.
    """
    cleaned = [s.strip() for s in serials if s and str(s).strip()]
    if not cleaned:
        return {"certificates": {"data": []}}
    return _cedar_get('/search-asset-certificates', {
        'serial_numbers': ','.join(cleaned),
        'metadata': 'true',
    })    
