from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from .models import APIKey

PUBLIC_API_PATHS = [
    "/api/donation-pledges/",
]


class APIKeyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path = request.path_info

        if not path.startswith('/api/'):
            return None

        # Public endpoints — no API key required
        for public_path in PUBLIC_API_PATHS:
            if path.startswith(public_path) and request.method == "POST":
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
                request._dont_enforce_csrf_checks = True
                # Create a fake user so REST Framework auth passes
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user, _ = User.objects.get_or_create(
                    username=f"apikey-{api_key.name}",
                    defaults={"is_active": True}
                )
                request.user = user
                return None

        return JsonResponse({'error': 'Invalid API key'}, status=401)
