import json
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ERPNextClientError(Exception):
    pass


class ERPNextClient:
    """
    HTTP client for the Frappe REST API (token-based auth).

    Usage:
        client = ERPNextClient()
        client.get("Customer", "CUST-001")
        client.create("ToDo", {"description": "Hello"})
        client.call_method("frappe.auth.get_logged_user")
    """

    def __init__(self):
        self.base_url = settings.ERPNEXT_URL.rstrip("/")
        self.api_key = settings.ERPNEXT_API_KEY
        self.api_secret = settings.ERPNEXT_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"token {self.api_key}:{self.api_secret}",
        })

    def _url(self, path):
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _request(self, method, path, **kwargs):
        url = self._url(path)
        logger.debug(f"ERPNext {method} {url}")
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            logger.error(f"ERPNext HTTP {e.response.status_code}: {e.response.text}")
            raise ERPNextClientError(e.response.text) from e
        except requests.RequestException as e:
            logger.error(f"ERPNext request failed: {e}")
            raise ERPNextClientError(str(e)) from e

    def get(self, doctype, name=None, fields=None, filters=None):
        """GET /api/resource/{doctype}[/{name}]"""
        if name:
            path = f"/api/resource/{doctype}/{name}"
            return self._request("GET", path)
        path = f"/api/resource/{doctype}"
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        return self._request("GET", path, params=params)

    def create(self, doctype, data):
        """POST /api/resource/{doctype}"""
        path = f"/api/resource/{doctype}"
        return self._request("POST", path, json=data)

    def update(self, doctype, name, data):
        """PUT /api/resource/{doctype}/{name}"""
        path = f"/api/resource/{doctype}/{name}"
        return self._request("PUT", path, json=data)

    def delete(self, doctype, name):
        """DELETE /api/resource/{doctype}/{name}"""
        path = f"/api/resource/{doctype}/{name}"
        return self._request("DELETE", path)

    def call_method(self, method_name, params=None):
        """POST /api/method/{method_name}"""
        path = f"/api/method/{method_name}"
        return self._request("POST", path, json=params or {})
