from multiexplorer.models import IPTracker
from django.http import HttpResponse

class IPLimiterMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META['REMOTE_ADDR']

        if not request.path.startswith("/api/") or IPTracker.allow(ip):
            response = self.get_response(request)
            return response

        return HttpResponse(
            '{"error": "Too many requests"}',
            content_type="application/json",
            status=429
        )
