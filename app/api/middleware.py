from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import APIKey


class APIKeyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path = request.path_info

        if not path.startswith('/api/'):
            return None

        if request.user.is_authenticated:
            return None

        raw_key = request.META.get('HTTP_X_API_KEY', '')
        if not raw_key:
            return JsonResponse({'error': 'Missing X-API-Key header'}, status=401)

        for api_key in APIKey.objects.filter(is_active=True):
            if api_key.verify_key(raw_key):
                api_key.record_usage()
                request.api_key_name = api_key.name
                # Mark this request as exempt from CSRF
                request._dont_enforce_csrf_checks = True
                return None

        return JsonResponse({'error': 'Invalid API key'}, status=401)
